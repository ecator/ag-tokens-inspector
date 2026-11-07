"""Fallback usage extraction through the local Language Server RPC (.pb sessions)."""

import json
import re
import ssl
import subprocess
import urllib.request
from datetime import date, datetime

from .dates import in_range
from .stats import Stats, record_usage

RPC_PATH = "/exa.language_server_pb.LanguageServerService/"


def get_ls_rpc_info() -> dict | None:
    """Find a running language server and return its pid, CSRF token and listening ports."""
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
            port_cmd = (
                f"(Get-NetTCPConnection -OwningProcess {pid} -State Listen "
                "-ErrorAction SilentlyContinue).LocalPort"
            )
            ports_out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", port_cmd], text=True
            ).strip()
            ports = [int(x) for x in ports_out.splitlines() if x.strip().isdigit()]
            if ports:
                return {"pid": pid, "csrf": m.group(1), "ports": ports}
    except Exception:
        pass
    return None


def call_ls_rpc(port: int, csrf: str, method: str, payload: dict) -> dict | None:
    """Call a Language Server RPC method, trying https then http on localhost."""
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Connect-Protocol-Version": "1",
        "x-codeium-csrf-token": csrf,
    }
    ctx = ssl._create_unverified_context()  # local loopback server uses a self-signed cert
    for scheme in ("https", "http"):
        url = f"{scheme}://127.0.0.1:{port}{RPC_PATH}{method}"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, context=ctx if scheme == "https" else None, timeout=2) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue
    return None


def _node_day(node: dict) -> date | None:
    """Best-effort local date from an RPC node's timestamp fields."""
    for key in ("createdAt", "timestamp", "startTime", "endTime"):
        value = node.get(key)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().date()
            except ValueError:
                continue
    return None


def extract_rpc_usage(
    node,
    stats: Stats,
    seen_uuids: set,
    cascade_id: str,
    start: date | None = None,
    end: date | None = None,
    day: date | None = None,
) -> None:
    """Recursively extract usage from a GetCascadeTrajectoryGeneratorMetadata response.

    When a date range is given, only nodes whose (inherited) day is in range are counted.
    """
    if isinstance(node, dict):
        day = _node_day(node) or day
        usage = node.get("usage") or node.get("tokenUsage") or node.get("usageMetadata") or {}
        if isinstance(usage, dict):
            prompt = int(
                usage.get("promptTokens") or usage.get("inputTokens") or usage.get("promptTokenCount") or 0
            )
            output = int(
                usage.get("candidatesTokens")
                or usage.get("outputTokens")
                or usage.get("candidatesTokenCount")
                or 0
            )
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
                if uid not in seen_uuids and in_range(day, start, end):
                    seen_uuids.add(uid)
                    record_usage(stats, model, prompt, cached, output, thoughts)
        for v in node.values():
            extract_rpc_usage(v, stats, seen_uuids, cascade_id, start, end, day)
    elif isinstance(node, list):
        for item in node:
            extract_rpc_usage(item, stats, seen_uuids, cascade_id, start, end, day)
