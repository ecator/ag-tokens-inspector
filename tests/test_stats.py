from ag_tokens_inspector.stats import ModelStats, new_stats, record_usage


def test_total_excludes_requests():
    assert ModelStats(requests=5, prompt=1, cached=2, output=3, thoughts=4).total == 10


def test_record_usage_accumulates():
    stats = new_stats()
    record_usage(stats, "m", 1, 2, 3, 4)
    record_usage(stats, "m", 1, 2, 3, 4)
    assert stats["m"] == ModelStats(2, 2, 4, 6, 8)
