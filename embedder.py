"""
Step H/I: Embed DocumentChunks into pgvector + attach entity_ids.

Pipeline:
  ingest (cached) → skip chunks already embedded by chunk_hash →
  OpenAI text-embedding-3-small → UPSERT into chunk_embeddings
  → attach entity_ids from extraction cache (Step I)

Shared chunk_id matches Neo4j source_chunk_ids.
entity_ids use hard-normalized names so they line up with resolver
canonical ids (e.g. Apple Inc. → APPLE).

Out of scope: HNSW index (Step J).
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Sequence

from openai import OpenAI
from pydantic import BaseModel

from config import settings
from extractor import ExtractionCache
from ingest import DocumentChunk, ingest_company
from resolver import normalize_name
from vector_db import (
    count_by_ticker,
    ensure_schema,
    get_connection,
    get_existing_hashes,
    sample_entity_links,
)


class EmbedStats(BaseModel):
    ticker: str
    accession_number: str
    filing_hash: str
    chunks_seen: int
    chunks_cached: int
    chunks_embedded: int
    chunks_entity_linked: int
    chunks_missing_extraction: int
    model: str
    rows_for_ticker: int
    sample_links: List[dict] = []


def _embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    if not settings.OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY is missing. Set it in your .env before embedding."
        )
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    vectors: List[List[float]] = []
    batch_size = 64
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=batch,
        )
        ordered = sorted(response.data, key=lambda row: row.index)
        vectors.extend([row.embedding for row in ordered])
    return vectors


def entity_ids_for_chunk(
    chunk: DocumentChunk,
    *,
    cache: Optional[ExtractionCache] = None,
) -> Optional[List[str]]:
    """
    Build sorted unique entity ids for a chunk from extraction cache.

    Returns None if no extraction is cached (caller can leave [] or skip).
    WHY normalize_name: Neo4j nodes use resolver canonical ids; raw Claude
    ids like APPLEINC must become APPLE to join cleanly.
    """
    cache = cache or ExtractionCache(settings.EXTRACTION_CACHE_PATH)
    extraction = cache.get(chunk.chunk_hash)
    if extraction is None:
        return None

    ids: set[str] = set()
    for entity in extraction.entities:
        canonical = normalize_name(entity.name) or entity.id.upper()
        if canonical:
            ids.add(canonical)
    return sorted(ids)


def _upsert_chunks(
    chunks: List[DocumentChunk],
    embeddings: List[List[float]],
    entity_ids_by_chunk: Dict[str, List[str]],
) -> None:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings length mismatch")

    model = settings.EMBEDDING_MODEL
    with get_connection() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            for chunk, emb in zip(chunks, embeddings):
                if len(emb) != settings.EMBEDDING_DIMENSIONS:
                    raise ValueError(
                        f"Expected {settings.EMBEDDING_DIMENSIONS}-d embedding, "
                        f"got {len(emb)} for {chunk.chunk_id}"
                    )
                entity_ids = entity_ids_by_chunk.get(chunk.chunk_id, [])
                cur.execute(
                    """
                    INSERT INTO chunk_embeddings (
                        chunk_id, chunk_hash, ticker, cik, accession_number,
                        filing_date, section, chunk_index, filing_hash,
                        text, embedding, model, entity_ids, embedded_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, NOW()
                    )
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        chunk_hash = EXCLUDED.chunk_hash,
                        ticker = EXCLUDED.ticker,
                        cik = EXCLUDED.cik,
                        accession_number = EXCLUDED.accession_number,
                        filing_date = EXCLUDED.filing_date,
                        section = EXCLUDED.section,
                        chunk_index = EXCLUDED.chunk_index,
                        filing_hash = EXCLUDED.filing_hash,
                        text = EXCLUDED.text,
                        embedding = EXCLUDED.embedding,
                        model = EXCLUDED.model,
                        entity_ids = EXCLUDED.entity_ids,
                        embedded_at = NOW()
                    """,
                    (
                        chunk.chunk_id,
                        chunk.chunk_hash,
                        chunk.ticker,
                        chunk.cik,
                        chunk.accession_number,
                        chunk.filing_date,
                        chunk.section,
                        chunk.chunk_index,
                        chunk.filing_hash,
                        chunk.text,
                        emb,
                        model,
                        entity_ids,
                    ),
                )
        conn.commit()


def link_entity_ids(
    chunks: Sequence[DocumentChunk],
    *,
    cache: Optional[ExtractionCache] = None,
) -> tuple[int, int]:
    """
    Backfill entity_ids on existing rows without re-embedding.

    Returns (linked_count, missing_extraction_count).
    """
    cache = cache or ExtractionCache(settings.EXTRACTION_CACHE_PATH)
    linked = 0
    missing = 0

    with get_connection() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            for chunk in chunks:
                ids = entity_ids_for_chunk(chunk, cache=cache)
                if ids is None:
                    missing += 1
                    ids = []
                else:
                    linked += 1
                cur.execute(
                    """
                    UPDATE chunk_embeddings
                    SET entity_ids = %s
                    WHERE chunk_id = %s
                    """,
                    (ids, chunk.chunk_id),
                )
        conn.commit()

    return linked, missing


def embed_company(
    ticker: str,
    *,
    max_chunks: Optional[int] = None,
    force_refresh: bool = False,
    link_only: bool = False,
) -> EmbedStats:
    """
    Embed ingest chunks for a ticker into pgvector and attach entity_ids.

    Cache key = chunk_hash: unchanged text is never re-sent to OpenAI.
    link_only: update entity_ids only (no OpenAI calls).
    """
    ingest_result = ingest_company(ticker)
    chunks = ingest_result.chunks
    if max_chunks is not None:
        chunks = chunks[:max_chunks]

    ensure_schema()
    cache = ExtractionCache(settings.EXTRACTION_CACHE_PATH)

    if link_only:
        linked, missing = link_entity_ids(chunks, cache=cache)
        return EmbedStats(
            ticker=ingest_result.ticker,
            accession_number=ingest_result.accession_number,
            filing_hash=ingest_result.filing_hash,
            chunks_seen=len(chunks),
            chunks_cached=len(chunks),
            chunks_embedded=0,
            chunks_entity_linked=linked,
            chunks_missing_extraction=missing,
            model=settings.EMBEDDING_MODEL,
            rows_for_ticker=count_by_ticker(ingest_result.ticker),
            sample_links=sample_entity_links(ingest_result.ticker),
        )

    if force_refresh:
        to_embed = list(chunks)
        cached_count = 0
    else:
        existing = get_existing_hashes([c.chunk_hash for c in chunks])
        to_embed = [c for c in chunks if c.chunk_hash not in existing]
        cached_count = len(chunks) - len(to_embed)

    entity_map: Dict[str, List[str]] = {}
    missing = 0
    for chunk in to_embed:
        ids = entity_ids_for_chunk(chunk, cache=cache)
        if ids is None:
            missing += 1
            entity_map[chunk.chunk_id] = []
        else:
            entity_map[chunk.chunk_id] = ids

    if to_embed:
        vectors = _embed_texts([c.text for c in to_embed])
        _upsert_chunks(to_embed, vectors, entity_map)

    # Always refresh entity_ids for cached rows too (cheap, no OpenAI).
    linked_all, missing_all = link_entity_ids(chunks, cache=cache)

    return EmbedStats(
        ticker=ingest_result.ticker,
        accession_number=ingest_result.accession_number,
        filing_hash=ingest_result.filing_hash,
        chunks_seen=len(chunks),
        chunks_cached=cached_count,
        chunks_embedded=len(to_embed),
        chunks_entity_linked=linked_all,
        chunks_missing_extraction=missing_all,
        model=settings.EMBEDDING_MODEL,
        rows_for_ticker=count_by_ticker(ingest_result.ticker),
        sample_links=sample_entity_links(ingest_result.ticker),
    )


if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    run_all = "--all" in sys.argv
    force = "--force" in sys.argv
    link_only = "--link-entities" in sys.argv
    # Default 5 chunks: cheap smoke test; --all for full filing.
    max_chunks = None if run_all else 5

    stats = embed_company(
        symbol,
        max_chunks=max_chunks,
        force_refresh=force,
        link_only=link_only,
    )
    print(json.dumps(stats.model_dump(), indent=2))
