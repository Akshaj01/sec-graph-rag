"""
Phase 3 glue: route a question, then run graph and/or vector retrieval.

Does not generate a final answer (Phase 4). Returns structured evidence packs.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from pydantic import BaseModel, Field

from graph_retriever import GraphRetrievalResult, retrieve_graph
from router import RetrievalRoute, RouteDecision, route_question
from vector_retriever import VectorRetrievalResult, retrieve_vector


class HybridRetrievalResult(BaseModel):
    question: str
    routing: RouteDecision
    graph: Optional[GraphRetrievalResult] = None
    vector: Optional[VectorRetrievalResult] = None


_PRODUCE_YES_NO = re.compile(
    r"^\s*(?:does|do|did)\b.+\b(?:produce|produces|manufactur\w*)\b",
    re.IGNORECASE,
)


def wants_produce_yes_no(question: str) -> bool:
    """Yes/no product asks need vector segment prose when the graph lacks that ProductLine."""
    return bool(_PRODUCE_YES_NO.search(question or ""))


def retrieve(
    question: str,
    *,
    ticker: Optional[str] = None,
    log_route: bool = True,
    force_route: Optional[RetrievalRoute] = None,
) -> HybridRetrievalResult:
    """
    Route → execute graph / vector / both based on effective_route.

    force_route: skip the router (Phase 5 vector-only baseline uses VECTOR).
    """
    if force_route is not None:
        decision = RouteDecision(
            question=question,
            model_route=force_route,
            effective_route=force_route,
            confidence=1.0,
            rationale=f"Forced route={force_route.value} (benchmark / override).",
            low_confidence_fallback=False,
            model="forced",
        )
    else:
        decision = route_question(question, log=log_route)
        # Graph-only "does X produce Y?" fails when Y is a segment name not a
        # ProductLine node (e.g. J&J MedTech). Pull vector too.
        if (
            decision.effective_route == RetrievalRoute.GRAPH
            and wants_produce_yes_no(question)
        ):
            decision = decision.model_copy(
                update={
                    "effective_route": RetrievalRoute.BOTH,
                    "rationale": (
                        decision.rationale
                        + " [produce-yes/no heuristic → both for segment prose]"
                    ),
                }
            )

    route = decision.effective_route

    graph_result: Optional[GraphRetrievalResult] = None
    vector_result: Optional[VectorRetrievalResult] = None

    if route in (RetrievalRoute.GRAPH, RetrievalRoute.BOTH):
        graph_result = retrieve_graph(question, ticker=ticker)

    if route in (RetrievalRoute.VECTOR, RetrievalRoute.BOTH):
        vector_result = retrieve_vector(question, ticker=ticker)

    return HybridRetrievalResult(
        question=question,
        routing=decision,
        graph=graph_result,
        vector=vector_result,
    )


if __name__ == "__main__":
    import sys

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    question = " ".join(args) if args else "What is AppleCare?"
    result = retrieve(question)
    payload = result.model_dump()
    # Keep CLI readable: strip full passage text.
    if payload.get("vector") and payload["vector"].get("passages"):
        for p in payload["vector"]["passages"]:
            p.pop("text", None)
    print(json.dumps(payload, indent=2))
