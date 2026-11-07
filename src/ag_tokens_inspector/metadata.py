"""Decoder for the gen_metadata blobs stored in conversation databases."""

from .protobuf import get_first_str, get_first_varint, parse_proto_fields


def decode_gen_metadata_blob(blob: bytes, fallback_model: str = "unknown") -> dict | None:
    """Decode a gen_metadata.data blob into a usage record.

    Schema (reverse-engineered by ccusage / CodeBurn):
    - .4       -> Generation UUID (dedup key)
    - .1       -> ChatModel
    - .1.19    -> model_config_id (e.g. gemini-pro-default)
    - .1.21    -> display_name
    - .1.4     -> Token usage sub-message:
        - .1.4.2 -> prompt_tokens
        - .1.4.3 -> candidates_tokens (output)
        - .1.4.5 -> cached_tokens
        - .1.4.9 -> thought_tokens

    Returns None when the blob carries no usable token usage.
    """
    root = parse_proto_fields(blob)
    gen_uuid = get_first_str(root, 4, "")

    chat_model_entries = root.get(1, [])
    if not chat_model_entries or chat_model_entries[0][0] != 2:
        return None

    chat_model = parse_proto_fields(chat_model_entries[0][1])
    model_name = get_first_str(chat_model, 21) or get_first_str(chat_model, 19) or fallback_model

    usage_entries = chat_model.get(4, [])
    if not usage_entries or usage_entries[0][0] != 2:
        return None

    usage = parse_proto_fields(usage_entries[0][1])
    prompt = get_first_varint(usage, 2, 0)
    candidates = get_first_varint(usage, 3, 0)
    cached = get_first_varint(usage, 5, 0)
    thoughts = get_first_varint(usage, 9, 0)

    if prompt == 0 and candidates == 0 and cached == 0 and thoughts == 0:
        return None

    return {
        "uuid": gen_uuid,
        "model": model_name,
        "prompt": prompt,
        "output": candidates,
        "cached": cached,
        "thoughts": thoughts,
    }
