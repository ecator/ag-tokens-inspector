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
