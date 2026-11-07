from datetime import date

import pytest

from ag_tokens_inspector.dates import in_range, parse_date, timestamp_to_date


@pytest.mark.parametrize("text", ["20260105", "2026-01-05", "2026/01/05"])
def test_parse_date_formats(text):
    assert parse_date(text) == date(2026, 1, 5)


@pytest.mark.parametrize("text", ["2026-1-5", "2026-01/05", "abc", "20261305", ""])
def test_parse_date_invalid(text):
    with pytest.raises(ValueError):
        parse_date(text)


def test_in_range_inclusive():
    a, b = date(2026, 1, 1), date(2026, 1, 3)
    assert in_range(a, a, b) and in_range(b, a, b)
    assert not in_range(date(2026, 1, 4), a, b)
    assert not in_range(date(2025, 12, 31), a, b)
    assert in_range(date(2030, 1, 1), a, None)
    assert in_range(None, None, None)
    assert not in_range(None, a, None)


def test_timestamp_to_date_roundtrip():
    assert isinstance(timestamp_to_date(0), date)
