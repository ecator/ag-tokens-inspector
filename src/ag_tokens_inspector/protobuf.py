"""Schema-less Protobuf wire format decoder."""

from collections import defaultdict

Fields = dict[int, list[tuple[int, object]]]


def read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    """Read a Protobuf varint and return (value, new_position)."""
    result = 0
    shift = 0
    while pos < len(buf):
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
    raise ValueError("Truncated varint")


def parse_proto_fields(buf: bytes) -> Fields:
    """Parse a Protobuf binary blob without a schema.

    Returns {field_num: [(wire_type, value), ...]}. Parsing stops quietly at
    the first malformed or truncated element.
    """
    fields: Fields = defaultdict(list)
    pos = 0
    n = len(buf)
    while pos < n:
        try:
            tag, pos = read_varint(buf, pos)
        except ValueError:
            break
        field_num = tag >> 3
        wire_type = tag & 0x07
        if field_num == 0:
            break

        if wire_type == 0:  # Varint
            try:
                val, pos = read_varint(buf, pos)
            except ValueError:
                break
            fields[field_num].append((0, val))
        elif wire_type == 1:  # 64-bit
            if pos + 8 > n:
                break
            fields[field_num].append((1, buf[pos : pos + 8]))
            pos += 8
        elif wire_type == 2:  # Length-delimited (bytes / string / sub-message)
            try:
                length, pos = read_varint(buf, pos)
            except ValueError:
                break
            if pos + length > n:
                break
            fields[field_num].append((2, buf[pos : pos + length]))
            pos += length
        elif wire_type == 5:  # 32-bit
            if pos + 4 > n:
                break
            fields[field_num].append((5, buf[pos : pos + 4]))
            pos += 4
        else:
            break
    return fields


def get_first_varint(fields: Fields, num: int, default: int = 0) -> int:
    """Return the first varint value of a field, or the default."""
    for wt, val in fields.get(num, []):
        if wt == 0:
            return val
    return default


def get_first_str(fields: Fields, num: int, default: str = "") -> str:
    """Return the first UTF-8 decodable string of a field, or the default."""
    for wt, val in fields.get(num, []):
        if wt == 2:
            try:
                return val.decode("utf-8")
            except UnicodeDecodeError:
                pass
    return default
