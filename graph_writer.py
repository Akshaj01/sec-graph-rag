"""
Step F: Idempotent Neo4j Cypher writes.

Takes a ResolvedGraph from resolver.py and MERGE-writes nodes + relationships.
Re-running the same ticker must not duplicate canonical entities or edges.

BASWE requirements covered here:
  - MERGE (not CREATE)
  - source_chunk_ids on edges for citation provenance
  - uniqueness constraints on entity id per label
"""

from __future__ import annotations

from typing import Dict, Optional, Set

from neo4j import GraphDatabase, Driver
from pydantic import BaseModel

from config import settings
from resolver import ResolvedGraph, resolve_company
from schemas import EntityType, RelationshipType

# Allowlists only — used to safely interpolate labels / rel types into Cypher.
_ENTITY_LABELS: Set[str] = {e.value for e in EntityType}
_REL_TYPES: Set[str] = {r.value for r in RelationshipType}


class WriteStats(BaseModel):
    entities_merged: int = 0
    relationships_merged: int = 0
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


def _merge_entity(tx, entity, *, ticker: Optional[str], accession_number: Optional[str]) -> None:
    label = entity.type.value
    if label not in _ENTITY_LABELS:
        raise ValueError(f"Refusing unknown entity label: {label}")

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


def _merge_relationship(tx, rel) -> None:
    rel_type = rel.type.value
    if rel_type not in _REL_TYPES:
        raise ValueError(f"Refusing unknown relationship type: {rel_type}")

    # Endpoints may have different labels; match by id across any ontology label.
    cypher = f"""
    MATCH (a {{id: $src}})
    MATCH (b {{id: $tgt}})
    MERGE (a)-[r:{rel_type}]->(b)
    SET r.confidence = $confidence,
        r.context = $context,
        r.source_chunk_ids = $source_chunk_ids,
        r.updated_at = datetime()
    """
    tx.run(
        cypher,
        src=rel.source_entity_id,
        tgt=rel.target_entity_id,
        confidence=rel.confidence,
        context=rel.context,
        source_chunk_ids=rel.source_chunk_ids,
    )


def write_graph(graph: ResolvedGraph, *, driver: Optional[Driver] = None) -> WriteStats:
    """MERGE all canonical entities and relationships into Neo4j."""
    own_driver = driver is None
    driver = driver or get_driver()
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
                for rel in graph.relationships:
                    _merge_relationship(tx, rel)

            session.execute_write(_write_all)

        return WriteStats(
            entities_merged=len(graph.entities),
            relationships_merged=len(graph.relationships),
            constraints_ensured=constraints,
            ticker=graph.ticker,
            accession_number=graph.accession_number,
        )
    finally:
        if own_driver:
            driver.close()


def write_company(
    ticker: str,
    *,
    max_chunks: Optional[int] = None,
    enable_soft_match: Optional[bool] = None,
) -> Dict[str, object]:
    """Resolve a company (cached extract when possible), then MERGE into Neo4j."""
    graph = resolve_company(
        ticker,
        max_chunks=max_chunks,
        enable_soft_match=enable_soft_match,
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
                "c.mention_count AS mentions, size(c.source_chunk_ids) AS chunks"
            ).single()
        return {
            "nodes": nodes,
            "relationships": rels,
            "apple_name": apple["name"] if apple else None,
            "apple_mentions": apple["mentions"] if apple else None,
            "apple_chunks": apple["chunks"] if apple else None,
        }
    finally:
        if own_driver:
            driver.close()


if __name__ == "__main__":
    import json
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    run_all = "--all" in sys.argv
    max_chunks = None if run_all else 5

    result = write_company(symbol, max_chunks=max_chunks)
    counts = smoke_counts()
    print(json.dumps({"result": result, "neo4j": counts}, indent=2))
