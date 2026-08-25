"""
Step L: Graph retrieval via parameterized Cypher templates.

Flow:
  question → extract mentions + template_id (Haiku/Instructor)
  → resolve mentions to Neo4j node ids
  → run FIXED Cypher templates with $params only
  → return paths + source_chunk_ids

WHY templates: curriculum forbids model-written Cypher (injection / hallucination).
Out of scope: vector retrieval (Step M), answer merge (Phase 4).
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, List, Optional

import anthropic
import instructor
from neo4j import Driver
from pydantic import BaseModel, Field

from config import settings
from graph_writer import get_driver
from resolver import normalize_name


class GraphTemplateId(str, Enum):
    """Allowlisted template keys — the only Cypher the system may run."""

    COMPANY_PRODUCTS = "company_products"
    COMPANY_RISKS = "company_risks"
    COMPANY_COMPETITORS = "company_competitors"
    COMPANY_SUPPLIERS = "company_suppliers"
    COMPANY_SUBSIDIARIES = "company_subsidiaries"
    ENTITY_OUTGOING = "entity_outgoing"


# Fixed Cypher only. Rel types are literals from our ontology — never interpolated from LLM text.
_TEMPLATES: Dict[GraphTemplateId, str] = {
    GraphTemplateId.COMPANY_PRODUCTS: """
        MATCH (c {id: $entity_id})-[r:PRODUCES_PRODUCT]->(p)
        RETURN c.id AS source_id, c.name AS source_name,
               type(r) AS rel_type,
               p.id AS target_id, p.name AS target_name,
               r.source_chunk_ids AS source_chunk_ids,
               r.context AS context,
               r.confidence AS confidence
        LIMIT $limit
        """,
    GraphTemplateId.COMPANY_RISKS: """
        MATCH (c {id: $entity_id})-[r:EXPOSED_TO_RISK]->(risk)
        RETURN c.id AS source_id, c.name AS source_name,
               type(r) AS rel_type,
               risk.id AS target_id, risk.name AS target_name,
               r.source_chunk_ids AS source_chunk_ids,
               r.context AS context,
               r.confidence AS confidence
        LIMIT $limit
        """,
    GraphTemplateId.COMPANY_COMPETITORS: """
        MATCH (c {id: $entity_id})-[r:COMPETES_WITH]->(other)
        RETURN c.id AS source_id, c.name AS source_name,
               type(r) AS rel_type,
               other.id AS target_id, other.name AS target_name,
               r.source_chunk_ids AS source_chunk_ids,
               r.context AS context,
               r.confidence AS confidence
        LIMIT $limit
        """,
    GraphTemplateId.COMPANY_SUPPLIERS: """
        MATCH (c {id: $entity_id})-[r:SUPPLIED_BY]->(s)
        RETURN c.id AS source_id, c.name AS source_name,
               type(r) AS rel_type,
               s.id AS target_id, s.name AS target_name,
               r.source_chunk_ids AS source_chunk_ids,
               r.context AS context,
               r.confidence AS confidence
        LIMIT $limit
        """,
    GraphTemplateId.COMPANY_SUBSIDIARIES: """
        MATCH (c {id: $entity_id})-[r:OWNS_SUBSIDIARY]->(sub)
        RETURN c.id AS source_id, c.name AS source_name,
               type(r) AS rel_type,
               sub.id AS target_id, sub.name AS target_name,
               r.source_chunk_ids AS source_chunk_ids,
               r.context AS context,
               r.confidence AS confidence
        LIMIT $limit
        """,
    GraphTemplateId.ENTITY_OUTGOING: """
        MATCH (c {id: $entity_id})-[r]->(n)
        RETURN c.id AS source_id, c.name AS source_name,
               type(r) AS rel_type,
               n.id AS target_id, n.name AS target_name,
               r.source_chunk_ids AS source_chunk_ids,
               r.context AS context,
               r.confidence AS confidence
        LIMIT $limit
        """,
}


PLAN_SYSTEM_PROMPT = f"""
You plan a Neo4j graph lookup for a question about SEC 10-K filings.

Choose exactly one template_id from this allowlist:
{", ".join(t.value for t in GraphTemplateId)}

Guidance:
- company_products: what products / product lines a company produces
- company_risks: risks a company is exposed to
- company_competitors: who / what a company competes with
- company_suppliers: suppliers of a company
- company_subsidiaries: subsidiaries owned by a company
- entity_outgoing: broad "what is connected to X" when no narrower template fits

Also extract entity_mentions: company/product/risk names that appear in the question
(or are clearly implied, e.g. "Apple" for "AAPL products"). Prefer the primary
subject company first in the list.

