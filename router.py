"""
Step K: Route questions to graph vs vector retrieval.

Cheap few-shot classifier (Claude Haiku + Instructor) returns GRAPH | VECTOR | BOTH.
Low confidence → BOTH. Every decision is logged for Phase 5 analysis.

Out of scope: actually running graph/vector retrieval (Steps L/M), answer merge (Phase 4).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional

import anthropic
import instructor
from pydantic import BaseModel, Field

from config import settings


class RetrievalRoute(str, Enum):
    GRAPH = "graph"
    VECTOR = "vector"
    BOTH = "both"


class RouteClassification(BaseModel):
    """Structured LLM output before confidence fallback."""

    route: RetrievalRoute = Field(
        ...,
        description="Primary retrieval path: graph for multi-hop/connections, "
        "vector for definitions/single facts, both when unclear or mixed.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Calibrated probability the chosen route is correct.",
    )
    rationale: str = Field(
        ...,
        description="One sentence explaining why this route fits the question.",
    )


class RouteDecision(BaseModel):
    """Final routing decision after confidence threshold (what downstream steps use)."""

    question: str
    model_route: RetrievalRoute
    effective_route: RetrievalRoute
    confidence: float
    rationale: str
    low_confidence_fallback: bool
    model: str


ROUTER_SYSTEM_PROMPT = """
You route user questions about SEC 10-K filings to the best retrieval strategy.

Return exactly one route:
- graph: multi-hop connections, comparisons, aggregations, "who supplies X", "what risks is Y exposed to", relationship traversal
- vector: definitions, single-fact lookup, policy-style prose, "what is X", "describe Y"
- both: mixed needs (entity + narrative), ambiguous, or you are unsure

Examples:
Q: What product lines does Apple produce?
route: graph
confidence: 0.92
rationale: Requires traversing PRODUCES_PRODUCT relationships from Company to ProductLine.

Q: What is AppleCare?
route: vector
confidence: 0.95
rationale: Definition-style question best answered by retrieving descriptive chunk text.

Q: How is Apple exposed to China trade and tariff risks?
route: both
confidence: 0.88
rationale: Needs risk entity links in the graph plus narrative detail from filing text.

Q: Compare Apple's competitive risks to its supply chain risks.
route: graph
confidence: 0.90
rationale: Comparison across relationship types in the knowledge graph.

Q: What did the filing say about seasonality?
route: vector
confidence: 0.91
rationale: Single-topic prose retrieval from MD&A or business sections.

Q: Tell me about Apple's situation with suppliers and what that means for the business.
route: both
confidence: 0.55
rationale: Ambiguous mix of relationship traversal and open-ended narrative; not confident enough for a single path.

Q: Apple risks?
route: both
confidence: 0.42
rationale: Too underspecified to choose graph vs vector; low confidence so prefer both.

When uncertain, prefer both and report low confidence (below ~0.75) rather than guessing graph or vector with a high score.
""".strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_client() -> instructor.Instructor:
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY is missing. Set it in your .env before routing."
        )
    raw = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    mode = getattr(instructor.Mode, "ANTHROPIC_TOOLS", None) or instructor.Mode.TOOLS
    return instructor.from_anthropic(raw, mode=mode)


def apply_confidence_fallback(
    classification: RouteClassification,
    *,
    threshold: Optional[float] = None,
) -> tuple[RetrievalRoute, bool]:
    """
    Low confidence → BOTH so we do not silently pick the wrong retrieval path.

    WHY: a wrong graph-only or vector-only path loses recall; running both is
    cheaper than a bad answer in Phase 4.
    """
    threshold = (
        settings.ROUTER_CONFIDENCE_THRESHOLD
        if threshold is None
        else threshold
    )
    if classification.confidence < threshold:
        return RetrievalRoute.BOTH, True
    return classification.route, False


class RouteLogger:
    """Append-only SQLite log of every routing decision."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS route_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    model_route TEXT NOT NULL,
                    effective_route TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    rationale TEXT NOT NULL,
                    low_confidence_fallback INTEGER NOT NULL,
                    model TEXT NOT NULL,
                    routed_at TEXT NOT NULL
                )
                """
            )

    def log(self, decision: RouteDecision) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO route_log (
                    question, model_route, effective_route, confidence,
                    rationale, low_confidence_fallback, model, routed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.question,
                    decision.model_route.value,
                    decision.effective_route.value,
                    decision.confidence,
                    decision.rationale,
                    int(decision.low_confidence_fallback),
                    decision.model,
                    _utc_now(),
                ),
            )


def classify_question(
    question: str,
    *,
    client: Optional[instructor.Instructor] = None,
) -> RouteClassification:
    """Call the router LLM; does not apply confidence fallback or log."""
    client = client or _build_client()
    return client.messages.create(
        model=settings.ROUTER_MODEL,
        max_tokens=settings.ROUTER_MAX_TOKENS,
        max_retries=settings.ROUTER_MAX_RETRIES,
        system=ROUTER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
        response_model=RouteClassification,
    )


def route_question(
    question: str,
    *,
    client: Optional[instructor.Instructor] = None,
    logger: Optional[RouteLogger] = None,
    threshold: Optional[float] = None,
    log: bool = True,
) -> RouteDecision:
    """
    Classify a question, apply confidence fallback, optionally log.

    Returns effective_route — what Steps L/M should execute.
    """
    classification = classify_question(question, client=client)
    effective, fallback = apply_confidence_fallback(
        classification, threshold=threshold
    )
    decision = RouteDecision(
        question=question,
        model_route=classification.route,
        effective_route=effective,
        confidence=classification.confidence,
        rationale=classification.rationale,
        low_confidence_fallback=fallback,
        model=settings.ROUTER_MODEL,
    )
    if log:
        route_logger = logger or RouteLogger(settings.ROUTER_LOG_PATH)
        route_logger.log(decision)
    return decision


# Smoke-test questions for Step K (no retrieval yet).
DEMO_QUESTIONS: List[str] = [
    "What product lines does Apple produce?",
    "What is AppleCare?",
    "How is Apple exposed to China trade and tariff risks?",
    "What did the filing say about business seasonality?",
    "Compare Apple's supply chain risks to its competitive risks.",
]


if __name__ == "__main__":
    import sys

    if "--demo" in sys.argv:
        questions = DEMO_QUESTIONS
    else:
        args = [a for a in sys.argv[1:] if not a.startswith("-")]
        questions = [" ".join(args)] if args else [DEMO_QUESTIONS[0]]

    results = [route_question(q).model_dump() for q in questions]
    print(json.dumps(results if len(results) > 1 else results[0], indent=2))
