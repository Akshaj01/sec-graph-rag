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
    filter_unmatched_produces_facts,
    format_evidence,
    has_answerable_graph_evidence,
    looks_like_strict_quantitative_question,
    query_needles,
    truncate_passage_for_query,
)
from graph_retriever import GraphFact, GraphRetrievalResult, GraphTemplateId
from retrieve import HybridRetrievalResult, wants_produce_yes_no
from router import RetrievalRoute, RouteDecision
from vector_retriever import (
    VectorPassage,
    VectorRetrievalResult,
    lexical_boost_score,
    rerank_passages_lexical,
)


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


def test_query_needles_picks_product_names():
    needles = [n.lower() for n in query_needles("What is AppleCare?")]
    assert "applecare" in needles
    needles_az = [n.lower() for n in query_needles("What is Microsoft Azure according to the filing?")]
    assert "azure" in needles_az


def test_truncate_passage_for_query_centers_mid_chunk_needle():
    prefix = "x" * 1500
    text = prefix + " AppleCare is a service and support program. " + ("y" * 500)
    out = truncate_passage_for_query(text, "What is AppleCare?", 200)
    assert "AppleCare" in out
    assert len(out) <= 200


def test_truncate_prefers_question_needle_over_entity_ids():
    """Passage entity_ids include earlier products; window must still target the ask."""
    text = (
        ("iPhone is mentioned early. " * 40)
        + "AppleCare is a service and support program. "
        + ("trailer " * 40)
    )
    out = truncate_passage_for_query(
        text,
        "What is AppleCare?",
        160,
        entity_ids=["AAPL_IPHONE", "AAPL_APPLECARE", "AAPL_MAC"],
    )
    assert "AppleCare" in out
    # Must not fall back to a pure head window of only the iPhone boilerplate.
    assert not out.startswith("iPhone is mentioned early. iPhone is mentioned early.")


def test_build_evidence_items_keeps_mid_chunk_definition():
    prefix = "boilerplate " * 200
    text = prefix + "AppleCare provides extended service and support coverage for Apple products."
    retrieval = HybridRetrievalResult(
        question="What is AppleCare?",
        routing=_route(),
        graph=None,
        vector=VectorRetrievalResult(
            question="What is AppleCare?",
            ticker="AAPL",
            k=3,
            model="test",
            passages=[
                VectorPassage(
                    chunk_id="v0",
                    text=text,
                    section="Item1",
                    score=0.9,
                    entity_ids=["AAPL_APPLECARE"],
                )
            ],
        ),
    )
    items = build_evidence_items(
        retrieval, max_graph=12, max_vector=3, max_vector_chars=200
    )
    assert len(items) == 1
    assert "AppleCare" in items[0].statement


def test_lexical_rerank_promotes_entity_match():
    passages = [
        VectorPassage(
            chunk_id="boilerplate",
            text="Microsoft describes cloud computing in broad terms without naming the product.",
            section="Item1",
            score=0.95,
            entity_ids=["MSFT"],
        ),
        VectorPassage(
            chunk_id="azure_def",
            text="Azure is Microsoft's cloud computing platform.",
            section="Item1A",
            score=0.70,
            entity_ids=["MSFT_AZURE"],
        ),
    ]
    ranked = rerank_passages_lexical(
        passages, "What is Microsoft Azure according to the filing?", k=2
    )
    assert ranked[0].chunk_id == "azure_def"
    assert lexical_boost_score(
        text=passages[1].text,
        entity_ids=passages[1].entity_ids,
        needles=["Azure"],
        base_score=0.7,
    ) > 0.7


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


def test_wants_produce_yes_no():
    assert wants_produce_yes_no("Does Johnson & Johnson produce MedTech products?")
    assert wants_produce_yes_no("Do they manufacture medical devices?")
    assert not wants_produce_yes_no("What product lines does Apple produce?")


def test_filter_unmatched_produces_drops_drug_laundry_list():
    facts = [
        GraphFact(
            source_id="JOHNSONJOHNSON",
            source_name="Johnson & Johnson",
            rel_type="PRODUCES_PRODUCT",
            target_id="JNJ_DARZALEX",
            target_name="DARZALEX",
            source_chunk_ids=["c1"],
            confidence=0.9,
        ),
        GraphFact(
            source_id="JOHNSONJOHNSON",
            source_name="Johnson & Johnson",
            rel_type="PRODUCES_PRODUCT",
            target_id="JNJ_IMBRUVICA",
            target_name="IMBRUVICA",
            source_chunk_ids=["c2"],
            confidence=0.9,
        ),
    ]
    kept = filter_unmatched_produces_facts(
        facts, "Does Johnson & Johnson produce MedTech products?"
    )
    assert kept == []


def test_filter_unmatched_produces_keeps_matching_product():
    facts = [
        GraphFact(
            source_id="APPLE",
            source_name="Apple",
            rel_type="PRODUCES_PRODUCT",
            target_id="AAPL_IPHONE",
            target_name="iPhone",
            source_chunk_ids=["c1"],
            confidence=0.9,
        ),
        GraphFact(
            source_id="APPLE",
            source_name="Apple",
            rel_type="PRODUCES_PRODUCT",
            target_id="AAPL_MAC",
            target_name="Mac",
            source_chunk_ids=["c2"],
            confidence=0.9,
        ),
    ]
    kept = filter_unmatched_produces_facts(facts, "What product lines include iPhone?")
    assert [f.target_id for f in kept] == ["AAPL_IPHONE"]


def test_filter_unmatched_produces_keeps_open_ended_apps_list():
    """Generic 'apps' must not collapse the pack to only 'Family of Apps'."""
    facts = [
        GraphFact(
            source_id="META",
            source_name="Meta",
            rel_type="PRODUCES_PRODUCT",
            target_id="META_FACEBOOK",
            target_name="Facebook",
            source_chunk_ids=["c1"],
            confidence=0.9,
        ),
        GraphFact(
            source_id="META",
            source_name="Meta",
            rel_type="PRODUCES_PRODUCT",
            target_id="META_FAMILY",
            target_name="Family of Apps",
            source_chunk_ids=["c2"],
            confidence=0.9,
        ),
    ]
    kept = filter_unmatched_produces_facts(
        facts, "Which apps or product lines does Meta produce?"
    )
    assert {f.target_id for f in kept} == {"META_FACEBOOK", "META_FAMILY"}


def test_filter_unmatched_produces_drops_all_on_competition_ask():
    facts = [
        GraphFact(
            source_id="APPLE",
            source_name="Apple",
            rel_type="PRODUCES_PRODUCT",
            target_id="AAPL_IPHONE",
            target_name="iPhone",
            source_chunk_ids=["c1"],
            confidence=0.9,
        ),
        GraphFact(
            source_id="APPLE",
            source_name="Apple",
            rel_type="COMPETES_WITH",
            target_id="META",
            target_name="Meta",
            source_chunk_ids=["c2"],
            confidence=0.9,
        ),
    ]
    kept = filter_unmatched_produces_facts(
        facts, "Does Apple compete with Meta according to the knowledge graph?"
    )
    assert [f.rel_type for f in kept] == ["COMPETES_WITH"]
