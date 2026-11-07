import sqlite3

from ag_tokens_inspector.sqlite_source import parse_sqlite_db
from ag_tokens_inspector.stats import new_stats


def ld(num, payload):
    return bytes([(num << 3) | 2 if num < 16 else 0xAA, *([1] if num >= 16 else []), len(payload)]) + payload


def blob(uuid: bytes, prompt: int) -> bytes:
    usage = bytes([2 << 3, prompt])
    return ld(1, ld(4, usage) + ld(21, b"M")) + ld(4, uuid)


def make_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE gen_metadata (idx INTEGER, data BLOB)")
    conn.executemany("INSERT INTO gen_metadata VALUES (?, ?)", rows)
    conn.commit()
    conn.close()


def test_parse_counts_and_deduplicates(tmp_path):
    db = tmp_path / "c.db"
    make_db(db, [(0, blob(b"a", 5)), (1, blob(b"a", 5)), (2, blob(b"b", 7)), (3, "text")])
    stats, seen = new_stats(), set()
    assert parse_sqlite_db(db, seen, stats) == 2
    assert stats["M"].prompt == 12
    assert stats["M"].requests == 2
    assert parse_sqlite_db(db, seen, stats) == 0


def test_parse_without_table(tmp_path):
    db = tmp_path / "c.db"
    sqlite3.connect(db).execute("CREATE TABLE other (x)").connection.close()
    assert parse_sqlite_db(db, set(), new_stats()) == 0


def test_parse_missing_file(tmp_path):
    assert parse_sqlite_db(tmp_path / "none.db", set(), new_stats()) == 0


def step_meta(seconds: int) -> bytes:
    return ld(1, bytes([1 << 3]) + varint(seconds))


def varint(n: int) -> bytes:
    out = bytearray()
    while n > 0x7F:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def blob_at(uuid: bytes, prompt: int, step: int) -> bytes:
    kv = ld(1, b"last_step_index") + ld(2, str(step).encode())
    usage = bytes([2 << 3, prompt])
    return ld(1, ld(4, usage) + ld(21, b"M") + bytes([0xA2, 1, len(kv)]) + kv) + ld(4, uuid)


def test_parse_filters_by_date(tmp_path):
    from datetime import datetime

    day1 = int(datetime(2026, 1, 1, 23, 59).timestamp())
    day3 = int(datetime(2026, 1, 3, 0, 1).timestamp())
    db = tmp_path / "c.db"
    make_db(db, [(0, blob_at(b"a", 1, 0)), (1, blob_at(b"b", 2, 2)), (2, blob_at(b"c", 4, 3))])
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE steps (idx INTEGER, metadata BLOB)")
    conn.executemany("INSERT INTO steps VALUES (?, ?)", [(0, step_meta(day1)), (2, step_meta(day3))])
    conn.commit()
    conn.close()
    from datetime import date

    stats = new_stats()
    assert parse_sqlite_db(db, set(), stats, date(2026, 1, 3), date(2026, 1, 3)) == 2
    assert stats["M"].prompt == 6
    stats = new_stats()
    assert parse_sqlite_db(db, set(), stats, None, date(2026, 1, 1)) == 1
    assert stats["M"].prompt == 1
