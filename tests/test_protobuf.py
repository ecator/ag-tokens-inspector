import pytest

from ag_tokens_inspector.protobuf import (
    get_first_str,
    get_first_varint,
    parse_proto_fields,
    read_varint,
)


def test_read_varint_multibyte():
    assert read_varint(b"\xac\x02", 0) == (300, 2)


def test_read_varint_truncated():
    with pytest.raises(ValueError):
        read_varint(b"\x80", 0)


def test_parse_fields_all_wire_types():
    buf = (
        b"\x08\x96\x01"  # field 1 varint 150
        + b"\x11"
        + b"\x01" * 8  # field 2 64-bit
        + b"\x1a\x03abc"  # field 3 length-delimited
        + b"\x25"
        + b"\x02" * 4  # field 4 32-bit
    )
    f = parse_proto_fields(buf)
    assert f[1] == [(0, 150)]
    assert f[2] == [(1, b"\x01" * 8)]
    assert f[3] == [(2, b"abc")]
    assert f[4] == [(5, b"\x02" * 4)]


def test_parse_fields_stops_on_truncated_data():
    assert parse_proto_fields(b"\x1a\x05ab") == {}
    assert parse_proto_fields(b"\x08") == {}


def test_parse_fields_stops_on_unknown_wire_type():
    assert parse_proto_fields(b"\x0b") == {}


def test_get_first_varint():
    f = parse_proto_fields(b"\x1a\x01a\x08\x07")
    assert get_first_varint(f, 1) == 7
    assert get_first_varint(f, 9, 42) == 42


def test_get_first_str():
    f = parse_proto_fields(b"\x0a\x02\xff\xfe\x0a\x02hi")
    assert get_first_str(f, 1) == "hi"
    assert get_first_str(f, 2, "d") == "d"
