"""Ranking helpers for the retrieve-only harness. No database or API."""

from __future__ import annotations

from graph_retriever import GraphFact
from retrieval_benchmark import graph_chunk_ids, hybrid_chunk_ids, score_retrieved


def _fact(rel: str, chunks: list[str], target: str, confidence: float = 0.5) -> GraphFact:
    return GraphFact(
        source_id="APPLE",
        source_name="Apple",
        rel_type=rel,
        target_id=target,
        target_name=target,
        source_chunk_ids=chunks,
        confidence=confidence,
    )


def test_graph_chunk_ids_follow_first_occurrence_after_rank():
    facts = [
        _fact("EXPOSED_TO_RISK", ["risk-chunk", "shared"], "RISK", confidence=0.2),
        _fact("PRODUCES_PRODUCT", ["shared", "phone-chunk"], "IPHONE", confidence=0.9),
    ]
    # Higher-confidence fact is ranked first. Chunk order inside a fact is unchanged.
    assert graph_chunk_ids(facts, "What product lines does Apple produce?") == [
        "shared",
        "phone-chunk",
        "risk-chunk",
    ]


def test_more_question_hits_outrank_higher_confidence():
    facts = [
        _fact("EXPOSED_TO_RISK", ["wrong"], "China supply", confidence=0.95),
        _fact("EXPOSED_TO_RISK", ["right"], "Ray-Ban Meta", confidence=0.4),
    ]
    assert graph_chunk_ids(facts, "What are Ray-Ban Meta glasses?")[0] == "right"


def test_hybrid_alternates_vector_then_graph_and_skips_duplicates():
    graph = [f"g{i}" for i in range(11)]
    vector = ["gold", "g0", "v2"]
    assert hybrid_chunk_ids(graph, vector)[:5] == ["gold", "g0", "v2", "g1", "g2"]
    assert hybrid_chunk_ids(["g1", "g2"], ["g2", "v1"]) == ["g2", "g1", "v1"]


def test_score_retrieved_rounds_miss():
    scores = score_retrieved(["other"], ["gold"])
    assert scores["recall_at_5"] == 0.0
    assert scores["recall_at_10"] == 0.0
    assert scores["mrr"] == 0.0
