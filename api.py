"""
Phase 5 Step T: FastAPI wrapper for grounded SEC Q&A.

POST /ask → answer_question (validated citations) plus a display trace.
GET /health → liveness for Docker / local dev.

WHY thin wrapper: all logic stays in answer.py; API only shapes I/O for clients.
The trace is a projection of AnswerResult. It does not retrieve or answer again.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from answer import AnswerClaim, AnswerResult, answer_question
from router import RetrievalRoute

# Local Next.js dev server. The demo does not accept arbitrary browser origins.
_DEMO_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Keep the public payload short. Retrieval already limits how much comes back;
# these caps are a second guard so a demo response is not a filing dump.
_MAX_FACTS = 12
_MAX_PASSAGES = 8
_MAX_EVIDENCE = 12
_MAX_CHUNK_IDS = 6
_PREVIEW_CHARS = 240
_STATEMENT_CHARS = 320


app = FastAPI(
    title="SEC GraphRAG",
    description="Hybrid knowledge graph + vector RAG over SEC 10-K filings.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEMO_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural-language question.")
    ticker: Optional[str] = Field(
        default=None,
        description="Scope vector search (e.g. AAPL). Defaults to router/guess.",
    )
    vector_only: bool = Field(
        default=False,
        description="If true, skip graph retrieval (vector-only baseline).",
    )


class TraceRoute(BaseModel):
    effective_route: str
    model_route: str
    confidence: float
    rationale: str
    low_confidence_fallback: bool


class TraceFact(BaseModel):
    source_name: str
    rel_type: str
    target_name: str
    source_chunk_ids: List[str]


class TraceGraph(BaseModel):
    template_ids: List[str]
    plan_rationale: str
    facts: List[TraceFact]


class TracePassage(BaseModel):
    chunk_id: str
    section: str
    score: float
    text_preview: str


class TraceVector(BaseModel):
    ticker: Optional[str] = None
    k: int
    passages: List[TracePassage]


class TraceEvidenceItem(BaseModel):
    source_label: str
    statement: str
    chunk_ids: List[str]
    section: Optional[str] = None
    score: Optional[float] = None


class TraceEvidence(BaseModel):
    items: List[TraceEvidenceItem]
    allowed_chunk_ids: List[str]


class TraceAnswer(BaseModel):
    summary: str
    claims: List[AnswerClaim]
    refused: bool


class TraceValidation(BaseModel):
    citations_valid: bool
    regenerated: bool
    attempts: int


class AskTrace(BaseModel):
    """What the demo draws. A view of one AnswerResult, not a second retrieval."""

    route: TraceRoute
    graph: Optional[TraceGraph] = None
    vector: Optional[TraceVector] = None
    evidence: TraceEvidence
    answer: TraceAnswer
    validation: TraceValidation


class AskResponse(BaseModel):
    question: str
    summary: str
    claims: List[AnswerClaim]
    refused: bool
    citations_valid: bool
    regenerated: bool
    attempts: int
    model: str
    route_effective: str
    allowed_chunk_ids: List[str]
    evidence_item_count: int
    trace: AskTrace


def _clip(text: str, limit: int) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _ids(values: List[str], limit: int = _MAX_CHUNK_IDS) -> List[str]:
    return [v for v in values if v][:limit]


def build_trace(result: AnswerResult) -> AskTrace:
    """Project an answer onto the fields the demo is allowed to show."""
    routing = result.retrieval.routing
    graph_result = result.retrieval.graph
    vector_result = result.retrieval.vector

    graph: Optional[TraceGraph] = None
    if graph_result is not None:
        template_ids = [item.value for item in graph_result.template_ids]
        if not template_ids:
            template_ids = [graph_result.template_id.value]
        graph = TraceGraph(
            template_ids=template_ids,
            plan_rationale=_clip(graph_result.plan_rationale, _STATEMENT_CHARS),
            facts=[
                TraceFact(
                    source_name=fact.source_name,
                    rel_type=fact.rel_type,
                    target_name=fact.target_name,
                    source_chunk_ids=_ids(fact.source_chunk_ids),
                )
                for fact in graph_result.facts[:_MAX_FACTS]
            ],
        )

    vector: Optional[TraceVector] = None
    if vector_result is not None:
        vector = TraceVector(
            ticker=vector_result.ticker,
            k=vector_result.k,
            passages=[
                TracePassage(
                    chunk_id=passage.chunk_id,
                    section=passage.section,
                    score=passage.score,
                    text_preview=_clip(
                        passage.text_preview or passage.text,
                        _PREVIEW_CHARS,
                    ),
                )
                for passage in vector_result.passages[:_MAX_PASSAGES]
            ],
        )

    return AskTrace(
        route=TraceRoute(
            effective_route=routing.effective_route.value,
            model_route=routing.model_route.value,
            confidence=routing.confidence,
            rationale=_clip(routing.rationale, _STATEMENT_CHARS),
            low_confidence_fallback=routing.low_confidence_fallback,
        ),
        graph=graph,
        vector=vector,
        evidence=TraceEvidence(
            items=[
                TraceEvidenceItem(
                    source_label=item.source_label,
                    statement=_clip(item.statement, _STATEMENT_CHARS),
                    chunk_ids=_ids(item.chunk_ids),
                    section=item.section,
                    score=item.score,
                )
                for item in result.evidence.items[:_MAX_EVIDENCE]
            ],
            allowed_chunk_ids=list(result.evidence.allowed_chunk_ids),
        ),
        answer=TraceAnswer(
            summary=result.draft.summary,
            claims=result.draft.claims,
            refused=result.draft.refused,
        ),
        validation=TraceValidation(
            citations_valid=result.citations_valid,
            regenerated=result.regenerated,
            attempts=result.attempts,
        ),
    )


def ask_response_from_result(result: AnswerResult) -> AskResponse:
    trace = build_trace(result)
    return AskResponse(
        question=result.question,
        summary=result.draft.summary,
        claims=result.draft.claims,
        refused=result.draft.refused,
        citations_valid=result.citations_valid,
        regenerated=result.regenerated,
        attempts=result.attempts,
        model=result.model,
        route_effective=result.retrieval.routing.effective_route.value,
        allowed_chunk_ids=result.evidence.allowed_chunk_ids,
        evidence_item_count=len(result.evidence.items),
        trace=trace,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest) -> AskResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")

    force = RetrievalRoute.VECTOR if body.vector_only else None
    try:
        result = answer_question(
            question,
            ticker=body.ticker,
            log_route=not body.vector_only,
            force_route=force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc

    return ask_response_from_result(result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
