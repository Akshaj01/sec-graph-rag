"""Trace projection for POST /ask. Does not call a model or a database."""

from __future__ import annotations

import json

from answer import (
    AnswerClaim,
    AnswerResult,
    EvidencePack,
    GroundedAnswerDraft,
    LabeledEvidenceItem,
)
from api import AskResponse, _MAX_FACTS, _PREVIEW_CHARS, ask_response_from_result
from graph_retriever import (
    GraphFact,
    GraphRetrievalResult,
    GraphTemplateId,
)
from retrieve import HybridRetrievalResult
from router import RetrievalRoute, RouteDecision
from vector_retriever import VectorPassage, VectorRetrievalResult


def _result(*, with_graph: bool = True, with_vector: bool = True) -> AnswerResult:
    facts = [
        GraphFact(
            source_id="APPLE",
            source_name="Apple Inc.",
            rel_type="PRODUCES_PRODUCT",
            target_id=f"AAPL_P{i}",
            target_name=f"Product {i}",
            source_chunk_ids=["0000320193-25-000079:Item1:0"] * 8,
        )
        for i in range(_MAX_FACTS + 3)
    ]
    long_text = "AppleCare " * 80
    return AnswerResult(
        question="What product lines does Apple produce?",
        retrieval=HybridRetrievalResult(
            question="What product lines does Apple produce?",
            routing=RouteDecision(
                question="What product lines does Apple produce?",
                model_route=RetrievalRoute.GRAPH,
                effective_route=RetrievalRoute.GRAPH,
                confidence=0.92,
                rationale="Requires PRODUCES_PRODUCT edges.",
                low_confidence_fallback=False,
                model="test",
            ),
            graph=GraphRetrievalResult(
                question="What product lines does Apple produce?",
                template_id=GraphTemplateId.COMPANY_PRODUCTS,
                template_ids=[GraphTemplateId.COMPANY_PRODUCTS],
                plan_rationale="Product lines sit on PRODUCES_PRODUCT.",
                resolved_entities=[],
                facts=facts,
                cypher_ran=True,
            )
            if with_graph
            else None,
            vector=VectorRetrievalResult(
                question="What product lines does Apple produce?",
                ticker="AAPL",
                k=8,
                model="embed-test",
                passages=[
                    VectorPassage(
                        chunk_id="0000320193-25-000079:Item1:0",
                        section="Item1",
                        text=long_text,
                        score=0.81,
                        text_preview=long_text,
                    )
                ],
            )
            if with_vector
            else None,
        ),
        evidence=EvidencePack(
            question="What product lines does Apple produce?",
            items=[
                LabeledEvidenceItem(
                    source_label="GRAPH",
                    statement="Apple produces iPhone. " * 40,
                    chunk_ids=["0000320193-25-000079:Item1:0"],
                    section="Item1",
                    score=0.9,
                )
            ],
            allowed_chunk_ids=["0000320193-25-000079:Item1:0"],
            prompt_text="SECRET PROMPT " + long_text,
        ),
        draft=GroundedAnswerDraft(
            summary="Apple produces iPhone, Mac, and iPad.",
            claims=[
                AnswerClaim(
                    text="Apple produces iPhone.",
                    citation_chunk_ids=["0000320193-25-000079:Item1:0"],
                )
            ],
            refused=False,
        ),
        model="test-answer",
        citations_valid=True,
        regenerated=False,
        attempts=1,
    )


def test_trace_keeps_route_and_drops_prompt_and_full_passage():
    response = ask_response_from_result(_result())
    dumped = response.model_dump()

    assert dumped["route_effective"] == "graph"
    assert dumped["trace"]["route"]["confidence"] == 0.92
    assert dumped["trace"]["route"]["low_confidence_fallback"] is False
    assert dumped["trace"]["graph"]["template_ids"] == ["company_products"]
    assert len(dumped["trace"]["graph"]["facts"]) == _MAX_FACTS
    assert len(dumped["trace"]["graph"]["facts"][0]["source_chunk_ids"]) == 6
    preview = dumped["trace"]["vector"]["passages"][0]["text_preview"]
    assert len(preview) <= _PREVIEW_CHARS
    assert "text" not in dumped["trace"]["vector"]["passages"][0]
    assert len(dumped["trace"]["evidence"]["items"][0]["statement"]) <= 320
    assert "SECRET PROMPT" not in str(dumped["trace"])
    assert dumped["trace"]["validation"]["citations_valid"] is True
    assert dumped["trace"]["answer"]["refused"] is False


def test_saved_runs_match_ask_response():
    from pathlib import Path

    fixture_dir = Path(__file__).parent / "web" / "fixtures"
    names = (
        "aapl-products.json",
        "nvda-products-risks.json",
        "aapl-bitcoin.json",
    )
    for name in names:
        payload = json.loads((fixture_dir / name).read_text())
        assert payload["saved_run"] is True
        assert payload["note"]
        AskResponse.model_validate(payload["response"])


def test_trace_omits_retrievers_that_did_not_run():
    response = ask_response_from_result(_result(with_graph=False, with_vector=False))
    assert response.trace.graph is None
    assert response.trace.vector is None
    assert response.summary.startswith("Apple produces")
