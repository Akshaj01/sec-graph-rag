"""
Phase 4 Steps N+O: Merge evidence into a grounded answer; validate citations.

Flow:
  HybridRetrievalResult → labeled evidence → Claude/Instructor draft
  → validate each citation_chunk_id ∈ allowed set → regenerate once if invalid

WHY validate: models invent plausible chunk ids; only cites from *this* retrieve
call are trustworthy for SEC Q&A.

Out of scope: portfolio-scale benchmark (Phase 5).
"""

from __future__ import annotations

import json
from typing import List, Optional, Set

import anthropic
import instructor
from pydantic import BaseModel, Field

from config import settings
from graph_retriever import GraphFact
from retrieve import HybridRetrievalResult, retrieve
from router import RetrievalRoute


# Human-readable templates for ontology edge types (deterministic — not LLM).
_REL_PHRASE = {
    "OWNS_SUBSIDIARY": "owns subsidiary",
    "SUPPLIED_BY": "is supplied by",
    "COMPETES_WITH": "competes with",
    "EXPOSED_TO_RISK": "is exposed to risk",
    "PRODUCES_PRODUCT": "produces product",
    "DEPENDS_ON": "depends on",
    "LED_BY": "is led by",
    "OPERATES_IN_SEGMENT": "operates in segment",
}


class AnswerClaim(BaseModel):
    """One atomic claim that must be backed by retrieved chunk id(s)."""

    text: str = Field(..., description="A single factual claim answering part of the question.")
    citation_chunk_ids: List[str] = Field(
        ...,
        min_length=1,
        description="chunk_id values from the evidence pack that support this claim. "
        "Must be copied exactly from GRAPH or VECTOR evidence — never invented.",
    )


class GroundedAnswerDraft(BaseModel):
    """Structured LLM output (validated by Step O before trust)."""

    summary: str = Field(
        ...,
        description="Short natural-language answer synthesizing the claims.",
    )
    claims: List[AnswerClaim] = Field(
        ...,
        min_length=1,
        description="Atomic claims; every claim needs at least one citation_chunk_id.",
    )
    refused: bool = Field(
        default=False,
        description="True if evidence is insufficient to answer; claims may explain the gap.",
    )


class LabeledEvidenceItem(BaseModel):
    """One block shown to the answer model, labeled by provenance."""

    source_label: str  # GRAPH | VECTOR
    statement: str
    chunk_ids: List[str] = Field(default_factory=list)
    section: Optional[str] = None
    score: Optional[float] = None


class EvidencePack(BaseModel):
    """Deduplicated, labeled context + allowlist for citation validation."""

    question: str
    items: List[LabeledEvidenceItem] = Field(default_factory=list)
    allowed_chunk_ids: List[str] = Field(default_factory=list)
    prompt_text: str = ""


class CitationIssue(BaseModel):
    claim_index: int
    claim_text: str
    bad_chunk_ids: List[str] = Field(default_factory=list)
    reason: str


class CitationValidationResult(BaseModel):
    valid: bool
    issues: List[CitationIssue] = Field(default_factory=list)

    def error_summary(self) -> str:
        if self.valid:
            return ""
        lines = []
        for issue in self.issues:
            bad = ", ".join(issue.bad_chunk_ids) if issue.bad_chunk_ids else "(none)"
            lines.append(
                f"- claim[{issue.claim_index}]: {issue.reason} "
                f"bad_ids=[{bad}] text={issue.claim_text[:120]!r}"
            )
        return "\n".join(lines)


class AnswerResult(BaseModel):
    """Final answer after citation validation (and optional regenerate)."""

    question: str
    retrieval: HybridRetrievalResult
    evidence: EvidencePack
    draft: GroundedAnswerDraft
    model: str
    citations_valid: bool
    regenerated: bool = False
    attempts: int = 1
    validation_issues: List[CitationIssue] = Field(default_factory=list)


