"""
Batch corpus growth: ingest + extract + resolve + Neo4j write + pgvector embed
for multiple tickers in one run, instead of the one-ticker-at-a-time dance in
HANDOFF.md's "Windows quick commands".

Reuses every existing Step (C-J) unchanged — this only adds an outer loop,
an aggregate budget gate before any spend, and a per-ticker error boundary so
one bad ticker (no 10-K, nonstandard filing structure) doesn't kill the batch.

Usage:
    python grow_corpus.py MSFT JPM XOM --budget            # estimate only, no spend
    python grow_corpus.py MSFT JPM XOM --confirm            # full filings, real spend
    python grow_corpus.py MSFT --confirm --max-chunks 5     # cheap smoke test
    python grow_corpus.py MSFT JPM --confirm --skip-embed   # graph only
    python grow_corpus.py MSFT JPM --confirm --max-total-usd 20

WHY full filings by default (unlike the per-file scripts' --all flag): this
tool exists specifically to grow the corpus past smoke scale, so a 5-chunk
cap would defeat the point. Pass --max-chunks to cap it for a cheap test run.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from budget import estimate_corpus_budget
from config import settings
from embedder import embed_company
from graph_writer import write_company


class TickerGrowthResult(BaseModel):
    ticker: str
    status: str  # "ok" | "error"
    accession_number: Optional[str] = None
    entities_merged: Optional[int] = None
    relationships_merged: Optional[int] = None
    chunks_embedded: Optional[int] = None
    chunks_entity_linked: Optional[int] = None
    error: Optional[str] = None


class CorpusGrowthReport(BaseModel):
    run_at: str
    tickers: List[str]
    max_chunks: Optional[int]
    est_total_usd: float
    skip_embed: bool
    results: List[TickerGrowthResult] = Field(default_factory=list)
    companies_ok: int = 0
    companies_failed: int = 0
    total_entities_merged: int = 0
    total_relationships_merged: int = 0
    total_chunks_embedded: int = 0


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def grow_corpus(
    tickers: List[str],
    *,
    max_chunks: Optional[int] = None,
    skip_embed: bool = False,
    link_only: bool = False,
) -> CorpusGrowthReport:
    """Write + embed each ticker; never raises on a single ticker's failure."""
    results: List[TickerGrowthResult] = []

    for ticker in tickers:
        try:
            write_result = write_company(
                ticker,
                max_chunks=max_chunks,
                confirm=True,
                skip_budget_check=True,  # already gated at the aggregate level in main()
            )
            write_stats = write_result["write"]

            embedded = None
            linked = None
            if not skip_embed:
                embed_stats = embed_company(
                    ticker, max_chunks=max_chunks, link_only=link_only
                )
                embedded = embed_stats.chunks_embedded
                linked = embed_stats.chunks_entity_linked

            results.append(
                TickerGrowthResult(
                    ticker=ticker,
                    status="ok",
                    accession_number=write_stats.get("accession_number"),
                    entities_merged=write_stats.get("entities_merged"),
                    relationships_merged=write_stats.get("relationships_merged"),
                    chunks_embedded=embedded,
                    chunks_entity_linked=linked,
                )
            )
        except Exception as exc:  # noqa: BLE001 - one ticker's failure must not kill the batch
            results.append(
                TickerGrowthResult(ticker=ticker, status="error", error=str(exc))
            )

    ok = [r for r in results if r.status == "ok"]
    failed = [r for r in results if r.status == "error"]

    return CorpusGrowthReport(
        run_at=_utc_stamp(),
        tickers=tickers,
        max_chunks=max_chunks,
        est_total_usd=0.0,  # filled in by main() from the pre-run budget estimate
        skip_embed=skip_embed,
        results=results,
        companies_ok=len(ok),
        companies_failed=len(failed),
        total_entities_merged=sum(r.entities_merged or 0 for r in ok),
        total_relationships_merged=sum(r.relationships_merged or 0 for r in ok),
        total_chunks_embedded=sum(r.chunks_embedded or 0 for r in ok),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="+", help="Tickers to add, e.g. MSFT JPM XOM")
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Cap chunks per ticker (default: full filing, all Item 1/1A/7 chunks)",
    )
    parser.add_argument(
        "--max-total-usd",
        type=float,
        default=None,
        help="Abort before spending anything if the aggregate estimate exceeds this",
    )
    parser.add_argument(
        "--confirm", action="store_true", help="Actually spend (Claude + OpenAI). Omit for a dry-run estimate."
    )
    parser.add_argument(
        "--budget", action="store_true", help="Print the aggregate estimate and exit (same as omitting --confirm)"
    )
    parser.add_argument(
        "--skip-embed", action="store_true", help="Write to Neo4j only; skip pgvector embedding"
    )
    parser.add_argument(
        "--link-only",
        action="store_true",
        help="Embed step only relinks entity_ids from cache; no OpenAI embedding calls",
    )
    args = parser.parse_args()

    tickers = sorted({t.upper() for t in args.tickers})

    budget = estimate_corpus_budget(tickers, max_chunks=args.max_chunks)
    print(json.dumps(budget, indent=2))

    if args.budget or not args.confirm:
        print(
            f"\nDry run only (no spend). Estimated ${budget['total_est_usd']:.2f} "
            f"across {len(tickers)} ticker(s). Re-run with --confirm to proceed.",
            file=sys.stderr,
        )
        return

    if not budget["within_budget"]:
        print(
            f"\nAborting: one or more tickers exceed MAX_EXTRACTION_BUDGET_USD "
            f"(${settings.MAX_EXTRACTION_BUDGET_USD}). Raise it in .env or reduce --max-chunks.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.max_total_usd is not None and budget["total_est_usd"] > args.max_total_usd:
        print(
            f"\nAborting: estimated ${budget['total_est_usd']:.2f} exceeds "
            f"--max-total-usd {args.max_total_usd:.2f}. Nothing was spent.",
            file=sys.stderr,
        )
        sys.exit(1)

    report = grow_corpus(
        tickers,
        max_chunks=args.max_chunks,
        skip_embed=args.skip_embed,
        link_only=args.link_only,
    )
    report.est_total_usd = budget["total_est_usd"]

    out_dir = Path("./data")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"corpus_growth_{report.run_at}.json"
    out_path.write_text(json.dumps(report.model_dump(), indent=2))

    print("\n" + json.dumps(report.model_dump(), indent=2))
    print(f"\nReport saved to {out_path}", file=sys.stderr)
    if report.companies_failed:
        print(
            f"{report.companies_failed} ticker(s) failed — see 'error' fields above.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
