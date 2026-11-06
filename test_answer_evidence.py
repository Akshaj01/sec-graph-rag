"""Free unit tests for answer evidence packing + refuse helpers (no API calls)."""

from __future__ import annotations

from answer import (
    AnswerClaim,
    EvidencePack,
    GroundedAnswerDraft,
    LabeledEvidenceItem,
    _fit_items_to_prompt_budget,
    _truncate_passage,
    allowed_chunk_ids_from_items,
    build_evidence_items,
    evidence_addresses_question,
    fact_to_statement,
    filter_unmatched_produces_facts,
    format_evidence,
    has_answerable_graph_evidence,
    looks_like_false_premise_for_others,
    looks_like_strict_quantitative_question,
    normalize_refused_draft,
    query_needles,
    topic_needles,
    truncate_passage_for_query,
    validate_citations,
)
from graph_retriever import GraphFact, GraphRetrievalResult, GraphTemplateId
from retrieve import HybridRetrievalResult, wants_produce_yes_no
from router import RetrievalRoute, RouteDecision
from vector_retriever import (
    VectorPassage,
    VectorRetrievalResult,
    competition_cooccurrence_boost,
    lexical_boost_score,
    lexical_needles,
    over_fetch_k,
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


def test_query_needles_keeps_short_ai_acronym():
    q = (
        "What major competitors or competitive pressures does Meta describe "
        "around AI and its core products?"
    )
    assert "ai" in [n.lower() for n in query_needles(q)]


def test_truncate_competition_ask_centers_on_named_rival():
    """Early 'products' summary must not hide TikTok mid-chunk."""
    q = (
        "What major competitors or competitive pressures does Meta describe "
        "around AI and its core products?"
    )
    early = (
        "Summary Risk Factors include risks related to our Product Offerings "
        "and our ability to compete effectively around core products. "
    )
    mid = "x " * 800
    rival = (
        "We face significant competition for users and advertisers, including "
        "from platforms such as TikTok, and from other companies developing AI "
        "features."
    )
    text = early + mid + rival + (" y" * 200)
    out = truncate_passage_for_query(text, q, 1200)
    assert "TikTok" in out
    assert "Summary Risk Factors" not in out


def test_truncate_glasses_ask_centers_on_ray_ban_not_early_ai_glasses():
    q = "What AI glasses or Reality Labs hardware products does Meta describe?"
    early = (
        "Our products enable people to connect through VR headsets and AI glasses. "
    )
    mid = "x " * 900
    brands = (
        "We offer Ray-Ban Meta AI glasses and Oakley Meta glasses, alongside "
        "Meta Quest headsets from Reality Labs."
    )
    text = early + mid + brands + (" y" * 200)
    out = truncate_passage_for_query(text, q, 1200)
    assert "Ray-Ban" in out
    assert "Oakley" in out or "Quest" in out
    assert not out.startswith("Our products enable people")


def test_lexical_needles_keeps_short_ai_acronym():
    """AI is the topic for Meta competition asks; len<3 used to drop it entirely."""
    q = (
        "What major competitors or competitive pressures does Meta describe "
        "around AI and its core products?"
    )
    needles = [n.lower() for n in lexical_needles(q)]
    assert "ai" in needles
    assert "competitors" in needles
    # Ordinary 2-letter stop-ish tokens still stay out.
    assert "to" not in needles
    assert "in" not in needles


def test_over_fetch_k_reaches_dense_rank_20():
    assert over_fetch_k(5) == 25
    assert over_fetch_k(10) == 30
    assert over_fetch_k(20) == 40


def test_competition_boost_promotes_named_rival_over_generic_ai():
    q = (
        "What major competitors or competitive pressures does Meta describe "
        "around AI and its core products?"
    )
    generic = (
        "The company faces regulatory scrutiny around AI from the FTC and Congress."
    )
    named = (
        "Meta faces significant competition for users and advertisers, including "
        "from platforms such as TikTok, and from other companies developing AI "
        "features and technologies."
    )
    assert competition_cooccurrence_boost(q, named) == 0.30
    assert competition_cooccurrence_boost(q, generic) == 0.0
    # Non-competition asks must not pick up the named-rival bonus.
    assert competition_cooccurrence_boost("What is AppleCare?", named) == 0.0

    passages = [
        VectorPassage(
            chunk_id="generic_ai_reg",
            text=generic,
            section="Item1A",
            score=0.52,
            entity_ids=[],
        ),
        VectorPassage(
            chunk_id="tiktok_competition",
            text=named,
            section="Item1A",
            score=0.37,
            entity_ids=[],
        ),
    ]
    ranked = rerank_passages_lexical(passages, q, k=2)
    assert ranked[0].chunk_id == "tiktok_competition"


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


def test_evidence_pack_alternates_vector_then_graph():
    retrieval = HybridRetrievalResult(
        question="What products?",
        routing=_route(),
        graph=_graph_result(
            [
                _fact("Phone", confidence=0.9, chunk="g1"),
                _fact("Watch", confidence=0.8, chunk="v1"),
            ]
        ),
        vector=VectorRetrievalResult(
            question="What products?",
            ticker="AAPL",
            k=2,
            model="test",
            passages=[
                VectorPassage(chunk_id="v1", text="phones", section="Item1", score=0.9),
                VectorPassage(chunk_id="v2", text="watches", section="Item1", score=0.8),
            ],
        ),
    )
    items = build_evidence_items(retrieval, max_graph=12, max_vector=5)
    assert [item.chunk_ids[0] for item in items] == ["v1", "g1", "v2"]
    assert [item.source_label for item in items] == ["VECTOR", "GRAPH", "VECTOR"]


def test_evidence_pack_keeps_question_hit_order_over_confidence():
    retrieval = HybridRetrievalResult(
        question="What are Ray-Ban Meta glasses?",
        routing=_route(),
        graph=_graph_result(
            [
                GraphFact(
                    source_id="APPLE",
                    source_name="Apple Inc.",
                    rel_type="EXPOSED_TO_RISK",
                    target_id="CHINA",
                    target_name="China supply",
                    source_chunk_ids=["wrong"],
                    confidence=0.95,
                ),
                GraphFact(
                    source_id="APPLE",
                    source_name="Apple Inc.",
                    rel_type="EXPOSED_TO_RISK",
                    target_id="RAYBAN",
                    target_name="Ray-Ban Meta",
                    source_chunk_ids=["right"],
                    confidence=0.4,
                ),
            ]
        ),
        vector=None,
    )
    items = build_evidence_items(retrieval, max_graph=5, max_vector=5)
    assert [item.chunk_ids[0] for item in items] == ["right", "wrong"]


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
    from retrieve import wants_graph_plus_vector_narrative

    assert wants_produce_yes_no("Does Johnson & Johnson produce MedTech products?")
    assert wants_produce_yes_no("Do they manufacture medical devices?")
    assert not wants_produce_yes_no("What product lines does Apple produce?")
    assert wants_graph_plus_vector_narrative(
        "How is NVIDIA involved in the automotive space?"
    )
    assert wants_graph_plus_vector_narrative(
        "What AI glasses or Reality Labs hardware products does Meta describe?"
    )
    assert not wants_graph_plus_vector_narrative(
        "What product lines does Apple produce?"
    )


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


def test_evidence_addresses_rejects_off_topic_graph_laundry_list():
    pack = EvidencePack(
        question="What battery supply risks does Apple face in its latest 10-K?",
        items=[
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="Apple Inc. produces product AppleCare. Context: advertising partners.",
                chunk_ids=["c1"],
            )
        ],
        allowed_chunk_ids=["c1"],
    )
    assert "battery" in [t.lower() for t in topic_needles(pack.question)]
    # Neither battery nor supply appear — off-topic laundry list.
    assert not evidence_addresses_question(pack)


