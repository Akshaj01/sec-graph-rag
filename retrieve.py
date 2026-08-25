"""
Phase 3 glue: route a question, then run graph and/or vector retrieval.

Does not generate a final answer (Phase 4). Returns structured evidence packs.
"""

from __future__ import annotations

import json
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


def retrieve(
    question: str,
    *,
    ticker: Optional[str] = None,
    log_route: bool = True,
) -> HybridRetrievalResult:
    """
    Route → execute graph / vector / both based on effective_route.
    """
    decision = route_question(question, log=log_route)
    route = decision.effective_route

    graph_result: Optional[GraphRetrievalResult] = None
    vector_result: Optional[VectorRetrievalResult] = None

    if route in (RetrievalRoute.GRAPH, RetrievalRoute.BOTH):
        graph_result = retrieve_graph(question)

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
