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

import argparse
import json
import random
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

RESULTS_DIR = Path(__file__).resolve().parent / "benchmarks" / "results"
DEFAULT_JUDGED = RESULTS_DIR / "archive" / "multi_company_smoke_judged.json"
DEFAULT_OUT = RESULTS_DIR / "archive" / "ablation_bootstrap.md"
N_RESAMPLES = 10_000
SEED = 0
LEVEL = 0.95
# Legacy override for multi_company_smoke_judged.json only: that file stores a
# later one-item rerun (1.0) while the full run scored 0.375. New comparison
# files use scores as written.
LEGACY_FULL_RUN_HYBRID_SCORE = {"hop2_jpm_credit_vs_market": 0.375}
LEGACY_JUDGED_NAME = "multi_company_smoke_judged.json"

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


def _score_overrides_for(path: Path) -> Mapping[str, float]:
    if path.name == LEGACY_JUDGED_NAME:
        return LEGACY_FULL_RUN_HYBRID_SCORE
    return {}


def load_pairs(
    path: Path = DEFAULT_JUDGED,
    *,
    score_overrides: Optional[Mapping[str, float]] = None,
) -> Dict[str, List[Pair]]:
    """Slice judged scores into the same buckets as the README generation table."""
    report = json.loads(path.read_text(encoding="utf-8"))
    hybrid = {row["item_id"]: row for row in report["hybrid"]["results"]}
    vector = {row["item_id"]: row for row in report["vector_only"]["results"]}
    if set(hybrid) != set(vector):
        raise ValueError("hybrid and vector-only item ids differ")

    overrides = (
        dict(score_overrides)
        if score_overrides is not None
        else dict(_score_overrides_for(path))
    )
    slices: Dict[str, List[Pair]] = {
        "overall": [],
        "hop_0": [],
        "hop_1": [],
        "hop_2": [],
        "oos": [],
    }
    for item_id, row in hybrid.items():
        hybrid_score = overrides.get(item_id, float(row["score"]))
        pair = (hybrid_score, float(vector[item_id]["score"]))
        slices["overall"].append(pair)
        if row["must_refuse"]:
            slices["oos"].append(pair)
        else:
            slices[f"hop_{int(row['hop'])}"].append(pair)
    return slices


