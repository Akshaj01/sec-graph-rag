"""
Step J: HNSW-backed retrieval + recall@k smoke test.

Curriculum gate: measure retrieval quality on a small labeled set
BEFORE building a Phase 3 router.

Labeled queries are hand-written against the AAPL 5-chunk smoke index.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Sequence, Set

from openai import OpenAI
from pydantic import BaseModel, Field

from config import settings
from vector_db import ensure_schema, hnsw_index_exists, search_similar_chunks


# Hand-labeled against AAPL accession 0000320193-25-000079 (5-chunk smoke set).
# relevant_chunk_ids = chunks that SHOULD appear in top-k for a good retriever.
AAPL_LABELED_QUERIES: List[Dict[str, object]] = [
    {
        "id": "q1_products",
        "query": "What product lines does Apple sell such as iPhone Mac iPad and AirPods?",
        "relevant_chunk_ids": ["0000320193-25-000079:Item1:0"],
    },
    {
        "id": "q2_china_tariffs",
        "query": "What risks does Apple face from China tariffs and international trade disputes?",
        "relevant_chunk_ids": ["0000320193-25-000079:Item1A:0"],
    },
    {
        "id": "q3_supply_chain",
        "query": "Component supply shortages manufacturing defects and product introduction risks",
        "relevant_chunk_ids": ["0000320193-25-000079:Item1A:1"],
    },
    {
        "id": "q4_competitors",
        "query": "Competition from Android Windows PlayStation Nintendo and Xbox",
        "relevant_chunk_ids": ["0000320193-25-000079:Item1A:2"],
    },
    {
        "id": "q5_seasonality_ip",
        "query": "Apple University seasonality and intellectual property licensing",
        "relevant_chunk_ids": ["0000320193-25-000079:Item1:1"],
    },
]


class QueryRecallResult(BaseModel):
    id: str
    query: str
    k: int
    relevant: List[str]
    retrieved: List[str]
    hits: List[str]
    recall_at_k: float
    top_scores: List[float] = Field(default_factory=list)


class RecallReport(BaseModel):
    ticker: str
    k: int
    n_queries: int
    mean_recall_at_k: float
    hnsw_index: bool
    queries: List[QueryRecallResult]


def _embed_query(text: str) -> List[float]:
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is missing. Set it in your .env.")
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=[text],
    )
    return list(response.data[0].embedding)


def recall_at_k(relevant: Set[str], retrieved: Sequence[str]) -> float:
    """
    |relevant ∩ retrieved| / |relevant|

    WHY recall (not precision): curriculum asks whether the right chunks
    appear in top-k before we trust vector path in a router.
    """
    if not relevant:
        return 0.0
    hits = relevant.intersection(retrieved)
    return len(hits) / len(relevant)


def retrieve(
    query: str,
    *,
    k: int = 3,
    ticker: Optional[str] = "AAPL",
) -> List[Dict[str, object]]:
    ensure_schema()
    emb = _embed_query(query)
    return search_similar_chunks(emb, k=k, ticker=ticker)


def evaluate_recall(
    *,
    k: int = 3,
    ticker: str = "AAPL",
    labeled: Optional[List[Dict[str, object]]] = None,
) -> RecallReport:
    """
    Run labeled queries and report mean recall@k.

    Default labeled set assumes the AAPL 5-chunk smoke index is loaded.
    """
    ensure_schema()
    labeled = labeled or AAPL_LABELED_QUERIES
    results: List[QueryRecallResult] = []

    for item in labeled:
        qid = str(item["id"])
        query = str(item["query"])
        relevant = {str(x) for x in item["relevant_chunk_ids"]}  # type: ignore[arg-type]
        hits_rows = retrieve(query, k=k, ticker=ticker)
        retrieved = [str(r["chunk_id"]) for r in hits_rows]
        score = recall_at_k(relevant, retrieved)
        results.append(
            QueryRecallResult(
                id=qid,
                query=query,
                k=k,
                relevant=sorted(relevant),
                retrieved=retrieved,
                hits=sorted(relevant.intersection(retrieved)),
                recall_at_k=round(score, 4),
                top_scores=[float(r["score"]) for r in hits_rows],
            )
        )

    mean = sum(r.recall_at_k for r in results) / len(results) if results else 0.0
    return RecallReport(
        ticker=ticker.upper(),
        k=k,
        n_queries=len(results),
        mean_recall_at_k=round(mean, 4),
        hnsw_index=hnsw_index_exists(),
        queries=results,
    )


if __name__ == "__main__":
    import sys

    k = 3
    for arg in sys.argv[1:]:
        if arg.startswith("--k="):
            k = int(arg.split("=", 1)[1])

    report = evaluate_recall(k=k)
    print(json.dumps(report.model_dump(), indent=2))
