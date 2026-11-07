"""Scan SQLite (.db) conversation files."""

import sqlite3
from pathlib import Path

from .metadata import decode_gen_metadata_blob
from .stats import Stats, record_usage


def parse_sqlite_db(db_path: Path, seen_uuids: set, stats: Stats) -> int:
    """Accumulate usage from one conversation database into stats.

    Returns the number of newly counted model calls; 0 on any error.
    """
    try:
        # Open read-only so a running writer (WAL) is not disturbed.
        uri = f"file:{db_path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=2)
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gen_metadata'")
            if not cur.fetchone():
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

                # Deduplicate by generation UUID, or (db name, idx) as a fallback.
                dedup_key = res["uuid"] or f"{db_path.stem}:{idx}"
                if dedup_key in seen_uuids:
                    continue
                seen_uuids.add(dedup_key)

                record_usage(
                    stats, res["model"], res["prompt"], res["cached"], res["output"], res["thoughts"]
                )
                count += 1
            return count
        finally:
            conn.close()
    except Exception:
        return 0