ANSWER_SYSTEM_PROMPT = """
You answer questions about SEC 10-K filings using ONLY the labeled evidence provided.

Evidence labels:
- [GRAPH]: structured facts from the knowledge graph (relationships). Prefer these for
  who/what is connected, products, risks, suppliers, competitors, subsidiaries.
- [VECTOR]: retrieved filing passages. Prefer these for definitions and narrative detail.

Rules:
1. Every claim must include citation_chunk_ids copied EXACTLY from the chunk_ids listed
   on the evidence items you used. Never invent or guess a chunk_id.
2. Prefer one clear claim per distinct fact; do not merge unrelated facts into one claim.
3. If evidence is missing or insufficient, set refused=true and explain what is missing
   in summary/claims without fabricating filing content.
4. Do not use outside knowledge of the company beyond the evidence pack.
5. When the allowed citation list is empty, set refused=true and explain the gap;
   do not invent chunk_ids.
""".strip()


def fact_to_statement(fact: GraphFact) -> str:
    """Deterministic graph path → readable statement."""
    phrase = _REL_PHRASE.get(fact.rel_type, fact.rel_type.replace("_", " ").lower())
    base = f"{fact.source_name} {phrase} {fact.target_name}."
    if fact.context:
        ctx = " ".join(fact.context.split())
        if len(ctx) > 280:
            ctx = ctx[:277] + "..."
        return f"{base} Context: {ctx}"
    return base


def collect_allowed_chunk_ids(retrieval: HybridRetrievalResult) -> List[str]:
    """Union of graph edge source_chunk_ids and vector passage chunk_ids."""
    ids: Set[str] = set()
    if retrieval.graph:
        for fact in retrieval.graph.facts:
            for cid in fact.source_chunk_ids:
                if cid:
                    ids.add(str(cid))
    if retrieval.vector:
        for passage in retrieval.vector.passages:
            if passage.chunk_id:
                ids.add(str(passage.chunk_id))
    return sorted(ids)


def format_evidence(retrieval: HybridRetrievalResult) -> EvidencePack:
    """
    Convert retrieve.py output into labeled, deduplicated prompt blocks.

    Dedup keys:
    - GRAPH: (statement text, frozenset of chunk ids)
    - VECTOR: chunk_id (keep highest-score passage if duplicates appear)
    """
    items: List[LabeledEvidenceItem] = []
    seen_graph: Set[tuple] = set()
    seen_vector: Set[str] = set()

    if retrieval.graph:
        for fact in retrieval.graph.facts:
            statement = fact_to_statement(fact)
            chunk_ids = [str(c) for c in fact.source_chunk_ids if c]
            key = (statement, tuple(sorted(chunk_ids)))
            if key in seen_graph:
                continue
            seen_graph.add(key)
            items.append(
                LabeledEvidenceItem(
                    source_label="GRAPH",
                    statement=statement,
                    chunk_ids=chunk_ids,
                )
            )

    if retrieval.vector:
        for passage in retrieval.vector.passages:
            cid = str(passage.chunk_id)
            if cid in seen_vector:
                continue
            seen_vector.add(cid)
            text = " ".join(passage.text.split())
            items.append(
                LabeledEvidenceItem(
                    source_label="VECTOR",
                    statement=text,
                    chunk_ids=[cid],
                    section=passage.section,
                    score=passage.score,
                )
            )

    allowed = collect_allowed_chunk_ids(retrieval)
    prompt_text = _render_evidence_prompt(retrieval.question, items, allowed)
    return EvidencePack(
        question=retrieval.question,
        items=items,
        allowed_chunk_ids=allowed,
        prompt_text=prompt_text,
    )


