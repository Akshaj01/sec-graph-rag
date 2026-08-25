"""
Step G/H/I: Postgres + pgvector schema and connectivity.

Shared chunk_id is the cross-link key between Neo4j (source_chunk_ids)
and this vector table. entity_ids link a vector hit → graph nodes.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

import psycopg
from pgvector.psycopg import register_vector

from config import settings


def get_connection() -> psycopg.Connection:
    conn = psycopg.connect(settings.postgres_dsn)
    register_vector(conn)
    return conn


def ensure_schema(conn: Optional[psycopg.Connection] = None) -> None:
    """
    Create/migrate chunk_embeddings table.

    WHY chunk_id as PK: same id as ingest DocumentChunk.chunk_id and
    Neo4j edge source_chunk_ids — Phase 2/3 join key.
    WHY entity_ids TEXT[]: Step I cross-link so a vector hit can jump to
    Neo4j nodes without re-reading the chunk text.
    """
    own = conn is None
    conn = conn or get_connection()
    try:
        dim = settings.EMBEDDING_DIMENSIONS
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    chunk_id TEXT PRIMARY KEY,
                    chunk_hash TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    cik TEXT NOT NULL,
                    accession_number TEXT NOT NULL,
                    filing_date TEXT NOT NULL,
                    section TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    filing_hash TEXT NOT NULL,
                    text TEXT NOT NULL,
                    embedding vector({dim}) NOT NULL,
                    model TEXT NOT NULL,
                    entity_ids TEXT[] NOT NULL DEFAULT '{{}}',
                    embedded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            # Migrate tables created in Step H before entity_ids existed.
            cur.execute(
                """
                ALTER TABLE chunk_embeddings
                ADD COLUMN IF NOT EXISTS entity_ids TEXT[] NOT NULL DEFAULT '{}'
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_chunk_hash
                    ON chunk_embeddings (chunk_hash)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_ticker
                    ON chunk_embeddings (ticker)
                """
            )
            # GIN: WHERE entity_ids @> ARRAY['APPLE']
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_entity_ids
                    ON chunk_embeddings USING GIN (entity_ids)
                """
            )
            # Step J: HNSW for approximate nearest-neighbor cosine search.
            # WHY HNSW: curriculum requires ANN index before building a router;
            # cosine ops match OpenAI embedding similarity.
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_hnsw
                    ON chunk_embeddings
                    USING hnsw (embedding vector_cosine_ops)
                """
            )
        conn.commit()
    finally:
        if own:
            conn.close()


def search_similar_chunks(
    query_embedding: Sequence[float],
    *,
    k: int = 5,
    ticker: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Cosine nearest-neighbor search over chunk_embeddings.

    Returns chunk_id, section, text, score (1 - cosine distance), entity_ids.
    """
    if k < 1:
        raise ValueError("k must be >= 1")

    with get_connection() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            if ticker:
                cur.execute(
                    """
                    SELECT chunk_id, section, text, entity_ids,
                           1 - (embedding <=> %s::vector) AS score
                    FROM chunk_embeddings
                    WHERE ticker = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (list(query_embedding), ticker.upper(), list(query_embedding), k),
                )
            else:
                cur.execute(
                    """
                    SELECT chunk_id, section, text, entity_ids,
                           1 - (embedding <=> %s::vector) AS score
                    FROM chunk_embeddings
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (list(query_embedding), list(query_embedding), k),
                )
            rows = cur.fetchall()

    return [
        {
            "chunk_id": r[0],
            "section": r[1],
            "text": r[2],
            "entity_ids": list(r[3] or []),
            "score": float(r[4]),
        }
        for r in rows
    ]


def hnsw_index_exists() -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'idx_chunk_embeddings_hnsw'
                """
            )
            return cur.fetchone() is not None


def verify_pgvector() -> Dict[str, Any]:
    """Connect and confirm pgvector + table (+ entity_ids + HNSW) are ready."""
    with get_connection() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT extname, extversion
                FROM pg_extension
                WHERE extname = 'vector'
                """
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(
                    "pgvector extension not found. "
                    "Ensure postgres service started with docker/postgres/init.sql."
                )

            cur.execute("SELECT version()")
            pg_version = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM chunk_embeddings")
            row_count = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*) FROM chunk_embeddings
                WHERE cardinality(entity_ids) > 0
                """
            )
            linked = cur.fetchone()[0]

    return {
        "postgres_host": settings.POSTGRES_HOST,
        "postgres_db": settings.POSTGRES_DB,
        "pgvector_version": row[1],
        "postgres_version": pg_version,
        "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
        "chunk_embeddings_rows": row_count,
        "rows_with_entity_ids": linked,
        "hnsw_index": hnsw_index_exists(),
    }


def get_existing_hashes(chunk_hashes: List[str]) -> set[str]:
    """Return which chunk_hashes already have embeddings (cache hits)."""
    if not chunk_hashes:
        return set()
    with get_connection() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_hash FROM chunk_embeddings
                WHERE chunk_hash = ANY(%s)
                """,
                (chunk_hashes,),
            )
            return {r[0] for r in cur.fetchall()}


def count_by_ticker(ticker: str) -> int:
    with get_connection() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM chunk_embeddings WHERE ticker = %s",
                (ticker.upper(),),
            )
            return int(cur.fetchone()[0])


def update_entity_ids(chunk_id: str, entity_ids: Sequence[str]) -> None:
    """Set entity_ids for one row (no re-embed)."""
    with get_connection() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chunk_embeddings
                SET entity_ids = %s
                WHERE chunk_id = %s
                """,
                (list(entity_ids), chunk_id),
            )
        conn.commit()


def sample_entity_links(ticker: str, *, limit: int = 5) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_id, section, entity_ids
                FROM chunk_embeddings
                WHERE ticker = %s
                ORDER BY section, chunk_index
                LIMIT %s
                """,
                (ticker.upper(), limit),
            )
            return [
                {
                    "chunk_id": r[0],
                    "section": r[1],
                    "entity_ids": list(r[2] or []),
                    "entity_count": len(r[2] or []),
                }
                for r in cur.fetchall()
            ]


if __name__ == "__main__":
    print(json.dumps(verify_pgvector(), indent=2))