Never invent Cypher. Only pick template_id + entity names.
""".strip()


class GraphQueryPlan(BaseModel):
    template_id: GraphTemplateId
    entity_mentions: List[str] = Field(
        ...,
        description="Names to resolve to Neo4j ids; primary subject first.",
    )
    rationale: str = Field(..., description="One sentence why this template fits.")


class ResolvedEntity(BaseModel):
    mention: str
    entity_id: Optional[str] = None
    name: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    resolved: bool = False


class GraphFact(BaseModel):
    source_id: str
    source_name: str
    rel_type: str
    target_id: str
    target_name: str
    source_chunk_ids: List[str] = Field(default_factory=list)
    context: Optional[str] = None
    confidence: Optional[float] = None


class GraphRetrievalResult(BaseModel):
    question: str
    template_id: GraphTemplateId
    plan_rationale: str
    resolved_entities: List[ResolvedEntity]
    entity_id_used: Optional[str] = None
    facts: List[GraphFact] = Field(default_factory=list)
    cypher_ran: bool = False


def _build_client() -> instructor.Instructor:
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY is missing. Set it in your .env before graph retrieval."
        )
    raw = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    mode = getattr(instructor.Mode, "ANTHROPIC_TOOLS", None) or instructor.Mode.TOOLS
    return instructor.from_anthropic(raw, mode=mode)


def plan_graph_query(
    question: str,
    *,
    client: Optional[instructor.Instructor] = None,
) -> GraphQueryPlan:
    """LLM picks an allowlisted template + entity mentions — never Cypher."""
    client = client or _build_client()
    return client.messages.create(
        model=settings.ROUTER_MODEL,
        max_tokens=settings.ROUTER_MAX_TOKENS,
        max_retries=settings.ROUTER_MAX_RETRIES,
        system=PLAN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
        response_model=GraphQueryPlan,
    )


def resolve_mention_to_node(
    mention: str,
    *,
    driver: Optional[Driver] = None,
) -> ResolvedEntity:
    """
    Map a surface name to a Neo4j node id.

    Tries normalize_name(mention) as id, then case-insensitive name match.
    """
    own = driver is None
    driver = driver or get_driver()
    candidate_id = normalize_name(mention) or mention.upper().replace(" ", "")

    try:
        with driver.session() as session:
            # Exact id hit (canonical resolver ids).
            row = session.run(
                """
                MATCH (n {id: $id})
                RETURN n.id AS id, n.name AS name, labels(n) AS labels
                LIMIT 1
                """,
                id=candidate_id,
            ).single()
            if row:
                return ResolvedEntity(
                    mention=mention,
                    entity_id=row["id"],
                    name=row["name"],
                    labels=list(row["labels"] or []),
                    resolved=True,
                )

            # Fallback: name / alias contains (still parameterized — no LLM Cypher).
            row = session.run(
                """
                MATCH (n)
                WHERE toLower(n.name) CONTAINS toLower($mention)
                   OR any(a IN coalesce(n.aliases, []) WHERE toLower(a) CONTAINS toLower($mention))
                RETURN n.id AS id, n.name AS name, labels(n) AS labels
                ORDER BY size(n.name) ASC
                LIMIT 1
                """,
                mention=mention,
            ).single()
            if row:
                return ResolvedEntity(
                    mention=mention,
                    entity_id=row["id"],
                    name=row["name"],
                    labels=list(row["labels"] or []),
                    resolved=True,
                )
    finally:
        if own:
            driver.close()

    return ResolvedEntity(mention=mention, resolved=False)


def run_template(
    template_id: GraphTemplateId,
    *,
    entity_id: str,
    limit: Optional[int] = None,
    driver: Optional[Driver] = None,
) -> List[GraphFact]:
    """
    Execute one allowlisted template with bound parameters only.

    Uses _TEMPLATES only — unknown ids raise before any Neo4j call.
    """
    if template_id not in _TEMPLATES:
        raise ValueError(f"Unknown template_id: {template_id}")

    limit = settings.GRAPH_RETRIEVAL_LIMIT if limit is None else limit
    cypher = _TEMPLATES[template_id]
    own = driver is None
    driver = driver or get_driver()
    facts: List[GraphFact] = []

    try:
        with driver.session() as session:
            result = session.run(
                cypher,
                entity_id=entity_id,
                limit=limit,
            )
            for record in result:
                chunk_ids = record.get("source_chunk_ids") or []
                if not isinstance(chunk_ids, list):
                    chunk_ids = list(chunk_ids)
                facts.append(
                    GraphFact(
                        source_id=record["source_id"],
                        source_name=record["source_name"] or record["source_id"],
                        rel_type=record["rel_type"],
                        target_id=record["target_id"],
                        target_name=record["target_name"] or record["target_id"],
                        source_chunk_ids=[str(x) for x in chunk_ids],
                        context=record.get("context"),
                        confidence=record.get("confidence"),
                    )
                )
    finally:
        if own:
            driver.close()

    return facts


def retrieve_graph(
    question: str,
    *,
    client: Optional[instructor.Instructor] = None,
    driver: Optional[Driver] = None,
    limit: Optional[int] = None,
) -> GraphRetrievalResult:
    """
    End-to-end Step L: plan → resolve → parameterized template query.
    """
    plan = plan_graph_query(question, client=client)
    own = driver is None
    driver = driver or get_driver()

    try:
        resolved: List[ResolvedEntity] = []
        for mention in plan.entity_mentions:
            resolved.append(resolve_mention_to_node(mention, driver=driver))

        # Prefer first resolved mention; else try "APPLE" if question is AAPL-ish — no:
        # stick to resolved list only.
        entity_id: Optional[str] = None
        for r in resolved:
            if r.resolved and r.entity_id:
                entity_id = r.entity_id
                break

        if entity_id is None:
            return GraphRetrievalResult(
                question=question,
                template_id=plan.template_id,
                plan_rationale=plan.rationale,
                resolved_entities=resolved,
                entity_id_used=None,
                facts=[],
                cypher_ran=False,
            )

        facts = run_template(
            plan.template_id,
            entity_id=entity_id,
            limit=limit,
            driver=driver,
        )
        return GraphRetrievalResult(
            question=question,
            template_id=plan.template_id,
            plan_rationale=plan.rationale,
            resolved_entities=resolved,
            entity_id_used=entity_id,
            facts=facts,
            cypher_ran=True,
        )
    finally:
        if own:
            driver.close()


if __name__ == "__main__":
    import sys

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    question = (
        " ".join(args)
        if args
        else "What product lines does Apple produce?"
    )
    result = retrieve_graph(question)
    print(json.dumps(result.model_dump(), indent=2))
