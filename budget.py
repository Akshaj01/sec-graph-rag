"""
Extraction cost estimation before running a full corpus.

WHY: Claude extraction is billed per token. Re-running uncached chunks across
many 10-Ks can hit hundreds of dollars fast. Always estimate first.

Caching already in place:
  - ingest.py: filing_hash (document identity) → skip re-fetch/re-chunk
  - extractor.py: chunk_hash → skip re-extraction for unchanged text
"""

from __future__ import annotations

import json
import sys
from typing import List, Optional, Sequence

from pydantic import BaseModel, Field

from config import settings
from extractor import ExtractionCache, SYSTEM_PROMPT
from ingest import DocumentChunk, IngestResult, ingest_company


# Conservative Claude Sonnet-ish pricing (USD per 1M tokens). Override in .env.
DEFAULT_INPUT_COST_PER_MTOK = 3.0
DEFAULT_OUTPUT_COST_PER_MTOK = 15.0
DEFAULT_EMBEDDING_COST_PER_MTOK = 0.02

# Worst-case retry multiplier: budget assumes some chunks retry on schema failure.
RETRY_BUFFER = 1.15


class ChunkCostLine(BaseModel):
    chunk_id: str
    section: str
    cached: bool
    est_input_tokens: int
    est_output_tokens: int
    est_cost_usd: float = 0.0


class ExtractionBudget(BaseModel):
    ticker: str
    accession_number: str
    filing_hash: str
    ingest_cache_hit: bool
    total_chunks: int
    chunks_to_extract: int
    chunks_cached: int
    max_chunks_cap: Optional[int] = None
    est_input_tokens: int
    est_output_tokens: int
    est_extraction_usd: float
    est_embedding_usd: float
    est_total_usd: float
    within_budget: bool
    budget_limit_usd: Optional[float] = None
    lines: List[ChunkCostLine] = Field(default_factory=list)


