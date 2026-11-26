"""
LLM-as-judge scoring for the benchmark suite.

Primary metric: Haiku + Instructor grades the model answer against hand-authored
required_facts (+ optional gold_answer). Keyword recall stays as a secondary check.

Cheap to re-run on saved answer text without re-calling the answer model.

Grounding (rubric v2): the judge sees the 10-K passages the answer cites. A
claim a cited passage supports is never a hallucination, even when the judge
model has not heard of it. The judge lists suspect claims and marks each as
supported or not. Code, not the judge, sets the hallucination flag from that
list.

WHY: rubric v1 let the judge use its own knowledge. It marked iPhone 17e and
MacBook Neo as invented when Apple's 10-K named them, because both shipped
after the judge model's training cutoff.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import anthropic
import instructor
from pydantic import BaseModel, Field

from benchmark_schema import BenchmarkItem
from config import settings


class FactJudgment(BaseModel):
    fact: str = Field(..., description="The required fact being graded.")
    covered: bool = Field(
        ...,
        description="True if the answer clearly covers this fact (paraphrase OK).",
    )
    note: str = Field(default="", description="Brief justification.")


class SuspectClaim(BaseModel):
    claim: str = Field(..., description="A material claim in the answer you doubt.")
    supported_by_cited_passage: bool = Field(
        ...,
        description="True if any cited passage states or clearly implies this claim. "
        "Judge only against the passages, not your own knowledge.",
    )
    contradicts_gold: bool = Field(
        ...,
        description="True if the claim contradicts the gold answer or a required fact.",
    )


class JudgeOutput(BaseModel):
    """What the judge model returns."""

    fact_judgments: List[FactJudgment] = Field(default_factory=list)
    overall_correctness: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="0=wrong/missing, 0.5=partial, 1=covers required facts adequately.",
    )
    suspect_claims: List[SuspectClaim] = Field(
        default_factory=list,
        description="Material claims that may be invented. Empty if none.",
    )
    rationale: str = Field(..., description="One or two sentences.")


class JudgeVerdict(BaseModel):
    """Structured grade for one (question, answer) pair."""

    fact_judgments: List[FactJudgment] = Field(default_factory=list)
    overall_correctness: float = Field(..., ge=0.0, le=1.0)
    has_major_hallucination: bool
    rationale: str
    suspect_claims: List[SuspectClaim] = Field(default_factory=list)


def is_major_hallucination(
    suspect_claims: Sequence[SuspectClaim],
    *,
    has_evidence: bool,
) -> bool:
    """
    A suspect claim counts only if no cited passage supports it. Without
    passages to check against, only a contradiction of the gold answer counts:
    the judge's own knowledge is never the test.
    """
    for claim in suspect_claims:
        if has_evidence:
            if not claim.supported_by_cited_passage:
                return True
        elif claim.contradicts_gold:
            return True
    return False


JUDGE_SYSTEM_PROMPT = """
You grade answers from a SEC 10-K RAG system.

You are given:
- the user question
- required_facts: atomic claims a good answer should cover (paraphrase is fine)
- gold_answer: a short reference (authoritative for this eval; may be incomplete prose)
- the model answer (summary + claims)
- cited passages: the 10-K text the answer cites

Rules:
- Score coverage of required_facts, not writing style.
- Paraphrases and reasonable synonyms count as covered.
- Omissions → lower correctness; do not invent facts the model "should have" beyond required_facts.
- overall_correctness: fraction of required_facts covered, or 0/0.5/1 if that better matches quality.
  If required_facts is empty, score against gold_answer alone (1=matches, 0.5=partial, 0=wrong/refuse).
  Score coverage only. Do not lower it for suspect claims: list those in suspect_claims instead.
- suspect_claims: list material claims that may be invented. For each, check the cited
  passages. Your own knowledge may be out of date: filings name products, people and
  events newer than your training data. Never call a claim invented because you have
  not heard of it. If a cited passage states or implies it, it is supported.
