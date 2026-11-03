import json
import os
import re
import sqlite3
import ssl
import subprocess
import urllib.request
from collections import defaultdict
from pathlib import Path

# ==================== 1. 纯 Python Protobuf Wire 解码器 ====================
def read_varint(buf: bytes, pos: int):
    """读取 Protobuf Varint 整数"""
    result = 0
    shift = 0
    while pos < len(buf):
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
    raise ValueError("Truncated varint")

def parse_proto_fields(buf: bytes):
    """无 Schema 解析 Protobuf 二进制流，返回 {field_num: [(wire_type, value), ...]}"""
    fields = defaultdict(list)
    pos = 0
    n = len(buf)
    while pos < n:
        try:
            tag, pos = read_varint(buf, pos)
        except ValueError:
            break
        field_num = tag >> 3
        wire_type = tag & 0x07
        if field_num == 0:
            break

        if wire_type == 0:  # Varint
            val, pos = read_varint(buf, pos)
            fields[field_num].append((0, val))
        elif wire_type == 1:  # 64-bit
            if pos + 8 > n:
                break
            fields[field_num].append((1, buf[pos:pos+8]))
            pos += 8
        elif wire_type == 2:  # Length-delimited (bytes / string / sub-message)
            length, pos = read_varint(buf, pos)
            if pos + length > n or length < 0:
                break
            fields[field_num].append((2, buf[pos:pos+length]))
            pos += length
        elif wire_type == 5:  # 32-bit
            if pos + 4 > n:
                break
            fields[field_num].append((5, buf[pos:pos+4]))
            pos += 4
        else:
            break
    return fields

def get_first_varint(fields, num, default=0):
    for wt, val in fields.get(num, []):
        if wt == 0:
            return val
    return default

def get_first_str(fields, num, default=""):
    for wt, val in fields.get(num, []):
        if wt == 2:
            try:
                return val.decode("utf-8")
            except UnicodeDecodeError:
                pass
    return default

def decode_gen_metadata_blob(blob: bytes, fallback_model="unknown"):
    """
    按照 ccusage / CodeBurn 逆向的 Schema 解析 gen_metadata.data:
    - .4       -> Generation UUID (去重键)
    - .1       -> ChatModel
    - .1.19    -> model_config_id (如 gemini-pro-default)
    - .1.21    -> display_name
    - .1.4     -> Token Usage 子消息:
        - .1.4.2 -> prompt_tokens
        - .1.4.3 -> candidates_tokens (output)
        - .1.4.5 -> cached_tokens
        - .1.4.9 -> thought_tokens
    """
    root = parse_proto_fields(blob)
    gen_uuid = get_first_str(root, 4, "")

    chat_model_entries = root.get(1, [])
    if not chat_model_entries or chat_model_entries[0][0] != 2:
        return None

    chat_model = parse_proto_fields(chat_model_entries[0][1])
    model_name = (
        get_first_str(chat_model, 21)
        or get_first_str(chat_model, 19)
        or fallback_model
    )

    usage_entries = chat_model.get(4, [])
    if not usage_entries or usage_entries[0][0] != 2:
        return None

    usage = parse_proto_fields(usage_entries[0][1])
    prompt = get_first_varint(usage, 2, 0)
    candidates = get_first_varint(usage, 3, 0)
    cached = get_first_varint(usage, 5, 0)
    thoughts = get_first_varint(usage, 9, 0)

    if prompt == 0 and candidates == 0 and cached == 0 and thoughts == 0:
        return None

    return {
        "uuid": gen_uuid,
        "model": model_name,
        "prompt": prompt,
        "output": candidates,
        "cached": cached,
        "thoughts": thoughts,
    }

