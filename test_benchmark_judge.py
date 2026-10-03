"""Free unit tests for LLM-judge helpers and keyword/OOS scoring (no API)."""

from __future__ import annotations

from benchmark_judge import (
    FactJudgment,
    JudgeVerdict,
    apply_verdict_to_fields,
    correctness_from_facts,
    finalize_score,
)
from benchmark_runner import ScoreMode, _score_answer_fields, score_keywords
from benchmark_schema import BenchmarkItem, HopBucket


def test_correctness_from_facts():
    js = [
        FactJudgment(fact="a", covered=True),
        FactJudgment(fact="b", covered=False),
        FactJudgment(fact="c", covered=True),
    ]
    assert correctness_from_facts(js) == round(2 / 3, 4)


def test_finalize_score_caps_hallucination():
    assert finalize_score(overall_correctness=1.0, has_major_hallucination=True) == 0.5
    assert finalize_score(overall_correctness=0.25, has_major_hallucination=True) == 0.25
    assert finalize_score(overall_correctness=0.9, has_major_hallucination=False) == 0.9


def test_apply_verdict_to_fields():
    v = JudgeVerdict(
        fact_judgments=[
            FactJudgment(fact="Mentions iPhone", covered=True),
            FactJudgment(fact="Mentions Mac", covered=False),
        ],
        overall_correctness=0.5,
        has_major_hallucination=False,
        rationale="Partial",
    )
    fields = apply_verdict_to_fields(v)
    assert fields["score"] == 0.5
    assert fields["judge_fact_hits"] == ["Mentions iPhone"]
    assert fields["judge_fact_misses"] == ["Mentions Mac"]


def test_oos_binary_score_no_judge():
    item = BenchmarkItem(
        id="oos_x",
        question="Tesla?",
        hop=HopBucket.HOP_0,
        must_refuse=True,
        required_facts=[],
    )
    ok = _score_answer_fields(
        item,
        answer_text="I don't know",
        refused=True,
        citations_valid=True,
        score_mode=ScoreMode.JUDGE,
    )
    bad = _score_answer_fields(
        item,
        answer_text="Tesla batteries...",
        refused=False,
        citations_valid=True,
        score_mode=ScoreMode.JUDGE,
    )
    assert ok["score"] == 1.0 and ok["correct_refuse"] is True
    assert bad["score"] == 0.0 and bad["correct_refuse"] is False


def test_keyword_mode_still_works():
    item = BenchmarkItem(
        id="hop1_x",
        question="Products?",
        hop=HopBucket.HOP_1,
        gold_keywords=["iPhone", "Mac"],
        required_facts=["Mentions iPhone"],
    )
    fields = _score_answer_fields(
        item,
        answer_text="Apple makes the iPhone and Mac.",
        refused=False,
        citations_valid=True,
        score_mode=ScoreMode.KEYWORD,
    )
    assert fields["keyword_recall"] == 1.0
    assert fields["score"] == 1.0


def test_score_keywords_case_insensitive():
    hits, misses, recall = score_keywords("AppleCare support plan", ["applecare", "SERVICE"])
    assert hits == ["applecare"]
    assert misses == ["SERVICE"]
    assert recall == 0.5
