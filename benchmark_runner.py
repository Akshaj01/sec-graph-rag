"""
Phase 5 Step R: Run labeled suite under hybrid vs vector-only.

Scoring (primary = judge):
  - must_refuse: score=1 if draft.refused else 0
  - else: LLM-as-judge correctness vs required_facts / gold_answer
    (refused non-OOS => score 0)
  - keyword recall kept as a secondary field on each result

Also supports --rejudge PATH to re-score saved answers without re-answering.

Cost: rough USD from chars≈tokens and .env rates (not a billing invoice).
Full answer suite is paid — use --limit / --ids for smoke; --confirm for all items.
Rejudge is cheap Haiku calls (~one per answered item).
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional, Sequence

from answer import AnswerResult, answer_question
from benchmark import DEFAULT_SUITE_PATH, load_suite
from benchmark_judge import apply_verdict_to_fields, judge_answer
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


class ScoreMode(str, Enum):
    JUDGE = "judge"
    KEYWORD = "keyword"
    BOTH = "both"  # judge primary; still fill keyword_* fields


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


def score_item_keyword(
    item: BenchmarkItem,
    answer_text: str,
    *,
    refused: bool,
) -> tuple[float, List[str], List[str], Optional[float]]:
    """Legacy keyword recall. Returns (score, hits, misses, keyword_recall)."""
    hits, misses, recall = score_keywords(answer_text, item.gold_keywords)
    if refused:
        return 0.0, hits, misses, recall
    if not item.gold_keywords:
        ok = 1.0 if answer_text.strip() else 0.0
        return ok, hits, misses, recall
    return recall, hits, misses, recall


def _score_answer_fields(
    item: BenchmarkItem,
    *,
    answer_text: str,
    refused: bool,
    citations_valid: bool,
    score_mode: ScoreMode,
) -> dict:
    """
    Returns scoring kwargs for BenchmarkItemResult.
    OOS refuse is binary; non-OOS uses judge (primary) and/or keywords.
    """
    if item.must_refuse:
        correct = bool(refused)
        return {
            "score": 1.0 if correct else 0.0,
            "correct_refuse": correct,
            "keyword_hits": [],
            "keyword_misses": [],
            "keyword_recall": None,
            "judge_correctness": None,
            "judge_fact_hits": [],
            "judge_fact_misses": [],
            "judge_hallucination": None,
            "judge_rationale": "",
        }

    kw_score, hits, misses, recall = score_item_keyword(
        item, answer_text, refused=refused
    )

    out: dict = {
        "keyword_hits": hits,
        "keyword_misses": misses,
        "keyword_recall": recall,
        "correct_refuse": None,
        "judge_correctness": None,
        "judge_fact_hits": [],
        "judge_fact_misses": [],
        "judge_hallucination": None,
        "judge_rationale": "",
        "score": kw_score,
    }

    if score_mode == ScoreMode.KEYWORD:
        # Prefer citations+nonempty when no gold keywords (old behavior).
        if not item.gold_keywords and not refused:
            out["score"] = (
                1.0 if citations_valid and answer_text.strip() else 0.0
            )
        return out

    # Judge path (JUDGE or BOTH)
    if refused:
        out["judge_correctness"] = 0.0
        out["judge_rationale"] = "Non-OOS item refused; scored 0."
        out["score"] = 0.0
        return out

    if not item.required_facts and not item.gold_answer.strip():
        # Fall back to keywords if gold not authored yet.
        out["judge_rationale"] = "No required_facts/gold_answer; using keyword recall."
        out["judge_correctness"] = kw_score
        out["score"] = kw_score
        return out

    verdict = judge_answer(item, answer_text, refused=False)
    out.update(apply_verdict_to_fields(verdict))
    return out


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
    *,
    score_mode: ScoreMode = ScoreMode.JUDGE,
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
        cited: List[str] = []
        for claim in answer.draft.claims:
            cited.extend(claim.citation_chunk_ids)
        scoring = _score_answer_fields(
            item,
            answer_text=_answer_text(answer),
            refused=answer.draft.refused,
            citations_valid=answer.citations_valid,
            score_mode=score_mode,
        )
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
            latency_ms=round(latency_ms, 1),
            estimated_cost_usd=estimate_cost_usd(mode, answer),
            **scoring,
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
        if v:
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
        notes=(
            "score=LLM-judge correctness vs required_facts "
            "(or refuse accuracy for OOS); keyword_recall is secondary; "
            "null hop = no items run"
        ),
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
    *,
    score_mode: ScoreMode = ScoreMode.JUDGE,
) -> BenchmarkComparison:
    hybrid_results: List[BenchmarkItemResult] = []
    vector_results: List[BenchmarkItemResult] = []

    for mode in modes:
        print(f"\n=== mode={mode.value} items={len(items)} score_mode={score_mode.value} ===")
        bucket = hybrid_results if mode == BenchmarkMode.HYBRID else vector_results
        for i, item in enumerate(items, start=1):
            print(f"[{i}/{len(items)}] {mode.value} {item.id} ...", flush=True)
            row = run_one(item, mode, score_mode=score_mode)
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
        notes=(
            f"score_mode={score_mode.value}; primary score is LLM-judge "
            "correctness vs required_facts (keyword_recall secondary)."
        ),
    )


def _result_answer_text(row: BenchmarkItemResult) -> str:
    return (row.summary or "").strip()


def rejudge_comparison(
    suite: BenchmarkSuite,
    comp: BenchmarkComparison,
    *,
    score_mode: ScoreMode = ScoreMode.JUDGE,
) -> BenchmarkComparison:
    """Re-score saved answers with the current suite gold + judge (no answer calls)."""
    items_by_id = {i.id: i for i in suite.items}

    def _rejudge_report(report: BenchmarkReport) -> BenchmarkReport:
        new_rows: List[BenchmarkItemResult] = []
        for i, row in enumerate(report.results, start=1):
            item = items_by_id.get(row.item_id)
            if item is None:
                print(f"  skip unknown item_id={row.item_id}", flush=True)
                new_rows.append(row)
                continue
            if row.error:
                new_rows.append(row)
                continue
            print(
                f"[{i}/{len(report.results)}] rejudge {report.mode.value} {row.item_id} ...",
                flush=True,
            )
            scoring = _score_answer_fields(
                item,
                answer_text=_result_answer_text(row),
                refused=row.refused,
                citations_valid=row.citations_valid,
                score_mode=score_mode,
            )
            data = row.model_dump()
            data.update(scoring)
            new_row = BenchmarkItemResult.model_validate(data)
            new_rows.append(new_row)
            print(
                f"  -> score={new_row.score} judge={new_row.judge_correctness} "
                f"kw={new_row.keyword_recall}",
                flush=True,
            )
        return aggregate_report(suite, report.mode, new_rows)

    return BenchmarkComparison(
        suite_name=suite.name,
        suite_version=suite.version,
        hybrid=_rejudge_report(comp.hybrid) if comp.hybrid.results else comp.hybrid,
        vector_only=(
            _rejudge_report(comp.vector_only) if comp.vector_only.results else comp.vector_only
        ),
        notes=(
            f"Rejudged with suite v{suite.version}, score_mode={score_mode.value}. "
            "Answers unchanged; scores refreshed via LLM judge."
        ),
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
        "--score-mode",
        type=str,
        default=ScoreMode.JUDGE.value,
        choices=[m.value for m in ScoreMode],
        help="Primary scoring: judge (default), keyword, or both (judge primary)",
    )
    parser.add_argument(
        "--rejudge",
        type=Path,
        default=None,
        help="Re-score an existing comparison JSON (no answer calls; Haiku judge only)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required when running more than 4 paid answer or judge calls",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write JSON report path (default under benchmarks/results/)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    suite = load_suite(args.suite)
    score_mode = ScoreMode(args.score_mode)

    if args.rejudge is not None:
        raw = json.loads(args.rejudge.read_text(encoding="utf-8"))
        comp_in = BenchmarkComparison.model_validate(raw)
        n_judge = sum(
            1
            for report in (comp_in.hybrid, comp_in.vector_only)
            for r in report.results
            if not r.error and not r.must_refuse and not r.refused
        )
        # OOS + refused still need scoring but are free (no LLM).
        print(
            f"Rejudge {args.rejudge} with suite v{suite.version} "
            f"score_mode={score_mode.value} (~{n_judge} Haiku judge calls, ~${round(n_judge * 0.003, 3)})."
        )
        if n_judge > 4 and not args.confirm:
            print("Refusing: more than 4 judge calls without --confirm.")
            return 2
        comp = rejudge_comparison(suite, comp_in, score_mode=score_mode)
        _print_summary(comp)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = args.out or (RESULTS_DIR / f"{suite.name}_judged_{stamp}.json")
        out_path.write_text(comp.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nWrote {out_path}")
        return 0

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
        f"Selected {len(items)} items × {len(modes)} modes = {n_calls} answer calls "
        f"(rough est ${est}); score_mode={score_mode.value}."
    )
    if n_calls > 4 and not args.confirm:
        print(
            "Refusing to run: more than 4 paid calls without --confirm. "
            "Try --limit 2 or --ids hop1_aapl_products,hop0_aapl_applecare first."
        )
        return 2

    comp = run_suite(suite, items, modes, score_mode=score_mode)
    _print_summary(comp)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = args.out or (RESULTS_DIR / f"{suite.name}_{stamp}.json")
    out_path.write_text(comp.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
