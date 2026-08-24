"""
Step D: Schema extraction with Claude + Instructor.

For each DocumentChunk:
  1) Call Claude with response_model=KnowledgeGraphExtraction
  2) Instructor validates against Pydantic (retries on ValidationError)
  3) Stamp source_chunk_id from the real chunk (do not trust the model)
  4) Cache by chunk_hash so unchanged text is not re-billed

Out of scope: entity resolution (Step E), Neo4j writes (Step F).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import anthropic
import instructor
from pydantic import BaseModel

from config import settings
from ingest import DocumentChunk, ingest_company
from schemas import (
    Entity,
    EntityType,
    KnowledgeGraphExtraction,
    Relationship,
    RelationshipType,
)

SYSTEM_PROMPT = f"""
You extract a closed-world knowledge graph from one SEC 10-K text chunk.

ALLOWED entity types ONLY:
{', '.join(e.value for e in EntityType)}

ALLOWED relationship types ONLY:
{', '.join(r.value for r in RelationshipType)}

Rules:
- Extract only facts explicitly supported by the chunk text. Do not invent.
- Use canonical names (clean official-style names, not ticker symbols alone when a name is present).
- Entity id: uppercase, alphanumeric only (strip spaces/punctuation), stable within this chunk.
- Relationships must reference entity ids that appear in entities.
- confidence is your calibrated probability in [0.0, 1.0] that the claim is correctly typed and grounded.
- If nothing relevant exists in the chunk, return empty lists.
- Prefer precision over recall: omit weak or speculative claims.
""".strip()


class ChunkExtractionResult(BaseModel):
    chunk_id: str
    chunk_hash: str
    section: str
    cache_hit: bool
    extraction: KnowledgeGraphExtraction


class ExtractionRunResult(BaseModel):
    ticker: str
    accession_number: str
    filing_hash: str
    chunks_processed: int
    cache_hits: int
    results: List[ChunkExtractionResult]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp_source_chunk_id(
    extraction: KnowledgeGraphExtraction,
    chunk_id: str,
) -> KnowledgeGraphExtraction:
    """
    Provenance must point at the chunk we actually sent.

    WHY overwrite: models can mistype or ignore source_chunk_id; citations
    become worthless if this field is wrong.
    """
    entities = [
        Entity(**{**e.model_dump(), "source_chunk_id": chunk_id})
        for e in extraction.entities
    ]
    relationships = [
        Relationship(**{**r.model_dump(), "source_chunk_id": chunk_id})
        for r in extraction.relationships
    ]
    return KnowledgeGraphExtraction(entities=entities, relationships=relationships)


class ExtractionCache:
    """SQLite cache keyed by chunk_hash (content-addressable extraction results)."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extractions (
                    chunk_hash TEXT PRIMARY KEY,
                    chunk_id TEXT NOT NULL,
                    section TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    extracted_at TEXT NOT NULL
                )
                """
            )

    def get(self, chunk_hash: str) -> Optional[KnowledgeGraphExtraction]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM extractions WHERE chunk_hash = ?",
                (chunk_hash,),
            ).fetchone()
        if row is None:
            return None
        return KnowledgeGraphExtraction.model_validate_json(row["payload_json"])

    def put(
        self,
        *,
        chunk_hash: str,
        chunk_id: str,
        section: str,
        extraction: KnowledgeGraphExtraction,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO extractions
                    (chunk_hash, chunk_id, section, payload_json, extracted_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    chunk_hash,
                    chunk_id,
                    section,
                    extraction.model_dump_json(),
                    _utc_now(),
                ),
            )


def _build_client() -> instructor.Instructor:
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY is missing. Set it in your .env before running extraction."
        )
    raw = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    # Prefer Anthropic tool-calling mode when available (enforces JSON shape).
    mode = getattr(instructor.Mode, "ANTHROPIC_TOOLS", None) or instructor.Mode.TOOLS
    return instructor.from_anthropic(raw, mode=mode)


def extract_chunk(
    chunk: DocumentChunk,
    *,
    client: Optional[instructor.Instructor] = None,
    cache: Optional[ExtractionCache] = None,
    force_refresh: bool = False,
) -> ChunkExtractionResult:
    """Extract a validated KnowledgeGraphExtraction from one chunk."""
    cache = cache or ExtractionCache(settings.EXTRACTION_CACHE_PATH)

    if not force_refresh:
        cached = cache.get(chunk.chunk_hash)
        if cached is not None:
            stamped = _stamp_source_chunk_id(cached, chunk.chunk_id)
            return ChunkExtractionResult(
                chunk_id=chunk.chunk_id,
                chunk_hash=chunk.chunk_hash,
                section=chunk.section,
                cache_hit=True,
                extraction=stamped,
            )

    client = client or _build_client()

    user_prompt = (
        f"source_chunk_id (must use exactly this value on every entity and relationship): "
        f"{chunk.chunk_id}\n"
        f"section: {chunk.section}\n"
        f"ticker: {chunk.ticker}\n\n"
        f"CHUNK TEXT:\n{chunk.text}"
    )

    # Instructor validates against KnowledgeGraphExtraction and retries on schema failure.
    extraction: KnowledgeGraphExtraction = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=settings.EXTRACTION_MAX_TOKENS,
        max_retries=settings.EXTRACTION_MAX_RETRIES,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        response_model=KnowledgeGraphExtraction,
    )

    extraction = _stamp_source_chunk_id(extraction, chunk.chunk_id)
    cache.put(
        chunk_hash=chunk.chunk_hash,
        chunk_id=chunk.chunk_id,
        section=chunk.section,
        extraction=extraction,
    )

    return ChunkExtractionResult(
        chunk_id=chunk.chunk_id,
        chunk_hash=chunk.chunk_hash,
        section=chunk.section,
        cache_hit=False,
        extraction=extraction,
    )


def extract_company(
    ticker: str,
    *,
    max_chunks: Optional[int] = None,
    force_refresh: bool = False,
    confirm: bool = False,
    skip_budget_check: bool = False,
) -> ExtractionRunResult:
    """
    Ingest (or load cached chunks), then run extraction over each chunk.

    max_chunks: optional cap for cheap smoke tests (e.g. max_chunks=1).
    confirm: must be True to spend on uncached chunks (see budget.py).
    """
    ingest_result = ingest_company(ticker)
    chunks = ingest_result.chunks
    if max_chunks is not None:
        chunks = chunks[:max_chunks]

    if not skip_budget_check:
        from budget import estimate_extraction_budget, require_budget_confirmation

        budget = estimate_extraction_budget(ingest_result, max_chunks=max_chunks)
        require_budget_confirmation(budget, confirmed=confirm)

    cache = ExtractionCache(settings.EXTRACTION_CACHE_PATH)
    client: Optional[instructor.Instructor] = None

    results: List[ChunkExtractionResult] = []
    cache_hits = 0
    for chunk in chunks:
        if not force_refresh and cache.get(chunk.chunk_hash) is not None:
            result = extract_chunk(
                chunk,
                cache=cache,
                force_refresh=False,
            )
        else:
            client = client or _build_client()
            result = extract_chunk(
                chunk,
                client=client,
                cache=cache,
                force_refresh=force_refresh,
            )
        if result.cache_hit:
            cache_hits += 1
        results.append(result)

    return ExtractionRunResult(
        ticker=ingest_result.ticker,
        accession_number=ingest_result.accession_number,
        filing_hash=ingest_result.filing_hash,
        chunks_processed=len(results),
        cache_hits=cache_hits,
        results=results,
    )


if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    run_all = "--all" in sys.argv
    budget_only = "--budget" in sys.argv
    confirmed = "--confirm" in sys.argv
    max_chunks = None if run_all else 1

    if budget_only:
        from budget import estimate_ticker_budget

        print(json.dumps(estimate_ticker_budget(symbol, max_chunks=max_chunks).model_dump(), indent=2))
        sys.exit(0)

    run = extract_company(
        symbol,
        max_chunks=max_chunks if not run_all else None,
        confirm=confirmed,
    )

    summary = {
        "ticker": run.ticker,
        "accession_number": run.accession_number,
        "chunks_processed": run.chunks_processed,
        "cache_hits": run.cache_hits,
        "sample": [
            {
                "chunk_id": r.chunk_id,
                "section": r.section,
                "cache_hit": r.cache_hit,
                "num_entities": len(r.extraction.entities),
                "num_relationships": len(r.extraction.relationships),
                "entities": [
                    {
                        "type": e.type.value,
                        "name": e.name,
                        "confidence": e.confidence,
                        "source_chunk_id": e.source_chunk_id,
                    }
                    for e in r.extraction.entities[:5]
                ],
            }
            for r in run.results[:1]
        ],
    }
    print(json.dumps(summary, indent=2))
