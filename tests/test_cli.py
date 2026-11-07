from pathlib import Path

import pytest

from ag_tokens_inspector import cli


def test_get_conversation_roots():
    roots = cli.get_conversation_roots(Path("/h"))
    assert Path("/h/.antigravity-ide/conversations") in roots
    assert len(roots) == 4


def test_main_without_data(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "get_conversation_roots", lambda: [tmp_path / "missing"])
    assert cli.main([]) == 0
    assert "GRAND TOTAL" in capsys.readouterr().out


def test_main_reports_pb_only_without_language_server(monkeypatch, capsys, tmp_path):
    (tmp_path / "x.pb").write_bytes(b"")
    monkeypatch.setattr(cli, "get_conversation_roots", lambda: [tmp_path])
    monkeypatch.setattr(cli, "get_ls_rpc_info", lambda: None)
    cli.main([])
    assert "skipped" in capsys.readouterr().out


def test_main_uses_rpc_for_pb_only(monkeypatch, capsys, tmp_path):
    (tmp_path / "x.pb").write_bytes(b"")
    monkeypatch.setattr(cli, "get_conversation_roots", lambda: [tmp_path])
    monkeypatch.setattr(cli, "get_ls_rpc_info", lambda: {"pid": 1, "csrf": "c", "ports": [9]})
    resp = {"generationId": "g", "model": "M", "usage": {"promptTokens": 5}}
    monkeypatch.setattr(cli, "call_ls_rpc", lambda *a: resp)
    cli.main([])
    assert "M" in capsys.readouterr().out


def test_main_prints_name_and_version(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "get_conversation_roots", lambda: [tmp_path / "missing"])
    cli.main([])
    assert capsys.readouterr().out.startswith(f"{cli.__app_name__} v{cli.__version__}")


def test_parse_args_dates_and_validation():
    from datetime import date

    args = cli.parse_args(["--from", "2026-01-02", "--to", "20260103"])
    assert args.start == date(2026, 1, 2) and args.end == date(2026, 1, 3)
    with pytest.raises(SystemExit):
        cli.parse_args(["--from", "bad"])
    with pytest.raises(SystemExit):
        cli.parse_args(["--from", "20260104", "--to", "20260103"])