def test_false_premise_for_others_rejects_own_product_graph():
    q = "How is Netflix producing AI Compute for other companies in the corpus?"
    assert looks_like_false_premise_for_others(q)
    pack = EvidencePack(
        question=q,
        items=[
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement=(
                    "Netflix produces product streaming service. "
                    "Context: entertainment video for its members."
                ),
                chunk_ids=["c1"],
            ),
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="Netflix produces product content delivery network.",
                chunk_ids=["c2"],
            ),
        ],
        allowed_chunk_ids=["c1", "c2"],
    )
    assert not evidence_addresses_question(pack)


def test_false_premise_for_others_accepts_external_compute_claim():
    q = "How is Netflix producing AI Compute for other companies in the corpus?"
    pack = EvidencePack(
        question=q,
        items=[
            LabeledEvidenceItem(
                source_label="VECTOR",
                statement=(
                    "Netflix sells AI compute capacity to other companies as a service."
                ),
                chunk_ids=["c9"],
            )
        ],
        allowed_chunk_ids=["c9"],
    )
    assert evidence_addresses_question(pack)


def test_evidence_addresses_any_topic_hit_enough_for_multi_aspect():
    pack = EvidencePack(
        question="What compute products does NVIDIA produce, and what geopolitical risks is it exposed to?",
        items=[
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="NVIDIA is exposed to risk Geopolitical export controls affecting China.",
                chunk_ids=["c1"],
            )
        ],
        allowed_chunk_ids=["c1"],
    )
    assert evidence_addresses_question(pack)


