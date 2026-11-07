"""Token usage statistics aggregation."""

from collections import defaultdict
from dataclasses import dataclass


@dataclass
class ModelStats:
    """Aggregated token counters for a single model."""

    requests: int = 0
    prompt: int = 0
    cached: int = 0
    output: int = 0
    thoughts: int = 0

    @property
    def total(self) -> int:
        """Sum of all token counters (excluding the request count)."""
        return self.prompt + self.cached + self.output + self.thoughts


Stats = defaultdict[str, ModelStats]


def new_stats() -> Stats:
    """Create an empty per-model statistics container."""
    return defaultdict(ModelStats)


def record_usage(stats: Stats, model: str, prompt: int, cached: int, output: int, thoughts: int) -> None:
    """Add one request's usage to the given model's counters."""
    s = stats[model]
    s.requests += 1
    s.prompt += prompt
    s.cached += cached
    s.output += output
    s.thoughts += thoughts
