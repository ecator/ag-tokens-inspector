"""Summary table rendering."""

from .stats import Stats

WIDTH = 105


def format_report(stats: Stats) -> str:
    """Render the per-model usage table with a grand total row."""
    header = (
        f"{'Model':<28} | {'Calls':<6} | {'Input (Prompt)':<14} | {'Cache Read':<14} | "
        f"{'Output':<10} | {'Thoughts':<10} | {'Total':<12}"
    )
    lines = ["", "=" * WIDTH, header, "=" * WIDTH]

    req = prompt = cached = output = thoughts = total = 0
    for model, s in sorted(stats.items(), key=lambda x: x[1].total, reverse=True):
        lines.append(
            f"{model:<28} | {s.requests:<6} | {s.prompt:<14,d} | {s.cached:<14,d} | "
            f"{s.output:<10,d} | {s.thoughts:<10,d} | {s.total:<12,d}"
        )
        req += s.requests
        prompt += s.prompt
        cached += s.cached
        output += s.output
        thoughts += s.thoughts
        total += s.total

    lines.append("-" * WIDTH)
    lines.append(
        f"{'GRAND TOTAL':<28} | {req:<6} | {prompt:<14,d} | {cached:<14,d} | "
        f"{output:<10,d} | {thoughts:<10,d} | {total:<12,d}"
    )
    lines.append("=" * WIDTH)
    return "\n".join(lines)
