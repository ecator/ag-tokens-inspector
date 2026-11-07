import json
import subprocess

from ag_tokens_inspector import rpc
from ag_tokens_inspector.stats import new_stats


def test_extract_rpc_usage_nested_and_dedup():
    node = {
        "items": [
            {
                "generationId": "g1",
                "modelDisplayName": "M",
                "usage": {"promptTokens": "3", "candidatesTokens": 2, "cachedTokens": 1, "thoughtTokens": 4},
            },
            {"generationId": "g1", "model": "M", "usage": {"promptTokens": 3}},
            {"uuid": "g2", "usage": {"inputTokens": 1}},
            {"usage": {}},
        ]
    }
    stats, seen = new_stats(), set()
    rpc.extract_rpc_usage(node, stats, seen, "c")
    assert stats["M"].requests == 1
    assert stats["M"].total == 10
    assert stats["unknown-rpc"].prompt == 1


def test_get_ls_rpc_info_parses_process(monkeypatch):
    procs = json.dumps({"ProcessId": 7, "CommandLine": "ls --csrf_token abc-1"})
    outputs = iter([procs, "1234\n5678"])
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: next(outputs))
    assert rpc.get_ls_rpc_info() == {"pid": 7, "csrf": "abc-1", "ports": [1234, 5678]}


def test_get_ls_rpc_info_handles_empty_and_errors(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "")
    assert rpc.get_ls_rpc_info() is None

    def boom(*a, **k):
        raise OSError

    monkeypatch.setattr(subprocess, "check_output", boom)
    assert rpc.get_ls_rpc_info() is None


def test_call_ls_rpc_success(monkeypatch):
    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"ok": true}'

    seen = []

    def fake_urlopen(req, context=None, timeout=None):
        seen.append(req.full_url)
        return Resp()

    monkeypatch.setattr(rpc.urllib.request, "urlopen", fake_urlopen)
    assert rpc.call_ls_rpc(1, "t", "M", {}) == {"ok": True}
    assert seen == ["https://127.0.0.1:1" + rpc.RPC_PATH + "M"]


def test_call_ls_rpc_failure(monkeypatch):
    def fail(*a, **k):
        raise OSError

    monkeypatch.setattr(rpc.urllib.request, "urlopen", fail)
    assert rpc.call_ls_rpc(1, "t", "M", {}) is None
