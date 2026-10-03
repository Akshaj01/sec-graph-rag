"""
Map chunk_id → filing ticker for retrieve-time issuer filters.

chunk_id shape: {accession_number}:{section}:{index}
Lookups prefer the local ingest SQLite cache, then pgvector metadata.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from config import settings


def accession_from_chunk_id(chunk_id: str) -> Optional[str]:
    if not chunk_id or ":" not in chunk_id:
        return None
    return chunk_id.split(":", 1)[0]


@lru_cache(maxsize=1)
def _sqlite_chunk_tickers() -> Dict[str, str]:
    path = Path(settings.INGEST_CACHE_PATH)
    if not path.exists():
        return {}
    out: Dict[str, str] = {}
    try:
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT chunk_id, ticker FROM chunks WHERE ticker IS NOT NULL"
            ).fetchall()
            for chunk_id, ticker in rows:
                if chunk_id and ticker:
                    out[str(chunk_id)] = str(ticker).upper()
    except sqlite3.Error:
        return {}
    return out


@lru_cache(maxsize=1)
def _sqlite_accession_tickers() -> Dict[str, str]:
    path = Path(settings.INGEST_CACHE_PATH)
    if not path.exists():
        return {}
    out: Dict[str, str] = {}
    try:
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT accession_number, ticker
                FROM chunks
                WHERE accession_number IS NOT NULL AND ticker IS NOT NULL
                """
            ).fetchall()
            for accession, ticker in rows:
                if accession and ticker:
                    out[str(accession)] = str(ticker).upper()
    except sqlite3.Error:
        return {}
    return out


def _pgvector_tickers(chunk_ids: Sequence[str]) -> Dict[str, str]:
    missing = [c for c in chunk_ids if c]
    if not missing:
        return {}
    try:
        from vector_db import get_connection
    except Exception:
        return {}
    out: Dict[str, str] = {}
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT chunk_id, ticker
                    FROM chunk_embeddings
                    WHERE chunk_id = ANY(%s)
                    """,
                    (list(missing),),
                )
                for chunk_id, ticker in cur.fetchall():
                    if chunk_id and ticker:
                        out[str(chunk_id)] = str(ticker).upper()
    except Exception:
        return {}
    return out


def ticker_for_chunk_id(chunk_id: str) -> Optional[str]:
    """Return uppercase ticker for a chunk, or None if unknown."""
    if not chunk_id:
        return None
    by_id = _sqlite_chunk_tickers()
    if chunk_id in by_id:
        return by_id[chunk_id]
    accession = accession_from_chunk_id(chunk_id)
    if accession:
        by_acc = _sqlite_accession_tickers()
        if accession in by_acc:
            return by_acc[accession]
    pg = _pgvector_tickers([chunk_id])
    return pg.get(chunk_id)


def filter_chunk_ids_for_ticker(
    chunk_ids: Iterable[str],
    ticker: Optional[str],
) -> List[str]:
    """
    Keep chunks belonging to `ticker`. Unknown chunks are kept (cannot prove foreign).
    When ticker is None/empty, return all ids unchanged.
    """
    ids = [str(c) for c in chunk_ids if c]
    if not ticker:
        return ids
    want = ticker.upper().strip()
    if not want:
        return ids

    # Batch-warm pgvector for unknowns.
    unknown = [c for c in ids if ticker_for_chunk_id(c) is None]
    if unknown:
        _pgvector_tickers(unknown)

    kept: List[str] = []
    for cid in ids:
        owner = ticker_for_chunk_id(cid)
        if owner is None or owner == want:
            kept.append(cid)
    return kept


def clear_chunk_ticker_caches() -> None:
    _sqlite_chunk_tickers.cache_clear()
    _sqlite_accession_tickers.cache_clear()
