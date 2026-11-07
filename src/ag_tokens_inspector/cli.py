"""Command line entry point."""

from pathlib import Path

from . import __app_name__, __version__
from .report import format_report
from .rpc import call_ls_rpc, extract_rpc_usage, get_ls_rpc_info
from .sqlite_source import parse_sqlite_db
from .stats import new_stats


def get_conversation_roots(home: Path | None = None) -> list[Path]:
    """Return the candidate conversation directories under the home directory."""
    home = home or Path.home()
    return [
        home / ".gemini" / "antigravity" / "conversations",
        home / ".gemini" / "antigravity-cli" / "conversations",
        home / ".gemini" / "antigravity-ide" / "conversations",
        home / ".antigravity-ide" / "conversations",
    ]


def main() -> int:
    """Scan all conversations and print the token usage report."""
    print(f"{__app_name__} v{__version__}")
    db_files: list[Path] = []
    pb_files: list[Path] = []
    for root in get_conversation_roots():
        if root.exists():
            db_files.extend(root.glob("*.db"))
            pb_files.extend(root.glob("*.pb"))

    print(
        f"Scan complete: found {len(db_files)} SQLite (.db) conversation databases "
        f"and {len(pb_files)} encrypted (.pb) conversation files."
    )

    stats = new_stats()
    seen_uuids: set = set()

    # 1. Parse all .db files directly.
    db_turns = sum(parse_sqlite_db(db, seen_uuids, stats) for db in db_files)
    if db_files:
        print(f"Extracted {db_turns} model call records from .db databases.")

    # 2. For .pb files without a .db, query the local Language Server over RPC.
    pb_only_ids = {p.stem for p in pb_files} - {d.stem for d in db_files}
    if pb_only_ids:
        ls_info = get_ls_rpc_info()
        if ls_info:
            print(
                f"Querying local Language Server (PID: {ls_info['pid']}) "
                f"for {len(pb_only_ids)} .pb conversations..."
            )
            working_port = None
            for cid in pb_only_ids:
                ports_to_try = [working_port] if working_port else ls_info["ports"]
                for port in ports_to_try:
                    res = call_ls_rpc(
                        port, ls_info["csrf"], "GetCascadeTrajectoryGeneratorMetadata", {"cascadeId": cid}
                    )
                    if res:
                        working_port = port
                        extract_rpc_usage(res, stats, seen_uuids, cid)
                        break
        else:
            print(
                f"Note: {len(pb_only_ids)} legacy encrypted .pb conversations were skipped; "
                "keep the Antigravity IDE running and rerun to include them."
            )

    # 3. Print the summary report.
    print(format_report(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