# ==================== 2. 扫描 SQLite (.db) 会话文件 ====================
def parse_sqlite_db(db_path: Path, seen_uuids: set, stats: dict):
    try:
        # 使用只读 URI 模式打开，避免干扰正在运行的 WAL 写入
        uri = f"file:{db_path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=2)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gen_metadata'")
        if not cur.fetchone():
            conn.close()
            return 0

        cur.execute("SELECT idx, data FROM gen_metadata ORDER BY idx ASC")
        last_model = "unknown"
        count = 0
        for idx, blob in cur.fetchall():
            if not isinstance(blob, bytes):
                continue
            res = decode_gen_metadata_blob(blob, fallback_model=last_model)
            if not res:
                continue
            if res["model"] != "unknown":
                last_model = res["model"]

            # 按 Generation UUID 或 (db名, idx) 去重
            dedup_key = res["uuid"] if res["uuid"] else f"{db_path.stem}:{idx}"
            if dedup_key in seen_uuids:
                continue
            seen_uuids.add(dedup_key)

            m = res["model"]
            stats[m]["requests"] += 1
            stats[m]["prompt"] += res["prompt"]
            stats[m]["cached"] += res["cached"]
            stats[m]["output"] += res["output"]
            stats[m]["thoughts"] += res["thoughts"]
            count += 1

        conn.close()
        return count
    except Exception:
        return 0

# ==================== 3. RPC 回退解析 (.pb 加密会话文件) ====================
def get_ls_rpc_info():
    ps_cmd = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match 'language_server' -and $_.CommandLine -match 'csrf_token' } | "
        "Select-Object ProcessId, CommandLine | ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd], text=True).strip()
        if not out:
            return None
        procs = json.loads(out)
        if isinstance(procs, dict):
            procs = [procs]
        for p in procs:
            cmd = p.get("CommandLine", "")
            pid = p.get("ProcessId")
            m = re.search(r"--csrf_token[=\s]+([a-zA-Z0-9\-_]+)", cmd)
            if not m:
                continue
            port_cmd = f"(Get-NetTCPConnection -OwningProcess {pid} -State Listen -ErrorAction SilentlyContinue).LocalPort"
            ports_out = subprocess.check_output(["powershell", "-NoProfile", "-Command", port_cmd], text=True).strip()
            ports = [int(x) for x in ports_out.splitlines() if x.strip().isdigit()]
            if ports:
                return {"pid": pid, "csrf": m.group(1), "ports": ports}
    except Exception:
        pass
    return None

def call_ls_rpc(port, csrf, method, payload):
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Connect-Protocol-Version": "1",
        "x-codeium-csrf-token": csrf,
    }
    ctx = ssl._create_unverified_context()
    for scheme in ("https", "http"):
        url = f"{scheme}://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/{method}"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, context=ctx if scheme == "https" else None, timeout=2) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue
    return None

def extract_rpc_usage(node, stats, seen_uuids, cascade_id):
    """递归解析 GetCascadeTrajectoryGeneratorMetadata 返回的 JSON 结构"""
    if isinstance(node, dict):
        usage = node.get("usage") or node.get("tokenUsage") or node.get("usageMetadata") or {}
        if isinstance(usage, dict):
            prompt = int(usage.get("promptTokens") or usage.get("inputTokens") or usage.get("promptTokenCount") or 0)
            output = int(usage.get("candidatesTokens") or usage.get("outputTokens") or usage.get("candidatesTokenCount") or 0)
            cached = int(usage.get("cachedTokens") or usage.get("cachedContentTokenCount") or 0)
            thoughts = int(usage.get("thoughtTokens") or usage.get("thoughtsTokenCount") or 0)
            if prompt > 0 or output > 0 or cached > 0 or thoughts > 0:
                model = (
                    node.get("modelDisplayName")
                    or node.get("modelConfigId")
                    or node.get("model")
                    or "unknown-rpc"
                )
                uid = node.get("generationId") or node.get("uuid") or f"{cascade_id}:{id(node)}"
                if uid not in seen_uuids:
                    seen_uuids.add(uid)
                    stats[model]["requests"] += 1
                    stats[model]["prompt"] += prompt
                    stats[model]["cached"] += cached
                    stats[model]["output"] += output
                    stats[model]["thoughts"] += thoughts
        for v in node.values():
            extract_rpc_usage(v, stats, seen_uuids, cascade_id)
    elif isinstance(node, list):
        for item in node:
            extract_rpc_usage(item, stats, seen_uuids, cascade_id)