- Extra detail that a cited passage supports is fine and is not a suspect claim.
- Be strict but fair. Do not reward keyword stuffing that fails to answer the question.
"""


def _build_client() -> instructor.Instructor:
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    raw = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    mode = getattr(instructor.Mode, "ANTHROPIC_TOOLS", None) or instructor.Mode.TOOLS
    return instructor.from_anthropic(raw, mode=mode)


def correctness_from_facts(judgments: Sequence[FactJudgment]) -> float:
    if not judgments:
        return 0.0
    return round(sum(1.0 if j.covered else 0.0 for j in judgments) / len(judgments), 4)


def finalize_score(
    *,
    overall_correctness: float,
    has_major_hallucination: bool,
) -> float:
    """Cap score when the judge flags a major hallucination."""
    score = max(0.0, min(1.0, float(overall_correctness)))
    if has_major_hallucination:
        score = min(score, 0.5)
    return round(score, 4)


def render_passages(evidence: Sequence[Tuple[str, str]]) -> str:
    """
    Format (chunk_id, text) pairs for the judge prompt.

    Every cited chunk goes in whole. A trimmed or dropped passage could hide
    the sentence that supports a claim, which is the bug this rubric fixes.
    """
    blocks: List[str] = []
    for chunk_id, text in evidence:
        body = (text or "").strip()
        if body:
            blocks.append(f"[{chunk_id}]\n{body}")
    return "\n\n".join(blocks)


def judge_answer(
    item: BenchmarkItem,
    answer_text: str,
    *,
    refused: bool = False,
    evidence: Sequence[Tuple[str, str]] = (),
    client: Optional[instructor.Instructor] = None,
) -> JudgeVerdict:
    """
    Grade one answer. OOS / must_refuse is handled by the runner (binary refuse),
    not here — pass only non-OOS items.
    """
    if refused:
        return JudgeVerdict(
            fact_judgments=[],
            overall_correctness=0.0,
            has_major_hallucination=False,
            rationale="Non-OOS item refused; scored 0.",
        )

    text = (answer_text or "").strip()
    if not text:
        return JudgeVerdict(
            fact_judgments=[
                FactJudgment(fact=f, covered=False, note="empty answer")
                for f in item.required_facts
            ],
            overall_correctness=0.0,
            has_major_hallucination=False,
            rationale="Empty answer.",
        )

    facts_block = (
        "\n".join(f"- {f}" for f in item.required_facts)
        if item.required_facts
        else "- (none listed; use gold_answer)"
    )
    gold = item.gold_answer.strip() or "(none provided)"

    passages = render_passages(evidence)
    user = (
        f"Question:\n{item.question}\n\n"
        f"Required facts:\n{facts_block}\n\n"
        f"Gold answer:\n{gold}\n\n"
        f"Model answer:\n{text}\n\n"
        f"Cited passages:\n{passages or '(none available)'}\n"
    )

    cli = client or _build_client()
    output = cli.messages.create(
        model=settings.ROUTER_MODEL,
        max_tokens=min(1024, settings.ROUTER_MAX_TOKENS * 2),
        temperature=0.0,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
        response_model=JudgeOutput,
        max_retries=settings.ROUTER_MAX_RETRIES,
    )
    verdict = JudgeVerdict(
        fact_judgments=output.fact_judgments,
        overall_correctness=output.overall_correctness,
        has_major_hallucination=is_major_hallucination(
            output.suspect_claims, has_evidence=bool(passages)
        ),
        rationale=output.rationale,
        suspect_claims=output.suspect_claims,
    )

    # Prefer fact-coverage if judgments present; otherwise trust overall.
    if verdict.fact_judgments:
        derived = correctness_from_facts(verdict.fact_judgments)
        # Blend: mostly fact coverage, allow judge overall to pull slightly.
        blended = round(0.75 * derived + 0.25 * float(verdict.overall_correctness), 4)
        verdict.overall_correctness = blended

    verdict.overall_correctness = finalize_score(
        overall_correctness=verdict.overall_correctness,
        has_major_hallucination=verdict.has_major_hallucination,
    )
    return verdict


def apply_verdict_to_fields(verdict: JudgeVerdict) -> dict:
    hits = [j.fact for j in verdict.fact_judgments if j.covered]
    misses = [j.fact for j in verdict.fact_judgments if not j.covered]
    return {
        "judge_correctness": verdict.overall_correctness,
        "judge_fact_hits": hits,
        "judge_fact_misses": misses,
        "judge_hallucination": verdict.has_major_hallucination,
        "judge_rationale": verdict.rationale,
        "score": verdict.overall_correctness,
    }
