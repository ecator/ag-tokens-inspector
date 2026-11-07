from pathlib import Path

from ag_tokens_inspector import cli


def test_get_conversation_roots():
    roots = cli.get_conversation_roots(Path("/h"))
    assert Path("/h/.antigravity-ide/conversations") in roots
    assert len(roots) == 4


def test_main_without_data(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "get_conversation_roots", lambda: [tmp_path / "missing"])
    assert cli.main() == 0
    assert "GRAND TOTAL" in capsys.readouterr().out


def test_main_reports_pb_only_without_language_server(monkeypatch, capsys, tmp_path):
    (tmp_path / "x.pb").write_bytes(b"")
    monkeypatch.setattr(cli, "get_conversation_roots", lambda: [tmp_path])
    monkeypatch.setattr(cli, "get_ls_rpc_info", lambda: None)
    cli.main()
    assert "skipped" in capsys.readouterr().out


def test_main_uses_rpc_for_pb_only(monkeypatch, capsys, tmp_path):
    (tmp_path / "x.pb").write_bytes(b"")
    monkeypatch.setattr(cli, "get_conversation_roots", lambda: [tmp_path])
    monkeypatch.setattr(cli, "get_ls_rpc_info", lambda: {"pid": 1, "csrf": "c", "ports": [9]})
    resp = {"generationId": "g", "model": "M", "usage": {"promptTokens": 5}}
    monkeypatch.setattr(cli, "call_ls_rpc", lambda *a: resp)
    cli.main()
    assert "M" in capsys.readouterr().out


def test_main_prints_name_and_version(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "get_conversation_roots", lambda: [tmp_path / "missing"])
    cli.main()
    assert capsys.readouterr().out.startswith(f"{cli.__app_name__} v{cli.__version__}")