def _chars_to_tokens(char_count: int) -> int:
    return max(1, char_count // settings.CHARS_PER_TOKEN)


def _chunk_input_tokens(chunk: DocumentChunk) -> int:
    """Approximate prompt tokens: system + user wrapper + chunk body."""
    wrapper = (
        f"source_chunk_id (must use exactly this value on every entity and relationship): "
        f"{chunk.chunk_id}\n"
        f"section: {chunk.section}\n"
        f"ticker: {chunk.ticker}\n\n"
        f"CHUNK TEXT:\n"
    )
    return _chars_to_tokens(len(SYSTEM_PROMPT) + len(wrapper) + len(chunk.text))


def _chunk_output_tokens(chunk: DocumentChunk, cache: ExtractionCache) -> int:
    """
    Use cached payload size when available; otherwise budget worst-case max_tokens.
    """
    cached = cache.get(chunk.chunk_hash)
    if cached is not None:
        payload_chars = len(cached.model_dump_json())
        return _chars_to_tokens(payload_chars)
    return settings.EXTRACTION_MAX_TOKENS


def _token_cost(
    input_tokens: int,
    output_tokens: int,
    *,
    input_rate: float,
    output_rate: float,
) -> float:
    return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate


def estimate_extraction_budget(
    ingest_result: IngestResult,
    *,
    max_chunks: Optional[int] = None,
    cache: Optional[ExtractionCache] = None,
    budget_limit_usd: Optional[float] = None,
    input_rate: Optional[float] = None,
    output_rate: Optional[float] = None,
    embedding_rate: Optional[float] = None,
) -> ExtractionBudget:
    """
    Estimate Claude extraction (+ rough embedding) cost for one filing.

    Does NOT call any paid APIs.
    """
    cache = cache or ExtractionCache(settings.EXTRACTION_CACHE_PATH)
    input_rate = (
        settings.EXTRACTION_INPUT_COST_PER_MTOK
        if input_rate is None
        else input_rate
    )
    output_rate = (
        settings.EXTRACTION_OUTPUT_COST_PER_MTOK
        if output_rate is None
        else output_rate
    )
    embedding_rate = (
        settings.EMBEDDING_COST_PER_MTOK
        if embedding_rate is None
        else embedding_rate
    )
    budget_limit_usd = (
        settings.MAX_EXTRACTION_BUDGET_USD
        if budget_limit_usd is None
        else budget_limit_usd
    )

    chunks = ingest_result.chunks
    if max_chunks is not None:
        chunks = chunks[:max_chunks]

    lines: List[ChunkCostLine] = []
    total_in = 0
    total_out = 0
    cached_count = 0

    for chunk in chunks:
        is_cached = cache.get(chunk.chunk_hash) is not None
        if is_cached:
            cached_count += 1

        in_tok = _chunk_input_tokens(chunk)
        out_tok = _chunk_output_tokens(chunk, cache)

        line_cost = 0.0 if is_cached else _token_cost(
            in_tok, out_tok, input_rate=input_rate, output_rate=output_rate
        ) * RETRY_BUFFER

        if not is_cached:
            total_in += in_tok
            total_out += out_tok

        lines.append(
            ChunkCostLine(
                chunk_id=chunk.chunk_id,
                section=chunk.section,
                cached=is_cached,
                est_input_tokens=in_tok,
                est_output_tokens=out_tok,
                est_cost_usd=round(line_cost, 4),
            )
        )

    extraction_usd = _token_cost(
        total_in, total_out, input_rate=input_rate, output_rate=output_rate
    ) * RETRY_BUFFER

    # Rough embedding budget: one small batch per uncached chunk (soft-match reps).
    # Actual Step E cost is usually much lower; this is a padded estimate.
    uncached = len(chunks) - cached_count
    est_embed_tokens = uncached * 500
    embedding_usd = (est_embed_tokens / 1_000_000) * embedding_rate

    total_usd = extraction_usd + embedding_usd
    within = True if budget_limit_usd is None else total_usd <= budget_limit_usd

    return ExtractionBudget(
        ticker=ingest_result.ticker,
        accession_number=ingest_result.accession_number,
        filing_hash=ingest_result.filing_hash,
        ingest_cache_hit=ingest_result.cache_hit,
        total_chunks=len(ingest_result.chunks),
        chunks_to_extract=len(chunks),
        chunks_cached=cached_count,
        max_chunks_cap=max_chunks,
        est_input_tokens=total_in,
        est_output_tokens=total_out,
        est_extraction_usd=round(extraction_usd, 4),
        est_embedding_usd=round(embedding_usd, 4),
        est_total_usd=round(total_usd, 4),
        within_budget=within,
        budget_limit_usd=budget_limit_usd,
        lines=lines,
    )


def estimate_ticker_budget(
    ticker: str,
    *,
    max_chunks: Optional[int] = None,
    force_refresh_ingest: bool = False,
) -> ExtractionBudget:
    ingest_result = ingest_company(ticker, force_refresh=force_refresh_ingest)
    return estimate_extraction_budget(ingest_result, max_chunks=max_chunks)


def estimate_corpus_budget(
    tickers: Sequence[str],
    *,
    max_chunks: Optional[int] = None,
) -> dict:
    """Roll up estimates for multiple tickers (e.g. before a batch job)."""
    rows: List[ExtractionBudget] = []
    for ticker in tickers:
        rows.append(estimate_ticker_budget(ticker, max_chunks=max_chunks))

    total_usd = sum(r.est_total_usd for r in rows)
    total_uncached = sum(r.chunks_to_extract - r.chunks_cached for r in rows)
    return {
        "tickers": len(rows),
        "total_est_usd": round(total_usd, 2),
        "total_uncached_chunks": total_uncached,
        "within_budget": all(r.within_budget for r in rows),
        "filings": [r.model_dump() for r in rows],
    }


def require_budget_confirmation(budget: ExtractionBudget, *, confirmed: bool) -> None:
    """Raise if spend exceeds limit or user has not passed --confirm."""
    if budget.chunks_to_extract == budget.chunks_cached:
        return  # All cached — free.

    if budget.budget_limit_usd is not None and not budget.within_budget:
        raise RuntimeError(
            f"Estimated ${budget.est_total_usd:.2f} exceeds budget limit "
            f"${budget.budget_limit_usd:.2f}. Raise MAX_EXTRACTION_BUDGET_USD or "
            f"reduce scope (max_chunks)."
        )

    if not confirmed and budget.est_total_usd > 0:
        raise RuntimeError(
            f"Estimated spend ${budget.est_total_usd:.2f} for "
            f"{budget.chunks_to_extract - budget.chunks_cached} uncached chunk(s). "
            f"Re-run with --budget to review, then add --confirm to proceed."
        )


if __name__ == "__main__":
    symbols = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not symbols:
        symbols = ["AAPL"]

    run_all = "--all" in sys.argv
    max_chunks = None if run_all else 5
    if "--all-chunks" in sys.argv:
        max_chunks = None

    if len(symbols) == 1:
        report = estimate_ticker_budget(symbols[0], max_chunks=max_chunks)
        print(json.dumps(report.model_dump(), indent=2))
    else:
        print(json.dumps(estimate_corpus_budget(symbols, max_chunks=max_chunks), indent=2))
