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


_LEXICAL_STOP = {
    "what",
    "whats",
    "which",
    "when",
    "where",
    "who",
    "how",
    "does",
    "did",
    "is",
    "are",
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "for",
    "and",
    "or",
    "as",
    "according",
    "filing",
    "filings",
    "company",
    "about",
    "from",
    "with",
    "describe",
    "said",
}


def lexical_needles(question: str) -> List[str]:
    """Needles for post-HNSW lexical / entity boost (shared with answer windowing idea)."""
    needles: List[str] = []
    seen = set()

    def _add(raw: str) -> None:
        s = (raw or "").strip()
        if len(s) < 3:
            return
        key = s.lower()
        if key in seen or key in _LEXICAL_STOP:
            return
        seen.add(key)
        needles.append(s)

    for m in re.findall(r"\b([A-Z][A-Za-z0-9]+(?:[A-Z][A-Za-z0-9]+)*)\b", question or ""):
        if m.upper() not in {"WHAT", "WHEN", "WHERE", "WHICH", "WHO", "HOW", "THE", "AND"}:
            _add(m)
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", question or ""):
        if tok.lower() not in _LEXICAL_STOP:
            _add(tok)
    return needles


def lexical_boost_score(
    *,
    text: str,
    entity_ids: List[str],
    needles: List[str],
    base_score: float,
) -> float:
    """
    Add a small additive boost when passage text or entity_ids match query needles.

    Kept small so dense similarity still dominates; enough to surface a
    definitional chunk that HNSW ranked just outside / below boilerplate.
    """
    if not needles:
        return base_score
    blob = (text or "").lower()
    ids_blob = " ".join(entity_ids or []).lower()
    boost = 0.0
    for needle in needles:
        n = needle.lower()
        if n in blob:
            boost += 0.08
        # entity id tokens: MSFT_AZURE contains azure
        if n in ids_blob or n.replace(" ", "") in ids_blob.replace("_", "").replace(" ", ""):
            boost += 0.12
        # id suffix exact-ish
        for eid in entity_ids or []:
            suffix = eid.split("_", 1)[-1].lower()
            if suffix and (suffix == n or n in suffix or suffix in n.replace(" ", "")):
                boost += 0.1
                break
    return base_score + min(boost, 0.35)


def rerank_passages_lexical(
    passages: List[VectorPassage],
    question: str,
    *,
    k: int,
) -> List[VectorPassage]:
    """Re-score and keep top-k after HNSW fetch."""
    needles = lexical_needles(question)
    scored: List[VectorPassage] = []
    for p in passages:
        new_score = lexical_boost_score(
            text=p.text,
            entity_ids=list(p.entity_ids or []),
            needles=needles,
            base_score=float(p.score),
        )
        scored.append(p.model_copy(update={"score": new_score}))
    scored.sort(key=lambda x: float(x.score), reverse=True)
    return scored[:k]


def guess_ticker(question: str) -> Optional[str]:
    """
    Lightweight ticker hint for filtering the vector index.

    WHY: single-company (AAPL) questions rarely spell out the ticker, so this
    keeps that case scoped. It is intentionally narrow — it only recognizes
    Apple by name and bare uppercase ticker tokens — so it will miss most
    natural-language mentions of other companies (e.g. "Microsoft"). That's
    fine: retrieve_vector's default_ticker=None means an unrecognized
    question falls through to a full-index search rather than silently
    landing on the wrong company.
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
    default_ticker: Optional[str] = None,
) -> VectorRetrievalResult:
    """
    Embed the question and return top-k similar chunks from pgvector.

    ticker=None searches the full index unless guess_ticker recognizes a
    company from the question text, or a caller passes default_ticker to
    force a scope (e.g. a single-company smoke test). Pass ticker="" to force
    a full-index search even when guess_ticker would otherwise match.

    WHY not default to AAPL: once the corpus holds more than one company, an
    unscoped default silently hides every other company's chunks behind an
    Apple-only search. A full-index search is the safe default; callers that
    know the company (the API's `ticker` field, benchmark harness) should
    pass it explicitly.
    """
    k = settings.VECTOR_RETRIEVAL_K if k is None else k
    ensure_schema()

    scope = ticker if ticker is not None else guess_ticker(question) or default_ticker
    if scope == "":
        scope = None

    emb = _embed_query(question)
    # Over-fetch so lexical/entity boost can promote definitional chunks that
    # dense similarity ranked below Item 1 boilerplate.
    fetch_k = max(k, min(k * 3, 15))
    rows = search_similar_chunks(emb, k=fetch_k, ticker=scope)

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
    passages = rerank_passages_lexical(passages, question, k=k)

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
