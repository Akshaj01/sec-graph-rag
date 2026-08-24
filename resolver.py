"""
Step E: Entity resolution & canonical mapping.

Collapse duplicate extractions (e.g. Apple Inc. across many chunks) into one
canonical node + alias list, then rewrite relationship endpoints.

Strategy:
  1) Hard match — normalize name; same type + same key => merge
  2) Soft match — OpenAI embeddings; same type + cosine >= threshold => merge
  3) Never merge across EntityType

Out of scope: Neo4j writes (Step F).
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

from openai import OpenAI
from pydantic import BaseModel, Field

from config import settings
from extractor import ChunkExtractionResult, ExtractionRunResult, extract_company
from schemas import EntityType, RelationshipType

# Corporate suffixes / noise stripped during hard normalization.
_SUFFIXES = {
    "INC",
    "INCORPORATED",
    "CORP",
    "CORPORATION",
    "CO",
    "COMPANY",
    "LLC",
    "LTD",
    "LIMITED",
    "LP",
    "LLP",
    "PLC",
    "NA",
    "USA",
}


class CanonicalEntity(BaseModel):
    id: str
    type: EntityType
    name: str
    aliases: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    source_chunk_ids: List[str] = Field(default_factory=list)
    confidence: float
    mention_count: int


class ResolvedRelationship(BaseModel):
    source_entity_id: str
    target_entity_id: str
    type: RelationshipType
    context: Optional[str] = None
    source_chunk_ids: List[str] = Field(default_factory=list)
    confidence: float


class ResolutionStats(BaseModel):
    input_entities: int
    canonical_entities: int
    input_relationships: int
    canonical_relationships: int
    hard_merge_groups: int
    soft_merges: int
    soft_match_enabled: bool


class ResolvedGraph(BaseModel):
    ticker: Optional[str] = None
    accession_number: Optional[str] = None
    entities: List[CanonicalEntity]
    relationships: List[ResolvedRelationship]
    stats: ResolutionStats


class _Mention(BaseModel):
    """One extracted entity occurrence from a single chunk."""

    chunk_id: str
    original_id: str
    type: EntityType
    name: str
    description: Optional[str] = None
    confidence: float
    norm_key: str


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True


def normalize_name(name: str) -> str:
    """
    Hard-normalization key for exact merges.

    WHY: SEC text repeats 'Apple Inc.' / 'APPLE INC' / 'Apple Inc' — string
    identity must not create four graph nodes.
    """
    cleaned = name.upper()
    cleaned = re.sub(r"[^A-Z0-9\s]", " ", cleaned)
    tokens = [t for t in cleaned.split() if t and t not in _SUFFIXES]
    return "".join(tokens)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    if not settings.OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY is missing. Soft-match requires it in your .env."
        )
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    # Batch for cost/latency; API accepts large batches but keep chunks modest.
    vectors: List[List[float]] = []
    batch_size = 64
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=batch,
        )
        # API returns data sorted by index within the request.
        ordered = sorted(response.data, key=lambda row: row.index)
        vectors.extend([row.embedding for row in ordered])
    return vectors


def _collect_mentions(results: Sequence[ChunkExtractionResult]) -> List[_Mention]:
    mentions: List[_Mention] = []
    for result in results:
        for entity in result.extraction.entities:
            mentions.append(
                _Mention(
                    chunk_id=result.chunk_id,
                    original_id=entity.id,
                    type=entity.type,
                    name=entity.name.strip(),
                    description=entity.description,
                    confidence=entity.confidence,
                    norm_key=normalize_name(entity.name),
                )
            )
    return mentions


def _cluster_mentions(
    mentions: List[_Mention],
    *,
    threshold: float,
    enable_soft_match: bool,
) -> Tuple[List[List[int]], int, int]:
    """
    Returns:
      clusters: list of mention-index lists
      hard_merge_groups: count of normalized keys that covered >1 mention
      soft_merges: number of successful soft unions
    """
    n = len(mentions)
    uf = _UnionFind(n)

    # --- Hard match within the same type ---
    hard_buckets: Dict[Tuple[EntityType, str], List[int]] = defaultdict(list)
    for idx, mention in enumerate(mentions):
        if not mention.norm_key:
            continue
        hard_buckets[(mention.type, mention.norm_key)].append(idx)

    hard_merge_groups = 0
    for idxs in hard_buckets.values():
        if len(idxs) > 1:
            hard_merge_groups += 1
        root = idxs[0]
        for other in idxs[1:]:
            uf.union(root, other)

    soft_merges = 0

    # --- Soft match: compare remaining cluster reps within each type ---
    if enable_soft_match and n > 1:
        by_type: Dict[EntityType, List[int]] = defaultdict(list)
        for idx, mention in enumerate(mentions):
            by_type[mention.type].append(idx)

        for type_idxs in by_type.values():
            # Unique union-find roots still present for this type.
            roots = sorted({uf.find(i) for i in type_idxs})
            if len(roots) < 2:
                continue

            # Representative display name per root (highest confidence mention).
            root_name: Dict[int, str] = {}
            for root in roots:
                members = [i for i in type_idxs if uf.find(i) == root]
                best = max(members, key=lambda i: (mentions[i].confidence, len(mentions[i].name)))
                root_name[root] = mentions[best].name

            embeddings = _embed_texts([root_name[r] for r in roots])
            for i in range(len(roots)):
                for j in range(i + 1, len(roots)):
                    score = _cosine(embeddings[i], embeddings[j])
                    if score >= threshold:
                        if uf.union(roots[i], roots[j]):
                            soft_merges += 1

    clusters_map: Dict[int, List[int]] = defaultdict(list)
    for idx in range(n):
        clusters_map[uf.find(idx)].append(idx)

    return list(clusters_map.values()), hard_merge_groups, soft_merges


def _pick_canonical(mentions: List[_Mention], member_idxs: List[int]) -> CanonicalEntity:
    members = [mentions[i] for i in member_idxs]
    # Prefer highest confidence; break ties with longer (usually more complete) name.
    best = max(members, key=lambda m: (m.confidence, len(m.name)))
    aliases = sorted({m.name for m in members})
    chunk_ids = sorted({m.chunk_id for m in members})
    descriptions = [m.description for m in members if m.description]
    description = max(descriptions, key=len) if descriptions else None
    canonical_id = normalize_name(best.name) or best.original_id.upper()

    return CanonicalEntity(
        id=canonical_id,
        type=best.type,
        name=best.name,
        aliases=aliases,
        description=description,
        source_chunk_ids=chunk_ids,
        confidence=max(m.confidence for m in members),
        mention_count=len(members),
    )


def resolve_extractions(
    results: Sequence[ChunkExtractionResult],
    *,
    ticker: Optional[str] = None,
    accession_number: Optional[str] = None,
    threshold: Optional[float] = None,
    enable_soft_match: Optional[bool] = None,
) -> ResolvedGraph:
    """Merge entity mentions across chunk extractions into a canonical graph."""
    threshold = (
        settings.ENTITY_SIMILARITY_THRESHOLD if threshold is None else threshold
    )
    if enable_soft_match is None:
        enable_soft_match = bool(settings.OPENAI_API_KEY)

    mentions = _collect_mentions(results)
    input_rel_count = sum(len(r.extraction.relationships) for r in results)

    if not mentions:
        return ResolvedGraph(
            ticker=ticker,
            accession_number=accession_number,
            entities=[],
            relationships=[],
            stats=ResolutionStats(
                input_entities=0,
                canonical_entities=0,
                input_relationships=input_rel_count,
                canonical_relationships=0,
                hard_merge_groups=0,
                soft_merges=0,
                soft_match_enabled=enable_soft_match,
            ),
        )

    clusters, hard_merge_groups, soft_merges = _cluster_mentions(
        mentions,
        threshold=threshold,
        enable_soft_match=enable_soft_match,
    )

    # (chunk_id, original_id) -> canonical entity id
    pair_to_canonical: Dict[Tuple[str, str], str] = {}
    canonical_entities: List[CanonicalEntity] = []
    used_ids: Dict[str, int] = {}

    for member_idxs in clusters:
        canonical = _pick_canonical(mentions, member_idxs)
        # Disambiguate rare id collisions across different types/names.
        base_id = canonical.id
        if base_id in used_ids:
            used_ids[base_id] += 1
            canonical.id = f"{base_id}_{canonical.type.value.upper()}_{used_ids[base_id]}"
        else:
            used_ids[base_id] = 1

        canonical_entities.append(canonical)
        for idx in member_idxs:
            m = mentions[idx]
            pair_to_canonical[(m.chunk_id, m.original_id)] = canonical.id

    # Rewrite + dedupe relationships onto canonical ids.
    rel_acc: Dict[Tuple[str, str, RelationshipType], ResolvedRelationship] = {}
    for result in results:
        for rel in result.extraction.relationships:
            src = pair_to_canonical.get((result.chunk_id, rel.source_entity_id))
            tgt = pair_to_canonical.get((result.chunk_id, rel.target_entity_id))
            if not src or not tgt or src == tgt:
                continue
            key = (src, tgt, rel.type)
            existing = rel_acc.get(key)
            if existing is None:
                rel_acc[key] = ResolvedRelationship(
                    source_entity_id=src,
                    target_entity_id=tgt,
                    type=rel.type,
                    context=rel.context,
                    source_chunk_ids=[result.chunk_id],
                    confidence=rel.confidence,
                )
            else:
                if result.chunk_id not in existing.source_chunk_ids:
                    existing.source_chunk_ids.append(result.chunk_id)
                if rel.confidence > existing.confidence:
                    existing.confidence = rel.confidence
                    if rel.context:
                        existing.context = rel.context

    canonical_entities.sort(key=lambda e: (e.type.value, e.name.lower()))
    relationships = sorted(
        rel_acc.values(),
        key=lambda r: (r.type.value, r.source_entity_id, r.target_entity_id),
    )

    return ResolvedGraph(
        ticker=ticker,
        accession_number=accession_number,
        entities=canonical_entities,
        relationships=relationships,
        stats=ResolutionStats(
            input_entities=len(mentions),
            canonical_entities=len(canonical_entities),
            input_relationships=input_rel_count,
            canonical_relationships=len(relationships),
            hard_merge_groups=hard_merge_groups,
            soft_merges=soft_merges,
            soft_match_enabled=enable_soft_match,
        ),
    )


def resolve_company(
    ticker: str,
    *,
    max_chunks: Optional[int] = None,
    threshold: Optional[float] = None,
    enable_soft_match: Optional[bool] = None,
    confirm: bool = False,
    skip_budget_check: bool = False,
) -> ResolvedGraph:
    """Extract (cached when possible), then resolve entities for a ticker."""
    run: ExtractionRunResult = extract_company(
        ticker,
        max_chunks=max_chunks,
        confirm=confirm,
        skip_budget_check=skip_budget_check,
    )
    return resolve_extractions(
        run.results,
        ticker=run.ticker,
        accession_number=run.accession_number,
        threshold=threshold,
        enable_soft_match=enable_soft_match,
    )


if __name__ == "__main__":
    import json
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    run_all = "--all" in sys.argv
    # Default 5 chunks: enough to show merges without a full-filing bill.
    max_chunks = None if run_all else 5

    graph = resolve_company(symbol, max_chunks=max_chunks)
    summary = {
        "ticker": graph.ticker,
        "accession_number": graph.accession_number,
        "stats": graph.stats.model_dump(),
        "sample_entities": [
            {
                "id": e.id,
                "type": e.type.value,
                "name": e.name,
                "aliases": e.aliases,
                "mention_count": e.mention_count,
                "source_chunk_ids": e.source_chunk_ids,
                "confidence": e.confidence,
            }
            for e in graph.entities[:10]
        ],
        "sample_relationships": [
            {
                "source": r.source_entity_id,
                "target": r.target_entity_id,
                "type": r.type.value,
                "confidence": r.confidence,
                "chunks": r.source_chunk_ids,
            }
            for r in graph.relationships[:10]
        ],
    }
    print(json.dumps(summary, indent=2))
