"""Unit tests for cross-issuer graph leak fixes (no API / no Neo4j)."""

from __future__ import annotations

from chunk_ticker import accession_from_chunk_id, filter_chunk_ids_for_ticker
from graph_retriever import GraphFact, filter_facts_for_ticker
from graph_writer import should_skip_issuer_owned_edge
from resolver import CanonicalEntity, ResolvedRelationship
from schemas import EntityType, RelationshipType


def _company(eid: str, *, is_issuer: bool = False) -> CanonicalEntity:
    return CanonicalEntity(
        id=eid,
        type=EntityType.COMPANY,
        name=eid.title(),
        aliases=[eid],
        source_chunk_ids=["c0"],
        confidence=0.9,
        mention_count=1,
        is_issuer=is_issuer,
    )


def test_skip_produces_from_non_issuer_company():
    entities = {
        "APPLE": _company("APPLE", is_issuer=False),
        "META": _company("META", is_issuer=True),
    }
    rel = ResolvedRelationship(
        source_entity_id="APPLE",
        target_entity_id="META_IOS",
        type=RelationshipType.PRODUCES_PRODUCT,
        source_chunk_ids=["0001628280-26-003942:Item1A:2"],
        confidence=0.8,
    )
    assert should_skip_issuer_owned_edge(rel, entities) is True


def test_allow_produces_from_issuer_company():
    entities = {
        "APPLE": _company("APPLE", is_issuer=True),
    }
    rel = ResolvedRelationship(
        source_entity_id="APPLE",
        target_entity_id="AAPL_IPHONE",
        type=RelationshipType.PRODUCES_PRODUCT,
        source_chunk_ids=["0000320193-25-000079:Item1:0"],
        confidence=0.9,
    )
    assert should_skip_issuer_owned_edge(rel, entities) is False


def test_allow_competes_with_from_non_issuer():
    """COMPETES_WITH is not issuer-owned; Meta may assert competition with Apple."""
    entities = {
        "META": _company("META", is_issuer=True),
        "APPLE": _company("APPLE", is_issuer=False),
    }
    rel = ResolvedRelationship(
        source_entity_id="APPLE",
        target_entity_id="META",
        type=RelationshipType.COMPETES_WITH,
        source_chunk_ids=["0001628280-26-003942:Item1:0"],
        confidence=0.7,
    )
    assert should_skip_issuer_owned_edge(rel, entities) is False


def test_accession_from_chunk_id():
    assert (
        accession_from_chunk_id("0001628280-26-003942:Item1A:2")
        == "0001628280-26-003942"
    )
    assert accession_from_chunk_id("nope") is None


def test_filter_chunk_ids_drops_known_foreign(monkeypatch=None):
    # Avoid depending on live SQLite: patch ticker_for_chunk_id via mapping.
    import chunk_ticker as ct

    mapping = {
        "0000320193-25-000079:Item1:0": "AAPL",
        "0001628280-26-003942:Item1A:2": "META",
    }

    original = ct.ticker_for_chunk_id

    def _fake(cid: str):
        return mapping.get(cid)

    ct.ticker_for_chunk_id = _fake  # type: ignore[assignment]
    try:
        kept = filter_chunk_ids_for_ticker(
            [
                "0000320193-25-000079:Item1:0",
                "0001628280-26-003942:Item1A:2",
            ],
            "AAPL",
        )
        assert kept == ["0000320193-25-000079:Item1:0"]
    finally:
        ct.ticker_for_chunk_id = original  # type: ignore[assignment]


def test_filter_facts_for_ticker_drops_meta_only_fact():
    import chunk_ticker as ct

    mapping = {
        "0000320193-25-000079:Item1:0": "AAPL",
        "0001628280-26-003942:Item1A:2": "META",
    }
    original = ct.ticker_for_chunk_id
    ct.ticker_for_chunk_id = lambda cid: mapping.get(cid)  # type: ignore[assignment]
    try:
        facts = [
            GraphFact(
                source_id="APPLE",
                source_name="Apple",
                rel_type="PRODUCES_PRODUCT",
                target_id="META_IOS",
                target_name="iOS",
                source_chunk_ids=["0001628280-26-003942:Item1A:2"],
            ),
            GraphFact(
                source_id="APPLE",
                source_name="Apple",
                rel_type="PRODUCES_PRODUCT",
                target_id="AAPL_IPHONE",
                target_name="iPhone",
                source_chunk_ids=[
                    "0000320193-25-000079:Item1:0",
                    "0001628280-26-003942:Item1A:2",
                ],
            ),
            GraphFact(
                source_id="APPLE",
                source_name="Apple",
                rel_type="COMPETES_WITH",
                target_id="META",
                target_name="Meta",
                source_chunk_ids=["0001628280-26-003942:Item1A:2"],
            ),
        ]
        filtered = filter_facts_for_ticker(facts, "AAPL")
        assert [f.target_id for f in filtered] == ["AAPL_IPHONE", "META"]
        iphone = next(f for f in filtered if f.target_id == "AAPL_IPHONE")
        assert iphone.source_chunk_ids == ["0000320193-25-000079:Item1:0"]
        # Cross-company COMPETES_WITH keeps Meta-filing provenance.
        meta = next(f for f in filtered if f.target_id == "META")
        assert meta.source_chunk_ids == ["0001628280-26-003942:Item1A:2"]
    finally:
        ct.ticker_for_chunk_id = original  # type: ignore[assignment]


def test_filter_keeps_competes_with_foreign_chunks_only():
    import chunk_ticker as ct

    original = ct.ticker_for_chunk_id
    ct.ticker_for_chunk_id = lambda cid: {  # type: ignore[assignment]
        "0001628280-26-003942:Item1A:2": "META",
    }.get(cid)
    try:
        facts = [
            GraphFact(
                source_id="APPLE",
                source_name="Apple",
                rel_type="COMPETES_WITH",
                target_id="META",
                target_name="Meta",
                source_chunk_ids=["0001628280-26-003942:Item1A:2"],
            )
        ]
        filtered = filter_facts_for_ticker(facts, "AAPL")
        assert len(filtered) == 1
        assert filtered[0].target_id == "META"
    finally:
        ct.ticker_for_chunk_id = original  # type: ignore[assignment]
