"""Scan SQLite (.db) conversation files."""

import sqlite3
from datetime import date
from pathlib import Path

from .dates import in_range, timestamp_to_date
from .metadata import decode_gen_metadata_blob
from .protobuf import get_first_varint, parse_proto_fields
from .stats import Stats, record_usage


def load_step_dates(cur: sqlite3.Cursor) -> dict[int, date]:
    """Map step index to the local date the step was created (steps.metadata.1.1 timestamp)."""
    days: dict[int, date] = {}
    try:
        rows = cur.execute("SELECT idx, metadata FROM steps").fetchall()
    except sqlite3.Error:
        return days
    for idx, blob in rows:
        if not isinstance(blob, bytes):
            continue
        entries = parse_proto_fields(blob).get(1, [])
        if not entries or entries[0][0] != 2:
            continue
        seconds = get_first_varint(parse_proto_fields(entries[0][1]), 1, 0)
        if seconds:
            days[idx] = timestamp_to_date(seconds)
    return days


def _resolve_day(step_index: int | None, step_days: dict[int, date], fallback: date | None) -> date | None:
    """Date of the step a call belongs to, else the nearest earlier step, else the fallback."""
    if step_index is not None and step_days:
        if step_index in step_days:
            return step_days[step_index]
        earlier = [i for i in step_days if i <= step_index]
        if earlier:
            return step_days[max(earlier)]
    return fallback


def parse_sqlite_db(
    db_path: Path,
    seen_uuids: set,
    stats: Stats,
    start: date | None = None,
    end: date | None = None,
) -> int:
    """Accumulate usage from one conversation database into stats.

    Only calls whose day lies within [start, end] (inclusive, optional) are counted.

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

            filtering = start is not None or end is not None
            step_days = load_step_dates(cur) if filtering else {}
            file_day = timestamp_to_date(db_path.stat().st_mtime) if filtering else None
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

                if filtering and not in_range(
                    _resolve_day(res["step_index"], step_days, file_day), start, end
                ):
                    continue

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
