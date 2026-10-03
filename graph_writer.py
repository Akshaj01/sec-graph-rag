"""
Step F: Idempotent Neo4j Cypher writes.

Takes a ResolvedGraph from resolver.py and MERGE-writes nodes + relationships.
Re-running the same ticker must not duplicate canonical entities or edges.

BASWE requirements covered here:
  - MERGE (not CREATE)
  - source_chunk_ids on edges for citation provenance
  - uniqueness constraints on entity id per label

Global entities (Company/Subsidiary/Supplier) share one node across filings.
Their provenance is multi-valued (`tickers` list); `home_ticker` is set only
when the filing issuer writes that Company, so a competitor mention cannot
clobber Apple's identity to NFLX.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from neo4j import GraphDatabase, Driver
from pydantic import BaseModel

from config import settings
from resolver import (
    GLOBAL_ENTITY_TYPES,
    ResolvedGraph,
    resolve_company,
)
from schemas import EntityType, RelationshipType

# Allowlists only — used to safely interpolate labels / rel types into Cypher.
_ENTITY_LABELS: Set[str] = {e.value for e in EntityType}
_REL_TYPES: Set[str] = {r.value for r in RelationshipType}

# Outgoing edges that assert the *filing issuer's* business. A competitor
# mention must not invent PRODUCES_PRODUCT / risks / etc. on global Company APPLE.
ISSUER_OWNED_REL_TYPES: Set[RelationshipType] = {
    RelationshipType.PRODUCES_PRODUCT,
    RelationshipType.EXPOSED_TO_RISK,
    RelationshipType.LED_BY,
    RelationshipType.OWNS_SUBSIDIARY,
    RelationshipType.OPERATES_IN_SEGMENT,
}


class WriteStats(BaseModel):
    entities_merged: int = 0
    relationships_merged: int = 0
    relationships_skipped: int = 0
    constraints_ensured: int = 0
    ticker: Optional[str] = None
    accession_number: Optional[str] = None


def get_driver() -> Driver:
    return GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
    )


def ensure_constraints(driver: Driver) -> int:
    """
    Create uniqueness constraints so id cannot double-insert under races/bugs.

    WHY IF NOT EXISTS: safe to call on every write_company run.
    """
    ensured = 0
    with driver.session() as session:
        for label in sorted(_ENTITY_LABELS):
            # Constraint names must be unique; include label.
            name = f"entity_id_{label.lower()}"
            cypher = (
                f"CREATE CONSTRAINT {name} IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.id IS UNIQUE"
            )
            session.run(cypher)
            ensured += 1
    return ensured


def _uniq_append(values: List[str], item: Optional[str]) -> List[str]:
    out = list(values)
    if item and item not in out:
        out.append(item)
    return out


def _merge_scoped_entity(
    tx, entity, *, ticker: Optional[str], accession_number: Optional[str]
) -> None:
    """Ticker-scoped types: node belongs to one filing company; replace props."""
    label = entity.type.value
    cypher = f"""
    MERGE (n:{label} {{id: $id}})
    SET n.name = $name,
        n.aliases = $aliases,
        n.description = $description,
        n.confidence = $confidence,
        n.mention_count = $mention_count,
        n.source_chunk_ids = $source_chunk_ids,
        n.ticker = $ticker,
        n.accession_number = $accession_number,
        n.updated_at = datetime()
    """
    tx.run(
        cypher,
        id=entity.id,
        name=entity.name,
        aliases=entity.aliases,
        description=entity.description,
        confidence=entity.confidence,
        mention_count=entity.mention_count,
        source_chunk_ids=entity.source_chunk_ids,
        ticker=ticker,
        accession_number=accession_number,
    )


def _merge_global_entity(
    tx, entity, *, ticker: Optional[str], accession_number: Optional[str]
) -> None:
    """
    Globally deduped types: accumulate filing tickers; pin home_ticker on issuer.

    Idempotent across re-runs of the same ticker because source_chunk_ids are
    unioned (re-adding the same chunks is a no-op) and tickers are de-duped.
    """
    label = entity.type.value
    is_issuer = bool(entity.is_issuer and entity.type == EntityType.COMPANY)

    row = tx.run(
        f"MATCH (n:{label} {{id: $id}}) RETURN n AS n",
        id=entity.id,
    ).single()

    if row is None:
        prev_tickers: List[str] = []
        prev_chunks: List[str] = []
        prev_aliases: List[str] = []
        prev_home: Optional[str] = None
        prev_name: Optional[str] = None
        prev_description: Optional[str] = None
        prev_confidence = 0.0
        prev_accession: Optional[str] = None
    else:
        n = row["n"]
        prev_tickers = list(n.get("tickers") or [])
        # Migrate nodes written before tickers[] existed.
        legacy = n.get("ticker")
        if not prev_tickers and legacy:
            prev_tickers = [legacy]
        prev_chunks = list(n.get("source_chunk_ids") or [])
        prev_aliases = list(n.get("aliases") or [])
        prev_home = n.get("home_ticker")
        prev_name = n.get("name")
        prev_description = n.get("description")
        prev_confidence = float(n.get("confidence") or 0.0)
        prev_accession = n.get("accession_number")

    tickers = _uniq_append(prev_tickers, ticker)
    chunks = sorted(set(prev_chunks) | set(entity.source_chunk_ids or []))
    aliases = sorted(set(prev_aliases) | set(entity.aliases or []))

    home_ticker = prev_home
    if entity.type == EntityType.COMPANY:
        if is_issuer and ticker:
            home_ticker = ticker
        legacy_ticker = home_ticker
    else:
        # Subsidiaries/suppliers: never claim an issuer home; keep first ticker.
        home_ticker = None
        if row is not None and row["n"].get("ticker"):
            legacy_ticker = row["n"].get("ticker")
        else:
            legacy_ticker = ticker

    if is_issuer or not prev_name:
        name = entity.name
    else:
        name = prev_name

    if is_issuer and entity.description:
        description = entity.description
    elif entity.description and (
        not prev_description or len(entity.description) > len(prev_description)
    ):
        description = entity.description
    else:
        description = prev_description

    if is_issuer:
        accession = accession_number
    else:
        accession = prev_accession or accession_number

    confidence = max(prev_confidence, float(entity.confidence or 0.0))
    mention_count = len(chunks)

    cypher = f"""
    MERGE (n:{label} {{id: $id}})
    SET n.name = $name,
        n.aliases = $aliases,
        n.description = $description,
        n.confidence = $confidence,
        n.mention_count = $mention_count,
        n.source_chunk_ids = $source_chunk_ids,
        n.tickers = $tickers,
        n.home_ticker = $home_ticker,
        n.ticker = $legacy_ticker,
        n.accession_number = $accession_number,
        n.updated_at = datetime()
    """
    tx.run(
        cypher,
        id=entity.id,
        name=name,
        aliases=aliases,
        description=description,
        confidence=confidence,
        mention_count=mention_count,
        source_chunk_ids=chunks,
        tickers=tickers,
        home_ticker=home_ticker,
        legacy_ticker=legacy_ticker,
        accession_number=accession,
    )


def _merge_entity(
    tx, entity, *, ticker: Optional[str], accession_number: Optional[str]
) -> None:
    label = entity.type.value
    if label not in _ENTITY_LABELS:
        raise ValueError(f"Refusing unknown entity label: {label}")

    if entity.type in GLOBAL_ENTITY_TYPES:
        _merge_global_entity(
            tx, entity, ticker=ticker, accession_number=accession_number
        )
    else:
        _merge_scoped_entity(
            tx, entity, ticker=ticker, accession_number=accession_number
        )


def should_skip_issuer_owned_edge(
    rel,
    entities_by_id: Dict[str, object],
) -> bool:
    """
    Skip issuer-owned edges whose source Company is not this filing's issuer.

    WHY: Meta's 10-K can mention Apple/iOS and extract
    APPLE-[:PRODUCES_PRODUCT]->META_IOS; that must not land on global APPLE.
    Cross-company edges (COMPETES_WITH, SUPPLIED_BY) are still allowed.
    """
    if rel.type not in ISSUER_OWNED_REL_TYPES:
        return False
    src = entities_by_id.get(rel.source_entity_id)
    if src is None:
        return False
    if getattr(src, "type", None) != EntityType.COMPANY:
        return False
    return not bool(getattr(src, "is_issuer", False))


def _merge_relationship(
    tx,
    rel,
    *,
    writing_ticker: Optional[str] = None,
) -> None:
    rel_type = rel.type.value
    if rel_type not in _REL_TYPES:
        raise ValueError(f"Refusing unknown relationship type: {rel_type}")

    row = tx.run(
        f"""
        MATCH (a {{id: $src}})-[r:{rel_type}]->(b {{id: $tgt}})
        RETURN r.source_chunk_ids AS chunks, r.write_tickers AS write_tickers
        """,
        src=rel.source_entity_id,
        tgt=rel.target_entity_id,
    ).single()

    if row is None:
        prev_chunks: List[str] = []
        prev_tickers: List[str] = []
    else:
        prev_chunks = list(row["chunks"] or [])
        prev_tickers = list(row["write_tickers"] or [])

    chunks = sorted(set(prev_chunks) | set(rel.source_chunk_ids or []))
    write_tickers = _uniq_append(prev_tickers, writing_ticker)

    # Endpoints may have different labels; match by id across any ontology label.
    cypher = f"""
    MATCH (a {{id: $src}})
    MATCH (b {{id: $tgt}})
    MERGE (a)-[r:{rel_type}]->(b)
    SET r.confidence = $confidence,
        r.context = $context,
        r.source_chunk_ids = $source_chunk_ids,
        r.write_tickers = $write_tickers,
        r.updated_at = datetime()
    """
    tx.run(
        cypher,
        src=rel.source_entity_id,
        tgt=rel.target_entity_id,
        confidence=rel.confidence,
        context=rel.context,
        source_chunk_ids=chunks,
        write_tickers=write_tickers,
    )


def write_graph(graph: ResolvedGraph, *, driver: Optional[Driver] = None) -> WriteStats:
    """MERGE all canonical entities and relationships into Neo4j."""
    own_driver = driver is None
    driver = driver or get_driver()
    entities_by_id = {e.id: e for e in graph.entities}
    kept_rels = [
        rel
        for rel in graph.relationships
        if not should_skip_issuer_owned_edge(rel, entities_by_id)
    ]
    skipped = len(graph.relationships) - len(kept_rels)
    try:
        constraints = ensure_constraints(driver)
        with driver.session() as session:
            def _write_all(tx):
                for entity in graph.entities:
                    _merge_entity(
                        tx,
                        entity,
                        ticker=graph.ticker,
                        accession_number=graph.accession_number,
                    )
                for rel in kept_rels:
                    _merge_relationship(tx, rel, writing_ticker=graph.ticker)

            session.execute_write(_write_all)

        return WriteStats(
            entities_merged=len(graph.entities),
            relationships_merged=len(kept_rels),
            relationships_skipped=skipped,
            constraints_ensured=constraints,
            ticker=graph.ticker,
            accession_number=graph.accession_number,
        )
    finally:
        if own_driver:
            driver.close()


def cleanup_cross_issuer_edges(
    *,
    driver: Optional[Driver] = None,
) -> Dict[str, int]:
    """
    Delete issuer-owned edges whose target is ticker-scoped to a *different*
    issuer than the source Company's home_ticker (e.g. APPLE→META_IOS).

    Also deletes issuer-owned edges whose write_tickers list is non-empty and
    does not include the source home_ticker (foreign-only provenance).
    """
    own_driver = driver is None
    driver = driver or get_driver()
    # Safe: rel types are from our allowlist constants, not user input.
    rel_union = "|".join(sorted(t.value for t in ISSUER_OWNED_REL_TYPES))
    try:
        with driver.session() as session:
            mismatched = session.run(
                f"""
                MATCH (c:Company)-[r:{rel_union}]->(n)
                WHERE c.home_ticker IS NOT NULL
                  AND n.ticker IS NOT NULL
                  AND n.ticker <> c.home_ticker
                WITH r
                DELETE r
                RETURN count(*) AS deleted
                """
            ).single()
            foreign_write = session.run(
                f"""
                MATCH (c:Company)-[r:{rel_union}]->(n)
                WHERE c.home_ticker IS NOT NULL
                  AND r.write_tickers IS NOT NULL
                  AND size(r.write_tickers) > 0
                  AND NOT c.home_ticker IN r.write_tickers
                WITH r
                DELETE r
                RETURN count(*) AS deleted
                """
            ).single()
            # Product ids prefixed with another ticker (covers nodes without .ticker).
            prefix_leak = session.run(
                f"""
                MATCH (c:Company)-[r:{rel_union}]->(n)
                WHERE c.home_ticker IS NOT NULL
                  AND n.id CONTAINS '_'
                  AND NOT n.id STARTS WITH c.home_ticker + '_'
                  AND any(t IN ['AAPL','AMZN','GOOGL','JNJ','JPM','META','MSFT','NFLX','NVDA','XOM']
                       WHERE n.id STARTS WITH t + '_' AND t <> c.home_ticker)
                WITH r
                DELETE r
                RETURN count(*) AS deleted
                """
            ).single()
        return {
            "deleted_ticker_mismatch": int(mismatched["deleted"] if mismatched else 0),
            "deleted_foreign_write_tickers": int(
                foreign_write["deleted"] if foreign_write else 0
            ),
            "deleted_prefix_leak": int(prefix_leak["deleted"] if prefix_leak else 0),
        }
    finally:
        if own_driver:
            driver.close()


def write_company(
    ticker: str,
    *,
    max_chunks: Optional[int] = None,
    enable_soft_match: Optional[bool] = None,
    confirm: bool = False,
    skip_budget_check: bool = False,
) -> Dict[str, object]:
    """Resolve a company (cached extract when possible), then MERGE into Neo4j."""
    graph = resolve_company(
        ticker,
        max_chunks=max_chunks,
        enable_soft_match=enable_soft_match,
        confirm=confirm,
        skip_budget_check=skip_budget_check,
    )
    stats = write_graph(graph)
    return {
        "write": stats.model_dump(),
        "resolution": graph.stats.model_dump(),
    }


def smoke_counts(driver: Optional[Driver] = None) -> Dict[str, object]:
    """Quick counts for verification after a write."""
    own_driver = driver is None
    driver = driver or get_driver()
    try:
        with driver.session() as session:
            nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            apple = session.run(
                "MATCH (c:Company {id: 'APPLE'}) RETURN c.name AS name, "
                "c.mention_count AS mentions, c.home_ticker AS home_ticker, "
                "c.tickers AS tickers, c.ticker AS ticker, "
                "size(c.source_chunk_ids) AS chunks"
            ).single()
        return {
            "nodes": nodes,
            "relationships": rels,
            "apple_name": apple["name"] if apple else None,
            "apple_mentions": apple["mentions"] if apple else None,
            "apple_chunks": apple["chunks"] if apple else None,
            "apple_home_ticker": apple["home_ticker"] if apple else None,
            "apple_tickers": list(apple["tickers"] or []) if apple else None,
            "apple_ticker": apple["ticker"] if apple else None,
        }
    finally:
        if own_driver:
            driver.close()


if __name__ == "__main__":
    import json
    import sys

    if "--cleanup-cross-issuer" in sys.argv:
        print(json.dumps(cleanup_cross_issuer_edges(), indent=2))
        sys.exit(0)

    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    run_all = "--all" in sys.argv
    budget_only = "--budget" in sys.argv
    confirmed = "--confirm" in sys.argv
    max_chunks = None if run_all else 5

    if budget_only:
        from budget import estimate_ticker_budget

        print(json.dumps(estimate_ticker_budget(symbol, max_chunks=max_chunks).model_dump(), indent=2))
        sys.exit(0)

    result = write_company(symbol, max_chunks=max_chunks, confirm=confirmed)
    counts = smoke_counts()
    print(json.dumps({"result": result, "neo4j": counts}, indent=2))
