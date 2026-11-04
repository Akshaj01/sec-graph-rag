"""
Paired bootstrap confidence intervals for the hybrid vs vector-only gap.

Each draw picks questions with replacement. A question keeps its hybrid
score and its vector-only score together, so the gap is not a comparison
of two unrelated samples.

The interval is the middle 95% of those recomputed gaps (percentile,
linear interpolation). The point estimate is the mean on the original
list, not the mean of the draws.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

DEFAULT_JUDGED = (
    Path(__file__).resolve().parent
    / "benchmarks"
    / "results"
    / "multi_company_smoke_judged.json"
)
DEFAULT_OUT = (
    Path(__file__).resolve().parent / "benchmarks" / "results" / "ablation_bootstrap.md"
)
N_RESAMPLES = 10_000
SEED = 0
LEVEL = 0.95

Pair = Tuple[float, float]


def percentile(sorted_values: Sequence[float], p: float) -> float:
    """Linear interpolation. Index is p * (n - 1) on an ascending list."""
    if not sorted_values:
        raise ValueError("percentile requires values")
    if p < 0.0 or p > 1.0:
        raise ValueError("p must be in [0, 1]")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = p * (len(sorted_values) - 1)
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    weight = position - low
    return sorted_values[low] * (1.0 - weight) + sorted_values[high] * weight


def bootstrap_paired(
    pairs: Sequence[Pair],
    *,
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
    level: float = LEVEL,
) -> Dict[str, float]:
    """
    Point means plus a percentile interval for hybrid, vector-only, and
    hybrid − vector-only. One index list per draw feeds all three.
    """
    if n_resamples < 1:
        raise ValueError("n_resamples must be >= 1")
    if not 0.0 < level < 1.0:
        raise ValueError("level must be between 0 and 1")
    if not pairs:
        raise ValueError("bootstrap_paired requires at least one question")

    hybrid = [float(h) for h, _ in pairs]
    vector = [float(v) for _, v in pairs]
    n = len(pairs)
    rng = random.Random(seed)
    hybrid_draws: List[float] = []
    vector_draws: List[float] = []
    gap_draws: List[float] = []
    for _ in range(n_resamples):
        indexes = [rng.randrange(n) for _ in range(n)]
        hybrid_mean = sum(hybrid[i] for i in indexes) / n
        vector_mean = sum(vector[i] for i in indexes) / n
        hybrid_draws.append(hybrid_mean)
        vector_draws.append(vector_mean)
        gap_draws.append(hybrid_mean - vector_mean)

    tail = (1.0 - level) / 2.0
    hybrid_draws.sort()
    vector_draws.sort()
    gap_draws.sort()
    return {
        "n": n,
        "hybrid_mean": sum(hybrid) / n,
        "hybrid_low": percentile(hybrid_draws, tail),
        "hybrid_high": percentile(hybrid_draws, 1.0 - tail),
        "vector_mean": sum(vector) / n,
        "vector_low": percentile(vector_draws, tail),
        "vector_high": percentile(vector_draws, 1.0 - tail),
        "gap_mean": (sum(hybrid) - sum(vector)) / n,
        "gap_low": percentile(gap_draws, tail),
        "gap_high": percentile(gap_draws, 1.0 - tail),
        "n_resamples": n_resamples,
        "seed": seed,
        "level": level,
    }


def load_pairs(path: Path = DEFAULT_JUDGED) -> Dict[str, List[Pair]]:
    """Slice judged scores into the same buckets as the README generation table."""
    report = json.loads(path.read_text())
    hybrid = {row["item_id"]: row for row in report["hybrid"]["results"]}
    vector = {row["item_id"]: row for row in report["vector_only"]["results"]}
    if set(hybrid) != set(vector):
        raise ValueError("hybrid and vector-only item ids differ")

    slices: Dict[str, List[Pair]] = {
        "overall": [],
        "hop_0": [],
        "hop_1": [],
        "hop_2": [],
        "oos": [],
    }
    for item_id, row in hybrid.items():
        pair = (float(row["score"]), float(vector[item_id]["score"]))
        slices["overall"].append(pair)
        if row["must_refuse"]:
            slices["oos"].append(pair)
        else:
            slices[f"hop_{int(row['hop'])}"].append(pair)
    return slices


def render_markdown(results: Dict[str, Dict[str, float]]) -> str:
    lines = [
        "# Ablation bootstrap — hybrid vs vector-only",
        "",
        "Paired bootstrap on the judged generation scores in "
        "`multi_company_smoke_judged.json`. Each draw resamples questions "
        "with replacement and keeps a question's hybrid and vector-only "
        "scores together. The 95% interval is the middle 95% of "
        f"{N_RESAMPLES} draws (seed {SEED}). The point estimate is the "
        "original mean. Gap is hybrid minus vector-only.",
        "",
        "| Slice | n | Hybrid mean | Hybrid 95% CI | Vector mean | Vector 95% CI | Gap | Gap 95% CI |",
        "|-------|--:|------------:|---------------|------------:|---------------|----:|------------|",
    ]
    for name in ("overall", "hop_0", "hop_1", "hop_2", "oos"):
        row = results[name]
        lines.append(
            "| {name} | {n} | {hm} | {hl} – {hh} | {vm} | {vl} – {vh} | {gm} | {gl} – {gh} |".format(
                name=name,
                n=int(row["n"]),
                hm=_fmt(row["hybrid_mean"]),
                hl=_fmt(row["hybrid_low"]),
                hh=_fmt(row["hybrid_high"]),
                vm=_fmt(row["vector_mean"]),
                vl=_fmt(row["vector_low"]),
                vh=_fmt(row["vector_high"]),
                gm=_fmt(row["gap_mean"]),
                gl=_fmt(row["gap_low"]),
                gh=_fmt(row["gap_high"]),
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_report(
    judged: Path = DEFAULT_JUDGED,
    out: Path = DEFAULT_OUT,
) -> Dict[str, Dict[str, float]]:
    slices = load_pairs(judged)
    results = {name: bootstrap_paired(pairs) for name, pairs in slices.items()}
    out.write_text(render_markdown(results))
    out.with_suffix(".json").write_text(json.dumps(results, indent=2) + "\n")
    return results


def _fmt(value: float) -> str:
    return f"{value:.3f}"


def main() -> None:
    results = write_report()
    for name in ("overall", "hop_2"):
        row = results[name]
        print(
            f"{name} n={int(row['n'])} gap={row['gap_mean']:.3f} "
            f"[{row['gap_low']:.3f}, {row['gap_high']:.3f}]"
        )


if __name__ == "__main__":
    main()
