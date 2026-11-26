"""
One pinned 10-K per issuer.

The suite's required facts and gold chunk ids were written against these
filings. Ingest fetches the pinned accession, not "latest", and retrieval
drops chunks from any other filing still sitting in the stores. Moving an
issuer to a newer 10-K is a deliberate suite change: update the pin and the
gold answers together, then re-run the benchmark.

WHY: ingest used to take the latest 10-K. Restoring Apple after Nov 3, 2026
pulled the fiscal 2026 filing next to the fiscal 2025 one, so answers could mix
years and cite products the gold answers never mention.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, List, Optional

PINNED_10K: Dict[str, str] = {
    "AAPL": "0000320193-25-000079",
    "AMZN": "0001018724-26-000004",
    "GOOGL": "0001652044-26-000018",
    "JNJ": "0000200406-26-000016",
    "JPM": "0001628280-26-008131",
    "META": "0001628280-26-003942",
    "MSFT": "0001193125-26-323660",
    "NFLX": "0001065280-26-000034",
    "NVDA": "0001045810-26-000021",
    "XOM": "0000034088-26-000045",
}

PINNED_ACCESSIONS: FrozenSet[str] = frozenset(PINNED_10K.values())


def pinned_accession(ticker: str) -> Optional[str]:
    return PINNED_10K.get((ticker or "").upper())


def accession_of(chunk_id: str) -> Optional[str]:
    """chunk_id shape: {accession_number}:{section}:{index}."""
    if not chunk_id or ":" not in chunk_id:
        return None
    return chunk_id.split(":", 1)[0]


def is_pinned_chunk(chunk_id: str) -> bool:
    return accession_of(chunk_id) in PINNED_ACCESSIONS


def keep_pinned(chunk_ids: Iterable[str]) -> List[str]:
    """Drop chunk ids that come from an unpinned filing. Order is kept."""
    return [c for c in chunk_ids if c and is_pinned_chunk(c)]