def test_evidence_addresses_rejects_competitor_without_product_cooccurrence():
    pack = EvidencePack(
        question="What is a possible competitor to Meta Glasses among major tech companies?",
        items=[
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="Meta competes with Apple Inc.",
                chunk_ids=["c1"],
            ),
            LabeledEvidenceItem(
                source_label="VECTOR",
                statement="Our current AI glasses include the Ray-Ban Meta glasses.",
                chunk_ids=["c2"],
            ),
        ],
        allowed_chunk_ids=["c1", "c2"],
    )
    assert not evidence_addresses_question(pack)


def test_evidence_addresses_open_product_segments_ask():
    """'segments' alone must not force-refuse a real products pack (MSFT)."""
    from answer import topic_needles

    q = "What product lines or segments does Microsoft produce?"
    assert topic_needles(q) == []
    pack = EvidencePack(
        question=q,
        items=[
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="Microsoft produces product Azure.",
                chunk_ids=["c1"],
            ),
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="Microsoft produces product Xbox.",
                chunk_ids=["c1"],
            ),
        ],
        allowed_chunk_ids=["c1"],
    )
    assert evidence_addresses_question(pack)


def test_evidence_addresses_general_competition_ask():
    """General AI/competition asks need a competition signal, not 'pressures'/'around'."""
    from answer import topic_needles

    q = (
        "What major competitors or competitive pressures does Meta describe "
        "around AI and its core products?"
    )
    assert "AI" in topic_needles(q) or "ai" in [t.lower() for t in topic_needles(q)]
    pack = EvidencePack(
        question=q,
        items=[
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="Meta Platforms competes with TikTok.",
                chunk_ids=["c1"],
            ),
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="Meta Platforms competes with Google.",
                chunk_ids=["c1"],
            ),
        ],
        allowed_chunk_ids=["c1"],
    )
    assert evidence_addresses_question(pack)


def test_topic_needles_keeps_short_aws():
    from answer import topic_needles

    needles = [t.lower() for t in topic_needles(
        "What is Netflix’s relationship to Amazon and AWS?"
    )]
    assert "aws" in needles


def test_evidence_addresses_automotive_via_drive_synonym():
    pack = EvidencePack(
        question="How is NVIDIA involved in the automotive space?",
        items=[
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="NVIDIA produces product NVIDIA DRIVE.",
                chunk_ids=["c1"],
            )
        ],
        allowed_chunk_ids=["c1"],
    )
    assert evidence_addresses_question(pack)


def test_evidence_addresses_accepts_on_topic_risk():
    pack = EvidencePack(
        question="What geopolitical risks is Nvidia exposed to?",
        items=[
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="NVIDIA is exposed to risk Geopolitical Export Controls affecting China.",
                chunk_ids=["c1"],
            )
        ],
        allowed_chunk_ids=["c1"],
    )
    assert evidence_addresses_question(pack)


def test_validate_citations_allows_empty_cites_when_refused():
    draft = GroundedAnswerDraft(
        summary="No evidence for this topic.",
        claims=[AnswerClaim(text="Cannot answer from pack.", citation_chunk_ids=[])],
        refused=True,
    )
    result = validate_citations(draft, ["c1", "c2"])
    assert result.valid


def test_normalize_refused_draft_validates():
    draft = normalize_refused_draft("What battery risks?", allowed_chunk_ids=["c9"])
    assert draft.refused
    assert validate_citations(draft, ["c9"]).valid


def test_truncate_passage_prefers_specific_needle_over_risks_header():
    """'risks' matches Item 1A header; window must still center on China/supply."""
    header = "Item 1A. Risk Factors The following summarizes factors that could have "
    mid = "x" * 1400
    supply = (
        "The Company's global supply chain is large and complex and a majority of "
        "supplier facilities are located outside the U.S."
    )
    tail = "y" * 500
    text = header + mid + supply + tail
    out = truncate_passage_for_query(
        text,
        "What China-related or international supply-chain risks does Apple describe?",
        400,
    )
    assert "supply chain" in out.lower()
    assert "Risk Factors The following" not in out


def test_filter_drops_products_on_supply_chain_risk_ask():
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
            rel_type="EXPOSED_TO_RISK",
            target_id="AAPL_SUPPLY",
            target_name="Supply Chain Risk",
            source_chunk_ids=["c2"],
            confidence=0.9,
            context="global supply chain outside the U.S.",
        ),
    ]
    kept = filter_unmatched_produces_facts(
        facts, "What major supply-chain risks does Apple describe?"
    )
    assert [f.rel_type for f in kept] == ["EXPOSED_TO_RISK"]


def test_evidence_addresses_hyphen_supply_chain():
    pack = EvidencePack(
        question="What major supply-chain risks does Apple describe?",
        items=[
            LabeledEvidenceItem(
                source_label="VECTOR",
                statement="The Company's global supply chain is large and complex.",
                chunk_ids=["c1"],
            )
        ],
        allowed_chunk_ids=["c1"],
    )
    assert evidence_addresses_question(pack)
