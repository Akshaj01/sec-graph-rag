"""
Phase 5 Step R: Run labeled suite under hybrid vs vector-only.

Scoring:
  - must_refuse: score=1 if draft.refused else 0
  - else: case-insensitive gold_keyword recall over summary+claims
    (refused non-OOS => score 0)

Cost: rough USD from chars≈tokens and .env rates (not a billing invoice).
Full suite is paid — use --limit / --ids for smoke; --confirm for all items.

Out of scope: README table (Step S), FastAPI (Step T).
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

from answer import AnswerResult, answer_question
from benchmark import DEFAULT_SUITE_PATH, load_suite
from benchmark_schema import (
    BenchmarkComparison,
    BenchmarkItem,
    BenchmarkItemResult,
    BenchmarkMode,
    BenchmarkReport,
    BenchmarkSuite,
)
from config import settings
from router import RetrievalRoute

RESULTS_DIR = Path(__file__).resolve().parent / "benchmarks" / "results"


def _answer_text(result: AnswerResult) -> str:
    parts = [result.draft.summary]
    for claim in result.draft.claims:
        parts.append(claim.text)
    return "\n".join(parts)


def score_keywords(text: str, gold_keywords: Sequence[str]) -> tuple[List[str], List[str], float]:
    lowered = text.lower()
    hits: List[str] = []
    misses: List[str] = []
    for kw in gold_keywords:
        if kw.lower() in lowered:
            hits.append(kw)
        else:
            misses.append(kw)
    recall = (len(hits) / len(gold_keywords)) if gold_keywords else 1.0
    return hits, misses, recall


def score_item(item: BenchmarkItem, answer: AnswerResult) -> tuple[float, Optional[bool], List[str], List[str], Optional[float]]:
    """
    Returns (score, correct_refuse, hits, misses, keyword_recall).
    """
    if item.must_refuse:
        correct = bool(answer.draft.refused)
        return (1.0 if correct else 0.0), correct, [], [], None

    hits, misses, recall = score_keywords(_answer_text(answer), item.gold_keywords)
    if answer.draft.refused:
        return 0.0, None, hits, misses, recall
    if not item.gold_keywords:
        # No needles: require valid citations and a non-empty summary.
        ok = 1.0 if answer.citations_valid and answer.draft.summary.strip() else 0.0
        return ok, None, hits, misses, recall
    return recall, None, hits, misses, recall


def estimate_cost_usd(
    mode: BenchmarkMode,
    answer: AnswerResult,
) -> float:
    """Order-of-magnitude USD; not provider-accurate."""
    prompt_chars = len(answer.evidence.prompt_text) + 800
    in_tok = max(1, prompt_chars // settings.CHARS_PER_TOKEN)
    out_tok = max(64, (len(answer.draft.summary) + sum(len(c.text) for c in answer.draft.claims)) // settings.CHARS_PER_TOKEN)
    out_tok *= max(1, answer.attempts)

    sonnet_in = settings.EXTRACTION_INPUT_COST_PER_MTOK / 1_000_000
    sonnet_out = settings.EXTRACTION_OUTPUT_COST_PER_MTOK / 1_000_000
    haiku_in = settings.HAIKU_INPUT_COST_PER_MTOK / 1_000_000
    haiku_out = settings.HAIKU_OUTPUT_COST_PER_MTOK / 1_000_000
    emb = settings.EMBEDDING_COST_PER_MTOK / 1_000_000

    cost = in_tok * sonnet_in + out_tok * sonnet_out

    # Query embedding when vector path ran.
    if answer.retrieval.vector is not None:
        q_tok = max(1, len(answer.question) // settings.CHARS_PER_TOKEN)
        cost += q_tok * emb

    if mode == BenchmarkMode.HYBRID:
        # Router always; graph plan when graph/both.
        cost += 200 * haiku_in + 80 * haiku_out
        route = answer.retrieval.routing.effective_route
        if route in (RetrievalRoute.GRAPH, RetrievalRoute.BOTH):
            cost += 250 * haiku_in + 100 * haiku_out

    return round(cost, 6)


def run_one(
    item: BenchmarkItem,
    mode: BenchmarkMode,
) -> BenchmarkItemResult:
    force = RetrievalRoute.VECTOR if mode == BenchmarkMode.VECTOR_ONLY else None
    t0 = time.perf_counter()
    try:
        answer = answer_question(
            item.question,
            ticker=item.ticker,
            log_route=(mode == BenchmarkMode.HYBRID),
            force_route=force,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        score, correct_refuse, hits, misses, kw_recall = score_item(item, answer)
        cited: List[str] = []
        for claim in answer.draft.claims:
            cited.extend(claim.citation_chunk_ids)
        return BenchmarkItemResult(
            item_id=item.id,
            mode=mode,
            question=item.question,
            hop=item.hop,
            must_refuse=item.must_refuse,
            refused=answer.draft.refused,
            citations_valid=answer.citations_valid,
            regenerated=answer.regenerated,
            summary=answer.draft.summary,
            claim_count=len(answer.draft.claims),
            cited_chunk_ids=sorted(set(cited)),
            route_effective=answer.retrieval.routing.effective_route.value,
            keyword_hits=hits,
            keyword_misses=misses,
            keyword_recall=kw_recall,
            correct_refuse=correct_refuse,
            latency_ms=round(latency_ms, 1),
            estimated_cost_usd=estimate_cost_usd(mode, answer),
            score=score,
        )
    except Exception as exc:  # noqa: BLE001 — keep suite running
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return BenchmarkItemResult(
            item_id=item.id,
            mode=mode,
            question=item.question,
            hop=item.hop,
            must_refuse=item.must_refuse,
            latency_ms=round(latency_ms, 1),
            error=f"{type(exc).__name__}: {exc}",
            score=0.0,
        )


def aggregate_report(
    suite: BenchmarkSuite,
    mode: BenchmarkMode,
    results: List[BenchmarkItemResult],
) -> BenchmarkReport:
    by_bucket: dict[str, List[float]] = {
        "hop_0": [],
        "hop_1": [],
        "hop_2": [],
        "oos": [],
    }
    for r in results:
        if r.score is None:
            continue
        if r.must_refuse:
            by_bucket["oos"].append(r.score)
        else:
            by_bucket[f"hop_{int(r.hop)}"].append(r.score)

    accuracy = {}
    for k, v in by_bucket.items():
        if not v:
            accuracy[k] = None
        else:
            accuracy[k] = round(sum(v) / len(v), 4)

    latencies = [r.latency_ms for r in results if r.latency_ms is not None]
    costs = [r.estimated_cost_usd for r in results if r.estimated_cost_usd is not None]
    scores = [r.score for r in results if r.score is not None]

    return BenchmarkReport(
        suite_name=suite.name,
        suite_version=suite.version,
        mode=mode,
        results=results,
        accuracy_by_hop=accuracy,
        mean_latency_ms=round(sum(latencies) / len(latencies), 1) if latencies else None,
        mean_cost_usd=round(sum(costs) / len(costs), 6) if costs else None,
        mean_score=round(sum(scores) / len(scores), 4) if scores else None,
        notes="score=keyword_recall (or refuse accuracy for OOS); null hop = no items run",
    )


def filter_items(
    suite: BenchmarkSuite,
    *,
    ids: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> List[BenchmarkItem]:
    items = list(suite.items)
    if ids:
        want = set(ids)
        items = [i for i in items if i.id in want]
    if limit is not None:
        items = items[: max(0, limit)]
    return items


def estimate_suite_cost_usd(n_items: int, modes: Sequence[BenchmarkMode]) -> float:
    """Very rough preflight: ~$0.04–0.08 per answered item depending on evidence size."""
    per = 0.05
    return round(n_items * len(list(modes)) * per, 2)


def run_suite(
    suite: BenchmarkSuite,
    items: Sequence[BenchmarkItem],
    modes: Sequence[BenchmarkMode],
) -> BenchmarkComparison:
    hybrid_results: List[BenchmarkItemResult] = []
    vector_results: List[BenchmarkItemResult] = []

    for mode in modes:
        print(f"\n=== mode={mode.value} items={len(items)} ===")
        bucket = hybrid_results if mode == BenchmarkMode.HYBRID else vector_results
        for i, item in enumerate(items, start=1):
            print(f"[{i}/{len(items)}] {mode.value} {item.id} ...", flush=True)
            row = run_one(item, mode)
            bucket.append(row)
            status = f"score={row.score}" if row.error is None else f"ERROR {row.error}"
            print(
                f"  -> {status} latency_ms={row.latency_ms} "
                f"refuse={row.refused} route={row.route_effective}",
                flush=True,
            )

    hybrid_report = aggregate_report(
        suite,
        BenchmarkMode.HYBRID,
        hybrid_results
        if BenchmarkMode.HYBRID in modes
        else [],
    )
    vector_report = aggregate_report(
        suite,
        BenchmarkMode.VECTOR_ONLY,
        vector_results
        if BenchmarkMode.VECTOR_ONLY in modes
        else [],
    )
    return BenchmarkComparison(
        suite_name=suite.name,
        suite_version=suite.version,
        hybrid=hybrid_report,
        vector_only=vector_report,
        notes="Step R comparison; paste accuracy_by_hop into README in Step S.",
    )


def _print_summary(comp: BenchmarkComparison) -> None:
    print("\n======== SUMMARY ========")
    for label, report in (("hybrid", comp.hybrid), ("vector_only", comp.vector_only)):
        if not report.results:
            continue
        print(f"\n{label}:")
        print(f"  mean_score={report.mean_score}")
        print(f"  accuracy_by_hop={json.dumps(report.accuracy_by_hop)}")
        print(f"  mean_latency_ms={report.mean_latency_ms}")
        print(f"  mean_cost_usd={report.mean_cost_usd}")
        total_cost = sum(r.estimated_cost_usd or 0.0 for r in report.results)
        print(f"  est_total_cost_usd={round(total_cost, 4)}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 5 Step R benchmark runner")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE_PATH)
    parser.add_argument("--limit", type=int, default=None, help="Only first N items")
    parser.add_argument(
        "--ids",
        type=str,
        default=None,
        help="Comma-separated item ids",
    )
    parser.add_argument(
        "--modes",
        type=str,
        default="hybrid,vector_only",
        help="Comma-separated: hybrid,vector_only",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required when running more than 4 item×mode calls (paid)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write JSON report path (default under benchmarks/results/)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    suite = load_suite(args.suite)
    ids = [x.strip() for x in args.ids.split(",") if x.strip()] if args.ids else None
    items = filter_items(suite, ids=ids, limit=args.limit)
    if not items:
        print("No items selected.")
        return 1

    modes: List[BenchmarkMode] = []
    for m in args.modes.split(","):
        m = m.strip()
        if not m:
            continue
        modes.append(BenchmarkMode(m))

    n_calls = len(items) * len(modes)
    est = estimate_suite_cost_usd(len(items), modes)
    print(
        f"Selected {len(items)} items × {len(modes)} modes = {n_calls} calls "
        f"(rough est ${est})."
    )
    if n_calls > 4 and not args.confirm:
        print(
            "Refusing to run: more than 4 paid calls without --confirm. "
            "Try --limit 2 or --ids hop1_products,hop0_applecare first."
        )
        return 2

    comp = run_suite(suite, items, modes)
    _print_summary(comp)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = args.out or (RESULTS_DIR / f"{suite.name}_{stamp}.json")
    out_path.write_text(comp.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
