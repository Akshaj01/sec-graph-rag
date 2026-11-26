"""Free unit tests for the one-10-K-per-issuer pin (no EDGAR, no stores)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from graph_retriever import GraphFact, filter_facts_to_pinned
from ingest import select_pinned_filing
from pinned_filings import PINNED_10K, is_pinned_chunk, keep_pinned

AAPL_FY25 = "0000320193-25-000079"
AAPL_FY26 = "0000320193-26-000026"


def test_apple_is_pinned_to_the_filing_its_gold_answers_use():
    assert PINNED_10K["AAPL"] == AAPL_FY25


def test_keep_pinned_drops_other_years_and_keeps_order():
    ids = [f"{AAPL_FY26}:Item1:0", f"{AAPL_FY25}:Item1:0", f"{AAPL_FY25}:Item7:2"]
    assert keep_pinned(ids) == [f"{AAPL_FY25}:Item1:0", f"{AAPL_FY25}:Item7:2"]
    assert not is_pinned_chunk(f"{AAPL_FY26}:Item1:0")
    assert not is_pinned_chunk("not-a-chunk-id")


def _filing(accession: str, date: str) -> SimpleNamespace:
    return SimpleNamespace(accession_number=accession, filing_date=date)


def test_select_pinned_filing_ignores_a_newer_filing():
    filings = [_filing(AAPL_FY26, "2026-11-03"), _filing(AAPL_FY25, "2025-10-31")]
    assert select_pinned_filing("aapl", filings).accession_number == AAPL_FY25


def test_select_pinned_filing_refuses_an_unpinned_ticker():
    with pytest.raises(ValueError, match="no pinned 10-K"):
        select_pinned_filing("TSLA", [_filing("0001318605-26-000001", "2026-01-29")])


def test_select_pinned_filing_errors_when_the_pin_is_missing_from_edgar():
    with pytest.raises(ValueError, match="was not in EDGAR"):
        select_pinned_filing("AAPL", [_filing(AAPL_FY26, "2026-11-03")])


def _fact(target: str, chunk_ids: list[str]) -> GraphFact:
    return GraphFact(
        source_id="APPLE",
        source_name="Apple Inc.",
        rel_type="PRODUCES_PRODUCT",
        target_id=target,
        target_name=target,
        source_chunk_ids=chunk_ids,
    )


def test_graph_facts_keep_only_pinned_provenance():
    facts = [
        _fact("AAPL_IPHONE", [f"{AAPL_FY26}:Item1:0", f"{AAPL_FY25}:Item1:0"]),
        _fact("AAPL_MACBOOK_NEO", [f"{AAPL_FY26}:Item1:0"]),
        _fact("AAPL_NO_PROVENANCE", []),
    ]
    kept = filter_facts_to_pinned(facts)
    assert [f.target_id for f in kept] == ["AAPL_IPHONE", "AAPL_NO_PROVENANCE"]
    assert kept[0].source_chunk_ids == [f"{AAPL_FY25}:Item1:0"]
