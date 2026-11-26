"""
Export one suite question's recorded hybrid and vector-only answers for the web demo.

Reads the three temperature-0 benchmark runs and copies, per run, each system's
summary, route, citations, judge score, and required-fact hits / misses. Nothing
is re-run or edited: the fixture is a subset of the committed result files.

    python export_compare_fixture.py hop1_aapl_competes_meta \
        --out web/fixtures/compare-aapl-competes-meta.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent
SUITE = ROOT / "benchmarks" / "multi_company_smoke.json"
# The headline runs: pinned 10-Ks, judge rubric v2 (grounded in cited passages).
RUNS = [
    ROOT / "benchmarks" / "results" / "multi_company_smoke_temp0_p7.json",
    ROOT / "benchmarks" / "results" / "multi_company_smoke_temp0_p7_run2.json",
    ROOT / "benchmarks" / "results" / "multi_company_smoke_temp0_p7_run3.json",
]
KEEP = (
    "route_effective",
    "summary",
    "cited_chunk_ids",
    "citations_valid",
    "refused",
    "score",
    "judge_fact_hits",
    "judge_fact_misses",
    "judge_hallucination",
    "judge_rationale",
)


def _row(report: Dict[str, Any], mode: str, item_id: str) -> Dict[str, Any]:
    for row in report[mode]["results"]:
        if row["item_id"] == item_id:
            return {key: row[key] for key in KEEP}
    raise KeyError(f"{item_id} not in {mode} results")


def build(item_id: str) -> Dict[str, Any]:
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    item = next((i for i in suite["items"] if i["id"] == item_id), None)
    if item is None:
        raise SystemExit(f"{item_id} is not in {SUITE.name}")

    runs: List[Dict[str, Any]] = []
    for path in RUNS:
        report = json.loads(path.read_text(encoding="utf-8"))
        runs.append(
            {
                "file": f"benchmarks/results/{path.name}",
                "hybrid": _row(report, "hybrid", item_id),
                "vector_only": _row(report, "vector_only", item_id),
            }
        )

    return {
        "item_id": item_id,
        "suite": f"{suite['name']} v{suite['version']}",
        "hop": item["hop"],
        "ticker": item["ticker"],
        "question": item["question"],
        "required_facts": item["required_facts"],
        "runs": runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("item_id")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    fixture = build(args.item_id)
    args.out.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
