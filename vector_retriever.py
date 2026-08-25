"""
Step M: Vector retrieval path for routed questions.

Reuses Phase 2 embedding + HNSW search (vector_db / same model as recall_eval).
Returns passages with chunk_id (citation key) + entity_ids (graph cross-link).

Out of scope: answer generation / citation validation (Phase 4).
"""

from __future__ import annotations

import json
import re
from typing import List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field

from config import settings
from vector_db import ensure_schema, search_similar_chunks


class VectorPassage(BaseModel):
    chunk_id: str
    section: str
    text: str
    score: float
    entity_ids: List[str] = Field(default_factory=list)
    # Short preview for CLI / logs (full text kept for Phase 4).
    text_preview: str = ""


class VectorRetrievalResult(BaseModel):
    question: str
    ticker: Optional[str] = None
    k: int
    model: str
    passages: List[VectorPassage] = Field(default_factory=list)


_TICKER_HINT = re.compile(r"\b([A-Z]{1,5})\b")


def _embed_query(text: str) -> List[float]:
    if not settings.OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY is missing. Set it in your .env before vector retrieval."
        )
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=[text],
    )
    return list(response.data[0].embedding)


def _preview(text: str, *, max_chars: int = 240) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3] + "..."


def guess_ticker(question: str) -> Optional[str]:
    """
    Lightweight ticker hint for filtering the vector index.

    WHY: multi-company corpora need scoping; AAPL smoke tests default to AAPL
    when no clear ticker token is present.
    """
    lowered = question.lower()
    if "apple" in lowered or "aapl" in lowered:
        return "AAPL"
    # Avoid matching common English words that look like tickers.
    skip = {"WHAT", "WHEN", "WHERE", "WHICH", "WHO", "HOW", "THE", "AND", "FOR", "RISK"}
    for token in _TICKER_HINT.findall(question.upper()):
        if token not in skip and len(token) >= 2:
            return token
    return None


def retrieve_vector(
    question: str,
    *,
    k: Optional[int] = None,
    ticker: Optional[str] = None,
    default_ticker: Optional[str] = "AAPL",
) -> VectorRetrievalResult:
    """
    Embed the question and return top-k similar chunks from pgvector.

    ticker=None with default_ticker set scopes to that company (smoke-test friendly).
    Pass ticker="" or default_ticker=None to search the full index.
    """
    k = settings.VECTOR_RETRIEVAL_K if k is None else k
    ensure_schema()

    scope = ticker if ticker is not None else guess_ticker(question) or default_ticker
    if scope == "":
        scope = None

    emb = _embed_query(question)
    rows = search_similar_chunks(emb, k=k, ticker=scope)

    passages = [
        VectorPassage(
            chunk_id=str(r["chunk_id"]),
            section=str(r["section"]),
            text=str(r["text"]),
            score=float(r["score"]),
            entity_ids=[str(x) for x in (r.get("entity_ids") or [])],
            text_preview=_preview(str(r["text"])),
        )
        for r in rows
    ]

    return VectorRetrievalResult(
        question=question,
        ticker=scope,
        k=k,
        model=settings.EMBEDDING_MODEL,
        passages=passages,
    )


if __name__ == "__main__":
    import sys

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    question = " ".join(args) if args else "What is AppleCare?"
    # Compact CLI: drop full text, keep preview.
    result = retrieve_vector(question)
    payload = result.model_dump()
    for p in payload["passages"]:
        p.pop("text", None)
    print(json.dumps(payload, indent=2))
