"""
WP2: retrieve-only recall@5, recall@10, and MRR.

Systems:
  graph  — graph facts only, chunk ids in evidence-pack order
  vector — vector passages only, top 10 after the lexical rerank
  hybrid — same order the evidence pack uses: graph ids, then new vector ids

Does not call the answer model. Out-of-scope items are skipped (no gold chunks).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from answer import _rank_graph_facts_for_question, filter_unmatched_produces_facts
from benchmark import load_suite
from benchmark_schema import BenchmarkItem, BenchmarkSuite
from graph_retriever import retrieve_graph
from retrieval_metrics import mean, recall_at_k, reciprocal_rank, unique_in_order
from retrieve import retrieve
from vector_retriever import retrieve_vector

DEFAULT_SUITE = Path(__file__).resolve().parent / "benchmarks" / "multi_company_smoke.json"
DEFAULT_OUT = (
    Path(__file__).resolve().parent / "benchmarks" / "results" / "retrieval_v4.json"
)
VECTOR_K = 10
KS = (5, 10)
SYSTEMS = ("graph", "vector", "hybrid")


def graph_chunk_ids(facts: Sequence, question: str) -> List[str]:
    """Unique source chunk ids after the same fact ranking the answer pack uses."""
    ranked = filter_unmatched_produces_facts(list(facts), question)
    ranked = _rank_graph_facts_for_question(ranked, question)
    ids: List[str] = []
    for fact in ranked:
        ids.extend(str(chunk_id) for chunk_id in fact.source_chunk_ids if chunk_id)
    return unique_in_order(ids)


def vector_chunk_ids(passages: Sequence) -> List[str]:
    return unique_in_order(str(p.chunk_id) for p in passages if p.chunk_id)


def hybrid_chunk_ids(graph_ids: Sequence[str], vector_ids: Sequence[str]) -> List[str]:
    """Graph ids first, then vector ids that are not already in the graph list."""
    return unique_in_order([*graph_ids, *vector_ids])


def score_retrieved(retrieved: Sequence[str], gold: Sequence[str]) -> Dict[str, float]:
    scores = {f"recall_at_{k}": round(recall_at_k(retrieved, gold, k), 4) for k in KS}
    scores["mrr"] = round(reciprocal_rank(retrieved, gold), 4)
    return scores


def retrieve_ranked_ids(item: BenchmarkItem, system: str) -> List[str]:
    if system == "graph":
        result = retrieve_graph(item.question, ticker=item.ticker)
        return graph_chunk_ids(result.facts, item.question)
    if system == "vector":
        result = retrieve_vector(item.question, ticker=item.ticker, k=VECTOR_K)
        return vector_chunk_ids(result.passages)
    if system == "hybrid":
        result = retrieve(
            item.question,
            ticker=item.ticker,
            log_route=False,
            vector_k=VECTOR_K,
        )
        graph_ids = (
            graph_chunk_ids(result.graph.facts, item.question) if result.graph else []
        )
        vector_ids = vector_chunk_ids(result.vector.passages) if result.vector else []
        return hybrid_chunk_ids(graph_ids, vector_ids)
    raise ValueError(f"unknown system {system}")


def _bucket(item: BenchmarkItem) -> str:
    return f"hop_{int(item.hop)}"


def _aggregate(rows: List[dict]) -> Dict[str, dict]:
    buckets = ("hop_0", "hop_1", "hop_2", "overall")
    out: Dict[str, dict] = {}
    for bucket in buckets:
        chosen = rows if bucket == "overall" else [r for r in rows if r["hop"] == bucket]
        entry = {"n": len(chosen)}
        for key in ("recall_at_5", "recall_at_10", "mrr"):
            value = mean([r[key] for r in chosen])
            entry[key] = None if value is None else round(value, 4)
        out[bucket] = entry
    return out


def run_retrieval_eval(suite: BenchmarkSuite) -> dict:
    items = [item for item in suite.items if not item.must_refuse and item.gold_chunk_ids]
    systems: Dict[str, dict] = {}
    for system in SYSTEMS:
        rows: List[dict] = []
        for index, item in enumerate(items, start=1):
            print(f"[{system} {index}/{len(items)}] {item.id}", flush=True)
            try:
                retrieved = retrieve_ranked_ids(item, system)
                error = None
            except Exception as exc:  # noqa: BLE001 — one bad item should not drop the table
                retrieved = []
                error = f"{type(exc).__name__}: {exc}"
            row = {
                "id": item.id,
                "hop": _bucket(item),
                "ticker": item.ticker,
                "gold_chunk_ids": list(item.gold_chunk_ids),
                "retrieved_chunk_ids": retrieved,
                "error": error,
                **score_retrieved(retrieved, item.gold_chunk_ids),
            }
            rows.append(row)
        systems[system] = {"by_hop": _aggregate(rows), "items": rows}
    return {
        "suite": suite.name,
        "version": suite.version,
        "vector_k": VECTOR_K,
        "ks": list(KS),
        "n_scored": len(items),
        "n_oos_skipped": sum(1 for item in suite.items if item.must_refuse),
        "notes": (
            "Macro-average over answerable items with gold_chunk_ids. "
            "Rank is first occurrence of a chunk id. "
            "Hybrid list is graph ids, then vector ids not already present. "
            "Vector depth is 10 so recall@10 can differ from recall@5. "
            "The answer model still caps the pack (graph facts 12, vector passages 5); "
            "this table is retrieve-only and does not apply that cap. "
            "OOS items are skipped."
        ),
        "systems": systems,
    }


def render_markdown(report: dict) -> str:
    lines = [
        f"# Retrieval metrics — {report['suite']} v{report['version']}",
        "",
        report["notes"],
        "",
        f"Scored n={report['n_scored']}. OOS skipped={report['n_oos_skipped']}.",
        "",
        "| Hop | n | System | Recall@5 | Recall@10 | MRR |",
        "|-----|--:|--------|--------:|----------:|----:|",
    ]
    order = ("hop_0", "hop_1", "hop_2", "overall")
    for bucket in order:
        for system in SYSTEMS:
            stats = report["systems"][system]["by_hop"][bucket]
            lines.append(
                "| {bucket} | {n} | {system} | {r5} | {r10} | {mrr} |".format(
                    bucket=bucket,
                    n=stats["n"],
                    system=system,
                    r5=_fmt(stats["recall_at_5"]),
                    r10=_fmt(stats["recall_at_10"]),
                    mrr=_fmt(stats["mrr"]),
                )
            )
    lines.append("")
    return "\n".join(lines)


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Retrieve-only recall@k and MRR.")
    parser.add_argument("--suite", default=str(DEFAULT_SUITE))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required. Runs router, graph planner, and embedding calls for every answerable item.",
    )
    args = parser.parse_args(argv)
    if not args.confirm:
        print("Refusing to run paid/API retrieval without --confirm.")
        print("This scores graph, vector, and hybrid retrieve-only (no answer model).")
        return 2
    suite = load_suite(args.suite)
    report = run_retrieval_eval(suite)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path = out.with_suffix(".md")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    print(f"wrote {out}")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
