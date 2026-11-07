from ag_tokens_inspector.report import format_report
from ag_tokens_inspector.stats import new_stats, record_usage


def test_report_sorted_with_grand_total():
    stats = new_stats()
    record_usage(stats, "small", 1, 0, 0, 0)
    record_usage(stats, "big", 1000, 0, 0, 0)
    out = format_report(stats)
    assert out.index("big") < out.index("small")
    last = [line for line in out.splitlines() if line.startswith("GRAND TOTAL")][0]
    assert "1,001" in last


def test_report_empty():
    assert "GRAND TOTAL" in format_report(new_stats())
