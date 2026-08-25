"""
Phase 5 Step Q: Load and inspect the labeled benchmark suite.

Does not run hybrid/vector eval (Step R). CLI lists items + hop counts.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark_schema import BenchmarkSuite

DEFAULT_SUITE_PATH = Path(__file__).resolve().parent / "benchmarks" / "aapl_smoke.json"


def load_suite(path: Path | str | None = None) -> BenchmarkSuite:
    """Load a versioned BenchmarkSuite from JSON."""
    suite_path = Path(path) if path else DEFAULT_SUITE_PATH
    raw = json.loads(suite_path.read_text(encoding="utf-8"))
    return BenchmarkSuite.model_validate(raw)


def print_suite_summary(suite: BenchmarkSuite) -> None:
    counts = suite.summary_counts()
    print(f"suite={suite.name} version={suite.version}")
    print(f"corpus: {suite.corpus_notes}")
    print("counts:", json.dumps(counts, indent=2))
    print()
    buckets = suite.by_hop()
    for bucket, items in buckets.items():
        print(f"## {bucket} ({len(items)})")
        for item in items:
            route = item.expected_route.value
            refuse = " REFUSE" if item.must_refuse else ""
            print(f"  - {item.id}: {item.question} [{route}]{refuse}")
        print()


if __name__ == "__main__":
    import sys

    path = None
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        path = args[0]
    suite = load_suite(path)
    print_suite_summary(suite)