def main():
    home = Path.home()
    conv_roots = [
        home / ".gemini" / "antigravity" / "conversations",
        home / ".gemini" / "antigravity-cli" / "conversations",
        home / ".gemini" / "antigravity-ide" / "conversations",
        home / ".antigravity-ide" / "conversations",
    ]

    db_files = []
    pb_files = []
    for r in conv_roots:
        if r.exists():
            db_files.extend(r.glob("*.db"))
            pb_files.extend(r.glob("*.pb"))

    print(f"📂 扫描完成: 发现 {len(db_files)} 个 SQLite (.db) 会话库, {len(pb_files)} 个加密 (.pb) 会话文件。")

    stats = defaultdict(lambda: {"requests": 0, "prompt": 0, "cached": 0, "output": 0, "thoughts": 0})
    seen_uuids = set()

    # 1. 使用 ccusage 逻辑解析所有 .db 文件
    db_turns = 0
    for db in db_files:
        db_turns += parse_sqlite_db(db, seen_uuids, stats)
    if db_files:
        print(f"✅ 从 .db 数据库成功解包 {db_turns} 条模型调用记录。")

    # 2. 如果存在未转换为 .db 的 .pb 文件，尝试通过本地 Language Server RPC 提取
    pb_only_ids = {p.stem for p in pb_files} - {d.stem for d in db_files}
    if pb_only_ids:
        ls_info = get_ls_rpc_info()
        if ls_info:
            print(f"🔗 正在通过本地 Language Server (PID: {ls_info['pid']}) 解析 {len(pb_only_ids)} 个 .pb 会话...")
            working_port = None
            for cid in pb_only_ids:
                ports_to_try = [working_port] if working_port else ls_info["ports"]
                for port in ports_to_try:
                    res = call_ls_rpc(port, ls_info["csrf"], "GetCascadeTrajectoryGeneratorMetadata", {"cascadeId": cid})
                    if res:
                        working_port = port
                        extract_rpc_usage(res, stats, seen_uuids, cid)
                        break
        else:
            print(f"💡 提示: 另有 {len(pb_only_ids)} 个旧版 .pb 加密会话；如需统计它们，请保持 Antigravity IDE 开启后重跑脚本。")

    # 3. 打印汇总报表
    print("\n" + "=" * 105)
    print(f"{'模型 (Model)':<28} | {'调用数':<6} | {'Input (Prompt)':<14} | {'Cache Read':<14} | {'Output':<10} | {'Thoughts':<10} | {'总计 (Total)':<12}")
    print("=" * 105)

    totals = {"req": 0, "in": 0, "cache": 0, "out": 0, "think": 0, "all": 0}
    for model, s in sorted(stats.items(), key=lambda x: (x[1]["prompt"] + x[1]["cached"] + x[1]["output"] + x[1]["thoughts"]), reverse=True):
        row_total = s["prompt"] + s["cached"] + s["output"] + s["thoughts"]
        print(f"{model:<28} | {s['requests']:<6} | {s['prompt']:<14,d} | {s['cached']:<14,d} | {s['output']:<10,d} | {s['thoughts']:<10,d} | {row_total:<12,d}")
        totals["req"] += s["requests"]
        totals["in"] += s["prompt"]
        totals["cache"] += s["cached"]
        totals["out"] += s["output"]
        totals["think"] += s["thoughts"]
        totals["all"] += row_total

    print("-" * 105)
    print(f"{'总计 (GRAND TOTAL)':<28} | {totals['req']:<6} | {totals['in']:<14,d} | {totals['cache']:<14,d} | {totals['out']:<10,d} | {totals['think']:<10,d} | {totals['all']:<12,d}")
    print("=" * 105)

if __name__ == "__main__":
     raise SystemExit(main())