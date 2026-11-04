"""
CI gate for hybrid recall@10.

Compares a saved retrieval report to a pinned baseline. No database, no
model calls. The check fails when recall@10 on the fixed item list drops
by more than 0.02 (two points).

    python recall_gate.py
    python recall_gate.py --degrade-first
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

DEFAULT_RESULTS = (
    Path(__file__).resolve().parent / "benchmarks" / "results" / "retrieval_v4.json"
)
DEFAULT_BASELINE = (
    Path(__file__).resolve().parent / "benchmarks" / "fixtures" / "recall_baseline.json"
)
SYSTEM = "hybrid"
METRIC = "recall_at_10"
MAX_DROP = 0.02


def macro_recall(report: dict, system: str = SYSTEM) -> tuple[float, list[str]]:
    items = report["systems"][system]["items"]
    if not items:
        raise ValueError(f"{system} report has no items")
    scores = [float(item[METRIC]) for item in items]
    return sum(scores) / len(scores), [item["id"] for item in items]


def build_baseline(report: dict, *, max_drop: float = MAX_DROP) -> dict:
    score, item_ids = macro_recall(report)
    return {
        "suite": report.get("suite"),
        "version": report.get("version"),
        "system": SYSTEM,
        "metric": METRIC,
        "max_drop": max_drop,
        "n": len(item_ids),
        "item_ids": item_ids,
        "recall_at_10": score,
    }


def degrade_first(report: dict, system: str = SYSTEM) -> dict:
    """Zero the first positive recall@10. One hit out of 32 is a 3.1 point drop."""
    degraded = copy.deepcopy(report)
    items = degraded["systems"][system]["items"]
    for item in items:
        if float(item[METRIC]) > 0.0:
            item[METRIC] = 0.0
            return degraded
    raise ValueError(f"no positive {METRIC} to degrade")


def evaluate(report: dict, baseline: dict) -> dict:
    score, item_ids = macro_recall(report, baseline.get("system", SYSTEM))
    expected_ids = list(baseline["item_ids"])
    pinned = float(baseline["recall_at_10"])
    max_drop = float(baseline.get("max_drop", MAX_DROP))
    if item_ids != expected_ids:
        return {
            "ok": False,
            "recall_at_10": score,
            "baseline": pinned,
            "drop": None,
            "max_drop": max_drop,
            "message": "item list changed; the gate only scores the pinned v4 ids",
        }
    drop = pinned - score
    # A drop of exactly two points passes. The epsilon absorbs binary float noise.
    ok = drop <= max_drop + 1e-9
    message = (
        f"hybrid recall@10 {score:.4f} vs baseline {pinned:.4f} "
        f"(drop {drop:.4f}, max {max_drop:.2f})"
    )
    return {
        "ok": ok,
        "recall_at_10": score,
        "baseline": pinned,
        "drop": drop,
        "max_drop": max_drop,
        "message": message,
    }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fail if hybrid recall@10 drops more than 0.02.")
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument(
        "--degrade-first",
        action="store_true",
        help="Zero one saved hit before scoring. This path is the deliberate red run.",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Overwrite the pinned baseline from --results. Not used in CI.",
    )
    args = parser.parse_args(argv)
    report = load_json(Path(args.results))
    if args.write_baseline:
        payload = build_baseline(report)
        path = Path(args.baseline)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path} recall@10={payload['recall_at_10']:.4f} n={payload['n']}")
        return 0
    if args.degrade_first:
        report = degrade_first(report)
    result = evaluate(report, load_json(Path(args.baseline)))
    print(result["message"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
