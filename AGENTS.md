# AGENTS.md

## Language
- Communicate with the user in the same language the user writes in.
- All code, comments, docstrings, commit messages and documentation must be written in English.

## Layout
- `src/ag_tokens_inspector/`: package code (`cli.py` entry point, `protobuf.py`, `metadata.py`, `sqlite_source.py`, `rpc.py`, `stats.py`, `report.py`).
- `tests/`: unit tests mirroring the source path, e.g. `src/ag_tokens_inspector/rpc.py` -> `tests/test_rpc.py`.

## Workflow
- Use `uv` to manage the environment.
- Format and lint: `uv run ruff format . && uv run ruff check .`
- Test: `uv run pytest`
- Keep modules small and single-purpose; add or update tests with every change.
