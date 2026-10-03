"""
LLM-as-judge scoring for the benchmark suite.

Primary metric: Haiku + Instructor grades the model answer against hand-authored
required_facts (+ optional gold_answer). Keyword recall stays as a secondary check.

Cheap to re-run on saved answer text without re-calling the answer model.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

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


class JudgeVerdict(BaseModel):
    """Structured grade for one (question, answer) pair."""

    fact_judgments: List[FactJudgment] = Field(default_factory=list)
    overall_correctness: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="0=wrong/missing, 0.5=partial, 1=covers required facts adequately.",
    )
    has_major_hallucination: bool = Field(
        ...,
        description="True if the answer invents material facts not supported by the "
        "gold answer / required facts (not mere omission).",
    )
    rationale: str = Field(..., description="One or two sentences.")


JUDGE_SYSTEM_PROMPT = """
You grade answers from a SEC 10-K RAG system.

You are given:
- the user question
- required_facts: atomic claims a good answer should cover (paraphrase is fine)
- gold_answer: a short reference (authoritative for this eval; may be incomplete prose)
- the model answer (summary + claims)

Rules:
- Score coverage of required_facts, not writing style.
- Paraphrases and reasonable synonyms count as covered.
- Omissions → lower correctness; do not invent facts the model "should have" beyond required_facts.
- overall_correctness: fraction of required_facts covered, or 0/0.5/1 if that better matches quality.
  If required_facts is empty, score against gold_answer alone (1=matches, 0.5=partial, 0=wrong/refuse).
- has_major_hallucination: only for clear invented material that contradicts gold/required facts
  (not for extra correct detail).
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


def judge_answer(
    item: BenchmarkItem,
    answer_text: str,
    *,
    refused: bool = False,
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

    user = (
        f"Question:\n{item.question}\n\n"
        f"Required facts:\n{facts_block}\n\n"
        f"Gold answer:\n{gold}\n\n"
        f"Model answer:\n{text}\n"
    )

    cli = client or _build_client()
    verdict = cli.messages.create(
        model=settings.ROUTER_MODEL,
        max_tokens=min(1024, settings.ROUTER_MAX_TOKENS * 2),
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
        response_model=JudgeVerdict,
        max_retries=settings.ROUTER_MAX_RETRIES,
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
