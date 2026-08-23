"""
Step C: SEC 10-K fetching, section-aware chunking, and SQLite hash caching.

Pipeline:
  ticker -> fetch latest 10-K (Item 1, 1A, 7) -> hash content ->
  return cached chunks OR chunk + persist -> list[DocumentChunk]

Out of scope: LLM extraction (Step D), Neo4j writes (Step F).
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from edgar import Company, set_identity
from pydantic import BaseModel, Field

from config import settings

# Locked Step C scope: highest signal sections for our closed-world ontology.
TARGET_SECTIONS: Dict[str, str] = {
    "Item1": "business",
    "Item1A": "risk_factors",
    "Item7": "management_discussion",
}


class DocumentChunk(BaseModel):
    """One LLM-ready piece of a 10-K section. chunk_id is the citation key for later steps."""

    chunk_id: str = Field(..., description="Stable id: {accession}:{section}:{index}")
    ticker: str
    cik: str
    accession_number: str
    filing_date: str
    section: str = Field(..., description="Item1 | Item1A | Item7")
    chunk_index: int
    text: str
    chunk_hash: str = Field(..., description="SHA-256 of this chunk's text")
    filing_hash: str = Field(..., description="SHA-256 of all selected section text for this filing")


class IngestResult(BaseModel):
    ticker: str
    cik: str
    accession_number: str
    filing_date: str
    filing_hash: str
    cache_hit: bool
    chunks: List[DocumentChunk]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _section_to_text(value: object) -> str:
    """Normalize edgartools section objects into plain text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    text_fn = getattr(value, "text", None)
    if callable(text_fn):
        return str(text_fn()).strip()
    return str(value).strip()


def _chunk_text(text: str, chunk_size_chars: int, overlap_chars: int) -> List[str]:
    """
    Sliding-window chunker with overlap.

    WHY overlap: an entity/relationship straddling a boundary still appears
    fully in at least one chunk, which protects extraction quality in Step D.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    if len(text) <= chunk_size_chars:
        return [text]

    chunks: List[str] = []
    start = 0
    step = max(chunk_size_chars - overlap_chars, 1)
    while start < len(text):
        end = start + chunk_size_chars
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start += step
    return chunks


class IngestCache:
    """SQLite content-addressable cache keyed by filing_hash."""

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
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS filings (
                    filing_hash TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    cik TEXT NOT NULL,
                    accession_number TEXT NOT NULL,
                    filing_date TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    filing_hash TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    cik TEXT NOT NULL,
                    accession_number TEXT NOT NULL,
                    filing_date TEXT NOT NULL,
                    section TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    chunk_hash TEXT NOT NULL,
                    FOREIGN KEY (filing_hash) REFERENCES filings(filing_hash)
                );

                CREATE INDEX IF NOT EXISTS idx_chunks_filing_hash
                    ON chunks(filing_hash);
                """
            )

    def get_chunks_by_filing_hash(self, filing_hash: str) -> Optional[List[DocumentChunk]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, ticker, cik, accession_number, filing_date,
                       section, chunk_index, text, chunk_hash, filing_hash
                FROM chunks
                WHERE filing_hash = ?
                ORDER BY section, chunk_index
                """,
                (filing_hash,),
            ).fetchall()
        if not rows:
            return None
        return [DocumentChunk(**dict(row)) for row in rows]

    def save_ingest(
        self,
        *,
        filing_hash: str,
        ticker: str,
        cik: str,
        accession_number: str,
        filing_date: str,
        chunks: List[DocumentChunk],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO filings
                    (filing_hash, ticker, cik, accession_number, filing_date, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (filing_hash, ticker, cik, accession_number, filing_date, _utc_now()),
            )
            # Drop any prior rows for this accession OR this hash.
            # WHY: chunk_id is accession-based; a re-chunk with a new filing_hash
            # would otherwise collide with leftover rows from the old hash.
            conn.execute(
                "DELETE FROM chunks WHERE filing_hash = ? OR accession_number = ?",
                (filing_hash, accession_number),
            )
            conn.executemany(
                """
                INSERT INTO chunks (
                    chunk_id, filing_hash, ticker, cik, accession_number, filing_date,
                    section, chunk_index, text, chunk_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        c.chunk_id,
                        c.filing_hash,
                        c.ticker,
                        c.cik,
                        c.accession_number,
                        c.filing_date,
                        c.section,
                        c.chunk_index,
                        c.text,
                        c.chunk_hash,
                    )
                    for c in chunks
                ],
            )


