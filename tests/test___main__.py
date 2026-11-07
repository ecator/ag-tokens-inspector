import runpy

import pytest

from ag_tokens_inspector import cli


def test_module_entry_exits(monkeypatch):
    monkeypatch.setattr(cli, "main", lambda: 0)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("ag_tokens_inspector.__main__", run_name="__main__")
    assert exc.value.code == 0