def _render_evidence_prompt(
    question: str,
    items: List[LabeledEvidenceItem],
    allowed_chunk_ids: List[str],
) -> str:
    lines: List[str] = [
        f"Question: {question}",
        "",
        "Allowed citation chunk_ids (copy exactly):",
        ", ".join(allowed_chunk_ids) if allowed_chunk_ids else "(none retrieved)",
        "",
        "Evidence:",
    ]
    if not items:
        lines.append("(no graph facts or vector passages retrieved)")
        return "\n".join(lines)

    for i, item in enumerate(items, start=1):
        ids = ", ".join(item.chunk_ids) if item.chunk_ids else "(no chunk_ids)"
        meta = ""
        if item.source_label == "VECTOR" and item.section:
            score_bit = f", score={item.score:.4f}" if item.score is not None else ""
            meta = f" section={item.section}{score_bit}"
        lines.append(f"{i}. [{item.source_label}] chunk_ids=[{ids}]{meta}")
        lines.append(item.statement)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def validate_citations(
    draft: GroundedAnswerDraft,
    allowed_chunk_ids: List[str],
) -> CitationValidationResult:
    """
    Every citation must resolve to a retrieved chunk id.

    Special case: empty allowlist + refused=True → valid (nothing to cite).
    Claims may still carry placeholder ids from the schema min_length=1 constraint;
    those are ignored when refused with zero retrieved evidence.
    """
    allowed = {str(c) for c in allowed_chunk_ids if c}

    if not allowed:
        if draft.refused:
            return CitationValidationResult(valid=True, issues=[])
        return CitationValidationResult(
            valid=False,
            issues=[
                CitationIssue(
                    claim_index=-1,
                    claim_text=draft.summary,
                    bad_chunk_ids=[],
                    reason="No retrieved chunk_ids but refused=false; must refuse or cite evidence.",
                )
            ],
        )

    issues: List[CitationIssue] = []
    for idx, claim in enumerate(draft.claims):
        cites = [str(c).strip() for c in claim.citation_chunk_ids if str(c).strip()]
        if not cites:
            issues.append(
                CitationIssue(
                    claim_index=idx,
                    claim_text=claim.text,
                    bad_chunk_ids=[],
                    reason="Claim has no citation_chunk_ids.",
                )
            )
            continue
        bad = [c for c in cites if c not in allowed]
        if bad:
            issues.append(
                CitationIssue(
                    claim_index=idx,
                    claim_text=claim.text,
                    bad_chunk_ids=bad,
                    reason="Citation chunk_id not in retrieved allowlist.",
                )
            )

    return CitationValidationResult(valid=len(issues) == 0, issues=issues)


def _refusal_fallback(question: str) -> GroundedAnswerDraft:
    """Deterministic refused answer when validation still fails after regenerate."""
    return GroundedAnswerDraft(
        summary=(
            "I could not produce a grounded answer with citations that resolve to "
            "retrieved filing chunks. Please rephrase or check that graph/vector "
            "retrieval returned evidence."
        ),
        claims=[
            AnswerClaim(
                text="Insufficient validated evidence to answer this question.",
                # Placeholder required by schema; empty allowlist + refused is accepted.
                citation_chunk_ids=["UNAVAILABLE"],
            )
        ],
        refused=True,
    )


def _build_client() -> instructor.Instructor:
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY is missing. Set it in your .env before answer generation."
        )
    raw = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    mode = getattr(instructor.Mode, "ANTHROPIC_TOOLS", None) or instructor.Mode.TOOLS
    return instructor.from_anthropic(raw, mode=mode)


def generate_draft(
    evidence: EvidencePack,
    *,
    client: Optional[instructor.Instructor] = None,
    repair_note: Optional[str] = None,
) -> GroundedAnswerDraft:
    """Instructor call: labeled evidence → structured claims + citations."""
    client = client or _build_client()
    user_content = evidence.prompt_text
    if repair_note:
        user_content = (
            f"{evidence.prompt_text}\n\n"
            f"CITATION REPAIR (previous answer was rejected):\n{repair_note}\n"
            "Rewrite the full answer. Use ONLY chunk_ids from the allowed list above. "
            "If you cannot cite valid ids, set refused=true.\n"
        )

    return client.messages.create(
        model=settings.ANSWER_MODEL,
        max_tokens=settings.ANSWER_MAX_TOKENS,
        max_retries=settings.ANSWER_MAX_RETRIES,
        temperature=0.0,
        system=ANSWER_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": user_content,
            }
        ],
        response_model=GroundedAnswerDraft,
    )