def render_markdown(
    results: Dict[str, Dict[str, float]],
    *,
    source_name: str,
    notes: str = "",
) -> str:
    lines = [
        "# Ablation bootstrap — hybrid vs vector-only",
        "",
        "Paired bootstrap on the judged generation scores in "
        f"`{source_name}`. Each draw resamples questions "
        "with replacement and keeps a question's hybrid and vector-only "
        "scores together. The 95% interval is the middle 95% of "
        f"{N_RESAMPLES} draws (seed {SEED}). The point estimate is the "
        "original mean. Gap is hybrid minus vector-only.",
    ]
    if notes:
        lines.extend(["", notes])
    lines.extend(
        [
            "",
            "| Slice | n | Hybrid mean | Hybrid 95% CI | Vector mean | Vector 95% CI | Gap | Gap 95% CI |",
            "|-------|--:|------------:|---------------|------------:|---------------|----:|------------|",
        ]
    )
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
    overall = results["overall"]
    hop2 = results["hop_2"]
    overall_stable = overall["gap_low"] > 0.0
    hop2_stable = hop2["gap_low"] > 0.0
    lines.extend(
        [
            "",
            "**Reading:** Overall gap {og} (95% CI {ol} – {oh}); hop-2 gap {hg} "
            "(95% CI {hl} – {hh}). ".format(
                og=_fmt(overall["gap_mean"]),
                ol=_fmt(overall["gap_low"]),
                oh=_fmt(overall["gap_high"]),
                hg=_fmt(hop2["gap_mean"]),
                hl=_fmt(hop2["gap_low"]),
                hh=_fmt(hop2["gap_high"]),
            )
            + (
                "The overall interval sits entirely above zero."
                if overall_stable
                else "The overall interval includes zero (or below), so the suite-wide lead is not stable."
            )
            + (
                " Hop-2 sits entirely above zero."
                if hop2_stable
                else " Hop-2's interval also includes zero or below."
                if not hop2_stable and hop2["gap_mean"] != 0.0
                else ""
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_report(
    judged: Path = DEFAULT_JUDGED,
    out: Path = DEFAULT_OUT,
    *,
    score_overrides: Optional[Mapping[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    judged = Path(judged)
    out = Path(out)
    overrides = (
        score_overrides
        if score_overrides is not None
        else _score_overrides_for(judged)
    )
    slices = load_pairs(judged, score_overrides=overrides)
    results = {name: bootstrap_paired(pairs) for name, pairs in slices.items()}
    notes = ""
    if judged.name == LEGACY_JUDGED_NAME and overrides:
        notes = (
            "`hop2_jpm_credit_vs_market` uses the full-run hybrid score 0.375, "
            "not the later one-item rerun of 1.0 (legacy judged file only)."
        )
    out.write_text(
        render_markdown(results, source_name=judged.name, notes=notes),
        encoding="utf-8",
    )
    out.with_suffix(".json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    return results


def load_pooled_pairs(paths: Sequence[Path]) -> Dict[str, List[Pair]]:
    """Per-item mean scores across comparison JSONs, then the usual hop slices."""
    if not paths:
        raise ValueError("load_pooled_pairs requires at least one path")
    reports = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
    ids = [row["item_id"] for row in reports[0]["hybrid"]["results"]]
    slices: Dict[str, List[Pair]] = {
        "overall": [],
        "hop_0": [],
        "hop_1": [],
        "hop_2": [],
        "oos": [],
    }
    for item_id in ids:
        hybrid_scores: List[float] = []
        vector_scores: List[float] = []
        meta = None
        for report in reports:
            hybrid_row = next(
                row for row in report["hybrid"]["results"] if row["item_id"] == item_id
            )
            vector_row = next(
                row
                for row in report["vector_only"]["results"]
                if row["item_id"] == item_id
            )
            hybrid_scores.append(float(hybrid_row["score"]))
            vector_scores.append(float(vector_row["score"]))
            meta = hybrid_row
        assert meta is not None
        pair = (
            sum(hybrid_scores) / len(hybrid_scores),
            sum(vector_scores) / len(vector_scores),
        )
        slices["overall"].append(pair)
        if meta["must_refuse"]:
            slices["oos"].append(pair)
        else:
            slices[f"hop_{int(meta['hop'])}"].append(pair)
    return slices


def write_pooled_report(
    paths: Sequence[Path],
    out: Path,
) -> Dict[str, Dict[str, float]]:
    slices = load_pooled_pairs(paths)
    results = {name: bootstrap_paired(pairs) for name, pairs in slices.items()}
    names = ", ".join(Path(p).name for p in paths)
    notes = (
        f"Per-item scores are the mean across {len(paths)} runs ({names}), "
        "then paired bootstrap."
    )
    out = Path(out)
    out.write_text(
        render_markdown(
            results,
            source_name=f"{len(paths)}-run item means",
            notes=notes,
        ),
        encoding="utf-8",
    )
    out.with_suffix(".json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    return results


def mean_of_runs(paths: Sequence[Path]) -> Dict[str, object]:
    """Mean of per-run means (overall + hop buckets) across comparison JSONs."""
    if not paths:
        raise ValueError("mean_of_runs requires at least one path")
    hybrid_means: List[float] = []
    vector_means: List[float] = []
    hop_hybrid: Dict[str, List[float]] = {
        "hop_0": [],
        "hop_1": [],
        "hop_2": [],
        "oos": [],
    }
    hop_vector: Dict[str, List[float]] = {
        "hop_0": [],
        "hop_1": [],
        "hop_2": [],
        "oos": [],
    }
    run_rows: List[Dict[str, object]] = []
    for path in paths:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
        h_mean = float(report["hybrid"]["mean_score"])
        v_mean = float(report["vector_only"]["mean_score"])
        hybrid_means.append(h_mean)
        vector_means.append(v_mean)
        h_hop = report["hybrid"]["accuracy_by_hop"]
        v_hop = report["vector_only"]["accuracy_by_hop"]
        row = {
            "path": Path(path).name,
            "hybrid": h_mean,
            "vector_only": v_mean,
            "gap": h_mean - v_mean,
            "hybrid_by_hop": {k: float(h_hop[k]) for k in hop_hybrid},
            "vector_by_hop": {k: float(v_hop[k]) for k in hop_vector},
        }
        run_rows.append(row)
        for key in hop_hybrid:
            hop_hybrid[key].append(float(h_hop[key]))
            hop_vector[key].append(float(v_hop[key]))

    def _mean(values: Sequence[float]) -> float:
        return sum(values) / len(values)

    return {
        "n_runs": len(paths),
        "paths": [Path(p).name for p in paths],
        "runs": run_rows,
        "hybrid_mean": _mean(hybrid_means),
        "hybrid_min": min(hybrid_means),
        "hybrid_max": max(hybrid_means),
        "vector_mean": _mean(vector_means),
        "vector_min": min(vector_means),
        "vector_max": max(vector_means),
        "gap_mean": _mean(hybrid_means) - _mean(vector_means),
        "by_hop": {
            key: {
                "hybrid_mean": _mean(hop_hybrid[key]),
                "vector_mean": _mean(hop_vector[key]),
                "gap_mean": _mean(hop_hybrid[key]) - _mean(hop_vector[key]),
            }
            for key in hop_hybrid
        },
    }


def render_mean_of_runs(summary: Dict[str, object]) -> str:
    lines = [
        "# Three-run generation means",
        "",
        "Mean of per-run `mean_score` values (and hop buckets). "
        "Parentheses are min-max across runs.",
        "",
        "| Run | Hybrid | Vector-only | Gap |",
        "|-----|-------:|------------:|----:|",
    ]
    for row in summary["runs"]:  # type: ignore[index]
        lines.append(
            "| {path} | {h} | {v} | {g} |".format(
                path=row["path"],
                h=_fmt(float(row["hybrid"])),
                v=_fmt(float(row["vector_only"])),
                g=_fmt(float(row["gap"])),
            )
        )
    lines.extend(
        [
            "",
            "| | Hybrid | Vector-only | Gap |",
            "|--|-------:|------------:|----:|",
            "| **Mean of runs** | {hm} ({hmin}-{hmax}) | {vm} ({vmin}-{vmax}) | {gm} |".format(
                hm=_fmt(float(summary["hybrid_mean"])),
                hmin=_fmt(float(summary["hybrid_min"])),
                hmax=_fmt(float(summary["hybrid_max"])),
                vm=_fmt(float(summary["vector_mean"])),
                vmin=_fmt(float(summary["vector_min"])),
                vmax=_fmt(float(summary["vector_max"])),
                gm=_fmt(float(summary["gap_mean"])),
            ),
            "",
            "| Hop / bucket | Hybrid mean | Vector mean | Gap |",
            "|--------------|------------:|------------:|----:|",
        ]
    )
    by_hop = summary["by_hop"]  # type: ignore[assignment]
    labels = {
        "hop_0": "Hop 0",
        "hop_1": "Hop 1",
        "hop_2": "Hop 2",
        "oos": "OOS",
    }
    for key, label in labels.items():
        row = by_hop[key]  # type: ignore[index]
        lines.append(
            "| {label} | {h} | {v} | {g} |".format(
                label=label,
                h=_fmt(float(row["hybrid_mean"])),
                v=_fmt(float(row["vector_mean"])),
                g=_fmt(float(row["gap_mean"])),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _fmt(value: float) -> str:
    return f"{value:.3f}"


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Paired bootstrap CI for hybrid vs vector-only generation scores."
    )
    parser.add_argument(
        "--judged",
        type=Path,
        default=DEFAULT_JUDGED,
        help="BenchmarkComparison JSON (default: multi_company_smoke_judged.json)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Markdown output path (sibling .json written too)",
    )
    parser.add_argument(
        "--mean-of-runs",
        nargs="+",
        type=Path,
        default=None,
        help="If set, also write mean-of-runs summary for these comparison JSONs",
    )
    parser.add_argument(
        "--mean-out",
        type=Path,
        default=None,
        help="Output path for --mean-of-runs markdown (default: beside first run)",
    )
    parser.add_argument(
        "--pool-runs",
        nargs="+",
        type=Path,
        default=None,
        help="Bootstrap on per-item means across these comparison JSONs",
    )
    parser.add_argument(
        "--pool-out",
        type=Path,
        default=None,
        help="Output path for --pool-runs markdown",
    )
    args = parser.parse_args(argv)

    if args.pool_runs:
        pool_out = args.pool_out or Path(args.pool_runs[0]).with_name(
            "ablation_bootstrap_three_run.md"
        )
        results = write_pooled_report(args.pool_runs, pool_out)
        for name in ("overall", "hop_2"):
            row = results[name]
            print(
                f"pooled {name} n={int(row['n'])} gap={row['gap_mean']:.3f} "
                f"[{row['gap_low']:.3f}, {row['gap_high']:.3f}]"
            )
    else:
        out = args.out
        if out is None:
            if args.judged.resolve() == DEFAULT_JUDGED.resolve():
                out = DEFAULT_OUT
            else:
                out = args.judged.with_name(f"{args.judged.stem}_bootstrap.md")

        results = write_report(args.judged, out)
        for name in ("overall", "hop_2"):
            row = results[name]
            print(
                f"{name} n={int(row['n'])} gap={row['gap_mean']:.3f} "
                f"[{row['gap_low']:.3f}, {row['gap_high']:.3f}]"
            )

    if args.mean_of_runs:
        summary = mean_of_runs(args.mean_of_runs)
        mean_out = args.mean_out or (
            Path(args.mean_of_runs[0]).with_name("three_run_means.md")
        )
        mean_out.write_text(render_mean_of_runs(summary), encoding="utf-8")
        mean_out.with_suffix(".json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"mean_of_runs hybrid={summary['hybrid_mean']:.3f} "
            f"vector={summary['vector_mean']:.3f} "
            f"gap={summary['gap_mean']:.3f} -> {mean_out}"
        )


if __name__ == "__main__":
    main()
