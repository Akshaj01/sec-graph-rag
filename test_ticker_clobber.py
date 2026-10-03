"""Unit tests for issuer marking + global-entity ticker accumulation helpers."""

from __future__ import annotations

from resolver import CanonicalEntity, mark_issuer_company
from schemas import EntityType
from graph_writer import _uniq_append


def _company(eid: str, name: str, mentions: int, conf: float = 0.9) -> CanonicalEntity:
    return CanonicalEntity(
        id=eid,
        type=EntityType.COMPANY,
        name=name,
        aliases=[name],
        description=None,
        source_chunk_ids=[f"c{i}" for i in range(mentions)],
        confidence=conf,
        mention_count=mentions,
    )


def test_mark_issuer_picks_highest_mention_company():
    entities = [
        _company("IRS", "Internal Revenue Service", 1),
        _company("APPLE", "Apple Inc.", 11),
        _company("GOOGLE", "Google LLC", 2),
        CanonicalEntity(
            id="AAPL_IPHONE",
            type=EntityType.PRODUCT_LINE,
            name="iPhone",
            aliases=["iPhone"],
            source_chunk_ids=["c0"],
            confidence=0.9,
            mention_count=3,
        ),
    ]
    issuer_id = mark_issuer_company(entities)
    assert issuer_id == "APPLE"
    assert [e.id for e in entities if e.is_issuer] == ["APPLE"]
    assert not any(e.is_issuer for e in entities if e.id != "APPLE")


def test_mark_issuer_noop_without_companies():
    entities = [
        CanonicalEntity(
            id="AAPL_IPHONE",
            type=EntityType.PRODUCT_LINE,
            name="iPhone",
            aliases=["iPhone"],
            source_chunk_ids=["c0"],
            confidence=0.9,
            mention_count=3,
        ),
    ]
    assert mark_issuer_company(entities) is None
    assert all(not e.is_issuer for e in entities)


def test_uniq_append_dedupes():
    assert _uniq_append(["AAPL"], "NFLX") == ["AAPL", "NFLX"]
    assert _uniq_append(["AAPL", "NFLX"], "NFLX") == ["AAPL", "NFLX"]
    assert _uniq_append([], None) == []
    assert _uniq_append([], "AAPL") == ["AAPL"]