def generate_validated_answer(
    evidence: EvidencePack,
    *,
    client: Optional[instructor.Instructor] = None,
    max_regenerates: Optional[int] = None,
) -> tuple[GroundedAnswerDraft, CitationValidationResult, int, bool]:
    """
    Draft → validate → optional regenerate with repair note.

    Returns (draft, last_validation, attempts, regenerated).
    """
    client = client or _build_client()
    max_regenerates = (
        settings.ANSWER_CITATION_REGENERATE_ATTEMPTS
        if max_regenerates is None
        else max_regenerates
    )

    draft = generate_draft(evidence, client=client)
    validation = validate_citations(draft, evidence.allowed_chunk_ids)
    attempts = 1
    regenerated = False

    while not validation.valid and attempts <= max_regenerates:
        repair = (
            "Invalid citations detected:\n"
            f"{validation.error_summary()}\n\n"
            "Allowed chunk_ids only:\n"
            + (
                ", ".join(evidence.allowed_chunk_ids)
                if evidence.allowed_chunk_ids
                else "(none — you must set refused=true)"
            )
        )
        draft = generate_draft(evidence, client=client, repair_note=repair)
        validation = validate_citations(draft, evidence.allowed_chunk_ids)
        attempts += 1
        regenerated = True

    if not validation.valid:
        # Hard stop: never return an answer with invented cites.
        draft = _refusal_fallback(evidence.question)
        if evidence.allowed_chunk_ids:
            # Attach a real id so the fallback itself validates when evidence existed
            # but the model kept inventing cites — still refuse rather than lie.
            draft = GroundedAnswerDraft(
                summary=draft.summary,
                claims=[
                    AnswerClaim(
                        text=draft.claims[0].text,
                        citation_chunk_ids=[evidence.allowed_chunk_ids[0]],
                    )
                ],
                refused=True,
            )
        validation = validate_citations(draft, evidence.allowed_chunk_ids)

    return draft, validation, attempts, regenerated


def answer_question(
    question: str,
    *,
    ticker: Optional[str] = None,
    log_route: bool = True,
    retrieval: Optional[HybridRetrievalResult] = None,
    force_route: Optional[RetrievalRoute] = None,
) -> AnswerResult:
    """Retrieve → format evidence → draft → validate citations (regenerate if needed)."""
    if retrieval is None:
        pack = retrieve(
            question,
            ticker=ticker,
            log_route=log_route,
            force_route=force_route,
        )
    else:
        pack = retrieval
    evidence = format_evidence(pack)
    draft, validation, attempts, regenerated = generate_validated_answer(evidence)
    return AnswerResult(
        question=question,
        retrieval=pack,
        evidence=evidence,
        draft=draft,
        model=settings.ANSWER_MODEL,
        citations_valid=validation.valid,
        regenerated=regenerated,
        attempts=attempts,
        validation_issues=validation.issues,
    )


if __name__ == "__main__":
    import sys

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    question = " ".join(args) if args else "What product lines does Apple produce?"
    result = answer_question(question)

    out = {
        "question": result.question,
        "model": result.model,
        "citations_valid": result.citations_valid,
        "regenerated": result.regenerated,
        "attempts": result.attempts,
        "validation_issues": [i.model_dump() for i in result.validation_issues],
        "routing": result.retrieval.routing.model_dump(),
        "allowed_chunk_ids": result.evidence.allowed_chunk_ids,
        "evidence_item_count": len(result.evidence.items),
        "evidence_labels": [i.source_label for i in result.evidence.items],
        "draft": result.draft.model_dump(),
    }
    print(json.dumps(out, indent=2))
