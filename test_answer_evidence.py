"""Free unit tests for answer evidence packing + refuse helpers (no API calls)."""

from __future__ import annotations

from answer import (
    EvidencePack,
    LabeledEvidenceItem,
    _fit_items_to_prompt_budget,
    _truncate_passage,
    allowed_chunk_ids_from_items,
    build_evidence_items,
    fact_to_statement,
    format_evidence,
    has_answerable_graph_evidence,
    looks_like_strict_quantitative_question,
)
from graph_retriever import GraphFact, GraphRetrievalResult, GraphTemplateId
from retrieve import HybridRetrievalResult
from router import RetrievalRoute, RouteDecision
from vector_retriever import VectorPassage, VectorRetrievalResult


def _route() -> RouteDecision:
    return RouteDecision(
        question="q",
        model_route=RetrievalRoute.GRAPH,
        effective_route=RetrievalRoute.GRAPH,
        confidence=1.0,
        rationale="test",
        low_confidence_fallback=False,
        model="test",
    )


def _fact(
    name: str,
    *,
    confidence: float,
    context: str = "",
    chunk: str = "c0",
) -> GraphFact:
    return GraphFact(
        source_id="APPLE",
        source_name="Apple Inc.",
        rel_type="PRODUCES_PRODUCT",
        target_id=name.upper().replace(" ", ""),
        target_name=name,
        source_chunk_ids=[chunk],
        context=context or None,
        confidence=confidence,
    )


def _graph_result(facts: list) -> GraphRetrievalResult:
    return GraphRetrievalResult(
        question="What products?",
        template_id=GraphTemplateId.COMPANY_PRODUCTS,
        plan_rationale="test",
        resolved_entities=[],
        entity_id_used="APPLE",
        facts=facts,
        cypher_ran=True,
    )


def test_truncate_passage():
    assert _truncate_passage("a b c", 100) == "a b c"
    assert _truncate_passage("abcdefghij", 8).endswith("...")
    assert len(_truncate_passage("abcdefghij", 8)) == 8


def test_build_evidence_items_caps_graph_by_confidence():
    facts = [_fact(f"P{i}", confidence=i / 10, chunk=f"c{i}") for i in range(20)]
    retrieval = HybridRetrievalResult(
        question="What products?",
        routing=_route(),
        graph=_graph_result(facts),
        vector=None,
    )
    items = build_evidence_items(retrieval, max_graph=5, max_vector=5)
    assert len(items) == 5
    assert all(i.source_label == "GRAPH" for i in items)
    assert items[0].statement.startswith("Apple Inc. produces product P19")


def test_allowed_ids_match_kept_items_not_full_retrieval():
    facts = [_fact(f"P{i}", confidence=i / 10, chunk=f"c{i}") for i in range(20)]
    retrieval = HybridRetrievalResult(
        question="What products?",
        routing=_route(),
        graph=_graph_result(facts),
        vector=None,
    )
    pack = format_evidence(retrieval)
    assert len(pack.items) <= 12
    assert set(pack.allowed_chunk_ids) == set(allowed_chunk_ids_from_items(pack.items))
    assert "c0" not in pack.allowed_chunk_ids


def test_vector_passages_truncated_and_capped():
    long_text = "word " * 500
    retrieval = HybridRetrievalResult(
        question="What is AppleCare?",
        routing=_route(),
        graph=None,
        vector=VectorRetrievalResult(
            question="What is AppleCare?",
            ticker="AAPL",
            k=8,
            model="test",
            passages=[
                VectorPassage(
                    chunk_id=f"v{i}",
                    text=long_text,
                    section="Item1",
                    score=1.0 - i * 0.1,
                )
                for i in range(8)
            ],
        ),
    )
    items = build_evidence_items(
        retrieval, max_graph=12, max_vector=3, max_vector_chars=100
    )
    assert len(items) == 3
    assert all(len(i.statement) <= 100 for i in items)


def test_prompt_budget_drops_tail_items():
    items = [
        LabeledEvidenceItem(
            source_label="GRAPH",
            statement="x" * 200,
            chunk_ids=[f"c{i}"],
        )
        for i in range(10)
    ]
    kept = _fit_items_to_prompt_budget("q", items, max_chars=800)
    assert len(kept) < len(items)
    assert len(kept) >= 1


def test_has_answerable_graph_evidence():
    empty = EvidencePack(question="q", items=[], allowed_chunk_ids=[])
    assert not has_answerable_graph_evidence(empty)
    with_graph = EvidencePack(
        question="q",
        items=[
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="Apple produces iPhone.",
                chunk_ids=["c1"],
            )
        ],
        allowed_chunk_ids=["c1"],
    )
    assert has_answerable_graph_evidence(with_graph)


def test_quantitative_oos_heuristic():
    assert looks_like_strict_quantitative_question(
        "How many Bitcoin does Apple hold on its balance sheet?"
    )
    assert looks_like_strict_quantitative_question(
        "What was Tim Cook's exact total compensation last year?"
    )
    assert looks_like_strict_quantitative_question(
        "What percentage of Walmart's revenue comes from Sam's Club?"
    )
    assert not looks_like_strict_quantitative_question(
        "What product lines does Apple produce?"
    )


def test_fact_context_truncated():
    fact = _fact("iPhone", confidence=1.0, context="y" * 500)
    stmt = fact_to_statement(fact, context_chars=40)
    assert "..." in stmt
    assert len(stmt) < 120
