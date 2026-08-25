"""
Phase 5 Step T: FastAPI wrapper for grounded SEC Q&A.

POST /ask → answer_question (validated citations).
GET /health → liveness for Docker / local dev.

WHY thin wrapper: all logic stays in answer.py; API only shapes I/O for clients.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from answer import AnswerClaim, answer_question
from router import RetrievalRoute

app = FastAPI(
    title="SEC GraphRAG",
    description="Hybrid knowledge graph + vector RAG over SEC 10-K filings.",
    version="0.1.0",
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
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
