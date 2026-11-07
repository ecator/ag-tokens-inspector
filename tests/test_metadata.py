from ag_tokens_inspector.metadata import decode_gen_metadata_blob


def tag(num: int, wire: int) -> bytes:
    value = (num << 3) | wire
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def ld(num: int, payload: bytes) -> bytes:
    return tag(num, 2) + bytes([len(payload)]) + payload


def vi(num: int, value: int) -> bytes:
    return tag(num, 0) + bytes([value])


def build(usage: bytes, name: bytes | None = b"Gemini", uuid: bytes = b"u1") -> bytes:
    chat = ld(4, usage)
    if name is not None:
        chat += ld(21, name)
    return ld(1, chat) + ld(4, uuid)


def test_decode_full_record():
    blob = build(vi(2, 10) + vi(3, 20) + vi(5, 30) + vi(9, 40))
    assert decode_gen_metadata_blob(blob) == {
        "uuid": "u1",
        "model": "Gemini",
        "prompt": 10,
        "output": 20,
        "cached": 30,
        "thoughts": 40,
    }


def test_decode_uses_fallback_model():
    blob = build(vi(2, 1), name=None)
    assert decode_gen_metadata_blob(blob, fallback_model="prev")["model"] == "prev"


def test_decode_returns_none_without_chat_model():
    assert decode_gen_metadata_blob(ld(4, b"x")) is None


def test_decode_returns_none_without_usage():
    assert decode_gen_metadata_blob(ld(1, ld(21, b"m"))) is None


def test_decode_returns_none_for_zero_usage():
    assert decode_gen_metadata_blob(build(vi(2, 0))) is None
