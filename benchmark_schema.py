"""
Phase 5 Step Q: Benchmark question + result schemas.

Hop labels (curriculum):
  0 — definition / single-fact prose (usually vector)
  1 — one relationship hop (Company → Product/Risk/Competitor/Supplier)
  2 — compare / aggregate across relationship types or mixed evidence
  oos — must_refuse=True; topic outside retrieved corpus

Out of scope for Step Q: running hybrid vs vector-only (Step R).
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class HopBucket(int, Enum):
    """Integer hop stratification for accuracy tables."""

    HOP_0 = 0
    HOP_1 = 1
    HOP_2 = 2


class ExpectedRouteHint(str, Enum):
    """Soft label for analysis — not enforced at retrieve time."""

    GRAPH = "graph"
    VECTOR = "vector"
    BOTH = "both"
    REFUSE = "refuse"


class BenchmarkMode(str, Enum):
    """Step R comparison modes."""

    HYBRID = "hybrid"
    VECTOR_ONLY = "vector_only"


class BenchmarkItem(BaseModel):
    """One labeled evaluation question."""

    id: str = Field(..., description="Stable id, e.g. hop1_products.")
    question: str
    hop: HopBucket = Field(
        ...,
        description="0=definition, 1=single edge, 2=multi/compare. Ignored when must_refuse.",
    )
    must_refuse: bool = Field(
        default=False,
        description="True for out-of-scope items; hybrid should set refused=true.",
    )
    ticker: str = Field(default="AAPL")
    expected_route: ExpectedRouteHint = Field(
        default=ExpectedRouteHint.BOTH,
        description="Soft routing expectation for post-hoc analysis.",
    )
    gold_keywords: List[str] = Field(
        default_factory=list,
        description="Case-insensitive needles; Step R scores hit rate in summary+claims.",
    )
    gold_entity_ids: List[str] = Field(
        default_factory=list,
        description="Optional Neo4j entity ids that should appear in graph evidence.",
    )
    gold_chunk_ids: List[str] = Field(
        default_factory=list,
        description="Optional chunk ids that should appear in citations or retrieval.",
    )
    notes: str = Field(default="", description="Why this item is labeled this way.")

    @field_validator("gold_keywords", "gold_entity_ids", "gold_chunk_ids", mode="before")
    @classmethod
    def _none_to_list(cls, v):  # noqa: ANN001
        return v or []


class BenchmarkSuite(BaseModel):
    """Versioned labeled set."""

    name: str
    version: str = "1"
    corpus_notes: str = ""
    items: List[BenchmarkItem] = Field(default_factory=list)

    def by_hop(self) -> dict[str, List[BenchmarkItem]]:
        buckets: dict[str, List[BenchmarkItem]] = {
            "hop_0": [],
            "hop_1": [],
            "hop_2": [],
            "oos": [],
        }
        for item in self.items:
            if item.must_refuse:
                buckets["oos"].append(item)
            else:
                buckets[f"hop_{int(item.hop)}"].append(item)
        return buckets

    def summary_counts(self) -> dict[str, int]:
        b = self.by_hop()
        return {k: len(v) for k, v in b.items()} | {"total": len(self.items)}


class BenchmarkItemResult(BaseModel):
    """
    One (item × mode) outcome — filled by Step R runner.

    Defined in Step Q so the labeled set and scoring contract stay aligned.
    """

    item_id: str
    mode: BenchmarkMode
    question: str
    hop: HopBucket
    must_refuse: bool
    # Answer / retrieval
    refused: bool = False
    citations_valid: bool = False
    regenerated: bool = False
    summary: str = ""
    claim_count: int = 0
    cited_chunk_ids: List[str] = Field(default_factory=list)
    route_effective: Optional[str] = None
    # Scoring hooks (Step R)
    keyword_hits: List[str] = Field(default_factory=list)
    keyword_misses: List[str] = Field(default_factory=list)
    keyword_recall: Optional[float] = None
    correct_refuse: Optional[bool] = None
    # Cost / latency
    latency_ms: Optional[float] = None
    estimated_cost_usd: Optional[float] = None
    error: Optional[str] = None
    # 0–1 item score (refuse accuracy or keyword recall)
    score: Optional[float] = None


class BenchmarkReport(BaseModel):
    """Aggregate report shell for Step R/S."""

    suite_name: str
    suite_version: str
    mode: BenchmarkMode
    results: List[BenchmarkItemResult] = Field(default_factory=list)
    accuracy_by_hop: dict[str, float] = Field(default_factory=dict)
    mean_latency_ms: Optional[float] = None
    mean_cost_usd: Optional[float] = None
    mean_score: Optional[float] = None
    notes: str = ""


class BenchmarkComparison(BaseModel):
    """Side-by-side hybrid vs vector-only (Step R output / Step S input)."""

    suite_name: str
    suite_version: str
    hybrid: BenchmarkReport
    vector_only: BenchmarkReport
    notes: str = ""
