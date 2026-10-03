"""Free unit tests for multi-template graph plans + graph answer fallback."""

from __future__ import annotations

from answer import (
    EvidencePack,
    LabeledEvidenceItem,
    draft_from_graph_evidence,
    has_answerable_graph_evidence,
)
from graph_retriever import (
    GraphFact,
    GraphQueryPlan,
    GraphTemplateId,
    _dedupe_facts,
)


def test_plan_accepts_multiple_template_ids():
    plan = GraphQueryPlan(
        template_ids=[
            GraphTemplateId.COMPANY_PRODUCTS,
            GraphTemplateId.COMPANY_RISKS,
        ],
        entity_mentions=["NVIDIA"],
        rationale="Need products and risks for a hop-2 question.",
    )
    assert plan.template_id == GraphTemplateId.COMPANY_PRODUCTS
    assert len(plan.template_ids) == 2


def test_dedupe_facts_keeps_first():
    a = GraphFact(
        source_id="NVIDIA",
        source_name="NVIDIA",
        rel_type="PRODUCES_PRODUCT",
        target_id="NVDA_A100",
        target_name="A100",
        source_chunk_ids=["c1"],
        confidence=0.9,
    )
    b = GraphFact(
        source_id="NVIDIA",
        source_name="NVIDIA",
        rel_type="PRODUCES_PRODUCT",
        target_id="NVDA_A100",
        target_name="A100",
        source_chunk_ids=["c2"],
        confidence=0.5,
    )
    c = GraphFact(
        source_id="NVIDIA",
        source_name="NVIDIA",
        rel_type="EXPOSED_TO_RISK",
        target_id="NVDA_GEOPOLITICALRISK",
        target_name="Geopolitical Risk",
        source_chunk_ids=["c3"],
        confidence=0.8,
    )
    out = _dedupe_facts([a, b, c])
    assert len(out) == 2
    assert out[0].source_chunk_ids == ["c1"]
    assert out[1].target_id == "NVDA_GEOPOLITICALRISK"


def test_draft_from_graph_evidence_answers_sibling_products():
    evidence = EvidencePack(
        question="How do Meta's Facebook and Reality Labs relate?",
        items=[
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="Meta produces product Facebook.",
                chunk_ids=["m1"],
            ),
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="Meta produces product Instagram.",
                chunk_ids=["m2"],
            ),
            LabeledEvidenceItem(
                source_label="GRAPH",
                statement="Meta produces product Reality Labs.",
                chunk_ids=["m3"],
            ),
        ],
        allowed_chunk_ids=["m1", "m2", "m3"],
    )
    assert has_answerable_graph_evidence(evidence)
    draft = draft_from_graph_evidence(evidence)
    assert draft is not None
    assert draft.refused is False
    text = draft.summary + " " + " ".join(c.text for c in draft.claims)
    assert "Facebook" in text
    assert "Reality Labs" in text
    assert all(c.citation_chunk_ids for c in draft.claims)


def test_augment_template_ids_adds_risks_for_products_and_risks_question():
    from graph_retriever import augment_template_ids

    out = augment_template_ids(
        "What compute products does NVIDIA produce, and what geopolitical risks is it exposed to?",
        [GraphTemplateId.COMPANY_PRODUCTS],
    )
    assert GraphTemplateId.COMPANY_PRODUCTS in out
    assert GraphTemplateId.COMPANY_RISKS in out
    assert len(out) <= 3


def test_draft_from_graph_evidence_none_without_graph():
    evidence = EvidencePack(
        question="q",
        items=[
            LabeledEvidenceItem(
                source_label="VECTOR",
                statement="Some prose",
                chunk_ids=["v1"],
            )
        ],
        allowed_chunk_ids=["v1"],
    )
    assert draft_from_graph_evidence(evidence) is None