def fetch_10k_sections(ticker: str) -> Tuple[dict, Dict[str, str]]:
    """
    Fetch the latest 10-K and return metadata + selected section text.

    Returns:
        meta: ticker/cik/accession/filing_date
        sections: { "Item1": "...", "Item1A": "...", "Item7": "..." }
    """
    set_identity(settings.USER_AGENT_EMAIL)

    company = Company(ticker)
    filings = company.get_filings(form="10-K")
    if filings is None or len(filings) == 0:
        raise ValueError(f"No 10-K filings found for ticker={ticker}")

    filing = filings[0]
    tenk = filing.obj()

    sections: Dict[str, str] = {}
    for section_name, attr_name in TARGET_SECTIONS.items():
        raw = getattr(tenk, attr_name, None)
        if raw is None:
            # Fallback to bracket access used by some edgartools versions
            item_key = {
                "Item1": "Item 1",
                "Item1A": "Item 1A",
                "Item7": "Item 7",
            }[section_name]
            try:
                raw = tenk[item_key]
            except Exception:
                raw = None
        text = _section_to_text(raw)
        if text:
            sections[section_name] = text

    if not sections:
        raise ValueError(
            f"Could not extract Item 1 / 1A / 7 text for ticker={ticker}. "
            "The filing may use a nonstandard structure."
        )

    cik = str(getattr(company, "cik", "") or getattr(filing, "cik", ""))
    accession = str(getattr(filing, "accession_number", "") or "")
    filing_date = str(getattr(filing, "filing_date", "") or "")

    meta = {
        "ticker": ticker.upper(),
        "cik": cik,
        "accession_number": accession,
        "filing_date": filing_date,
    }
    return meta, sections


def build_chunks_from_sections(
    *,
    meta: dict,
    sections: Dict[str, str],
    filing_hash: str,
) -> List[DocumentChunk]:
    chunk_size_chars = settings.CHUNK_SIZE_TOKENS * settings.CHARS_PER_TOKEN
    overlap_chars = settings.CHUNK_OVERLAP_TOKENS * settings.CHARS_PER_TOKEN

    chunks: List[DocumentChunk] = []
    for section_name, section_text in sections.items():
        pieces = _chunk_text(section_text, chunk_size_chars, overlap_chars)
        for idx, piece in enumerate(pieces):
            chunk_id = f"{meta['accession_number']}:{section_name}:{idx}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    ticker=meta["ticker"],
                    cik=meta["cik"],
                    accession_number=meta["accession_number"],
                    filing_date=meta["filing_date"],
                    section=section_name,
                    chunk_index=idx,
                    text=piece,
                    chunk_hash=_sha256(piece),
                    filing_hash=filing_hash,
                )
            )
    return chunks


def ingest_company(ticker: str, *, force_refresh: bool = False) -> IngestResult:
    """
    Main Step C entrypoint.

    1) Fetch Item 1 / 1A / 7 from the latest 10-K
    2) Hash concatenated section text (document identity)
    3) On cache hit, return stored chunks (no re-chunk)
    4) On miss, chunk + persist + return
    """
    cache = IngestCache(settings.INGEST_CACHE_PATH)
    meta, sections = fetch_10k_sections(ticker)

    # Document hash = hash of selected corpus only (not the full filing).
    # WHY: if we later add Item 10, the hash changes and we correctly re-chunk.
    joined = "\n\n".join(f"## {name}\n{text}" for name, text in sections.items())
    filing_hash = _sha256(joined)

    if not force_refresh:
        cached = cache.get_chunks_by_filing_hash(filing_hash)
        if cached is not None:
            return IngestResult(
                ticker=meta["ticker"],
                cik=meta["cik"],
                accession_number=meta["accession_number"],
                filing_date=meta["filing_date"],
                filing_hash=filing_hash,
                cache_hit=True,
                chunks=cached,
            )

    chunks = build_chunks_from_sections(meta=meta, sections=sections, filing_hash=filing_hash)
    cache.save_ingest(
        filing_hash=filing_hash,
        ticker=meta["ticker"],
        cik=meta["cik"],
        accession_number=meta["accession_number"],
        filing_date=meta["filing_date"],
        chunks=chunks,
    )

    return IngestResult(
        ticker=meta["ticker"],
        cik=meta["cik"],
        accession_number=meta["accession_number"],
        filing_date=meta["filing_date"],
        filing_hash=filing_hash,
        cache_hit=False,
        chunks=chunks,
    )


if __name__ == "__main__":
    import json
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    result = ingest_company(symbol)
    preview = {
        "ticker": result.ticker,
        "accession_number": result.accession_number,
        "filing_date": result.filing_date,
        "filing_hash": result.filing_hash,
        "cache_hit": result.cache_hit,
        "num_chunks": len(result.chunks),
        "sections": sorted({c.section for c in result.chunks}),
        "sample_chunk_ids": [c.chunk_id for c in result.chunks[:5]],
    }
    print(json.dumps(preview, indent=2))
