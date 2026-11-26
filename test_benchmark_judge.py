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


# --- Rubric v2: the judge is grounded in the cited passages -----------------

import sqlite3
from types import SimpleNamespace

import chunk_ticker
from benchmark_judge import (
    JudgeOutput,
    SuspectClaim,
    is_major_hallucination,
    judge_answer,
    render_passages,
)
from calibration_worksheet import rescored_holdout_keys


def _claim(supported: bool, contradicts: bool = False) -> SuspectClaim:
    return SuspectClaim(
        claim="Apple sells the MacBook Neo.",
        supported_by_cited_passage=supported,
        contradicts_gold=contradicts,
    )


def test_a_claim_a_cited_passage_supports_is_never_a_hallucination():
    assert not is_major_hallucination([_claim(True, contradicts=True)], has_evidence=True)
    assert is_major_hallucination([_claim(False)], has_evidence=True)


def test_without_passages_only_a_gold_contradiction_counts():
    # The judge's own knowledge is never the test.
    assert not is_major_hallucination([_claim(False)], has_evidence=False)
    assert is_major_hallucination([_claim(False, contradicts=True)], has_evidence=False)


def test_render_passages_keeps_whole_chunks():
    long_text = "x" * 13000 + " MacBook Neo"
    rendered = render_passages([("A:Item1:0", long_text), ("A:Item1:1", "  ")])
    assert rendered.endswith("MacBook Neo")
    assert "A:Item1:1" not in rendered


class _FakeJudge:
    def __init__(self, output: JudgeOutput):
        self.output = output
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.output


def _apple_item() -> BenchmarkItem:
    return BenchmarkItem(
        id="hop2_aapl_hardware_services",
        question="What hardware devices and services does Apple produce?",
        hop=HopBucket.HOP_2,
        required_facts=["Mentions two hardware devices", "Mentions a service"],
        gold_answer="iPhone, Mac, iPad; AppleCare and other services.",
    )


def _covered_output(claims: list[SuspectClaim]) -> JudgeOutput:
    return JudgeOutput(
        fact_judgments=[
            FactJudgment(fact="Mentions two hardware devices", covered=True),
            FactJudgment(fact="Mentions a service", covered=True),
        ],
        overall_correctness=1.0,
        suspect_claims=claims,
        rationale="Covers both facts.",
    )


def test_supported_new_product_names_are_not_capped():
    fake = _FakeJudge(_covered_output([_claim(True)]))
    verdict = judge_answer(
        _apple_item(),
        "iPhone 17e, MacBook Neo, and services.",
        evidence=[("0000320193-25-000079:Item1:0", "Apple's products include MacBook Neo.")],
        client=fake,
    )
    assert verdict.has_major_hallucination is False
    assert verdict.overall_correctness == 1.0
    prompt = fake.calls[0]["messages"][0]["content"]
    assert "Cited passages:" in prompt and "MacBook Neo" in prompt
    assert fake.calls[0]["response_model"] is JudgeOutput


def test_an_unsupported_claim_is_still_capped():
    fake = _FakeJudge(_covered_output([_claim(False)]))
    verdict = judge_answer(
        _apple_item(),
        "iPhone 99 and services.",
        evidence=[("0000320193-25-000079:Item1:0", "Apple sells the iPhone.")],
        client=fake,
    )
    assert verdict.has_major_hallucination is True
    assert verdict.overall_correctness == 0.5


def test_chunk_texts_reads_the_ingest_cache(tmp_path, monkeypatch):
    db = tmp_path / "ingest_cache.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE chunks (chunk_id TEXT PRIMARY KEY, text TEXT)")
        conn.executemany(
            "INSERT INTO chunks VALUES (?, ?)",
            [("A:Item1:0", "first"), ("A:Item1:1", "second")],
        )
    monkeypatch.setattr(chunk_ticker.settings, "INGEST_CACHE_PATH", str(db))
    monkeypatch.setattr(
        "vector_db.get_connection",
        lambda: (_ for _ in ()).throw(RuntimeError("no pgvector in tests")),
    )
    got = chunk_ticker.chunk_texts(["A:Item1:1", "missing:Item1:0", "A:Item1:0", "A:Item1:1"])
    assert got == [("A:Item1:1", "second"), ("A:Item1:0", "first")]


def test_calibration_takes_judge_scores_from_a_rejudged_file(tmp_path):
    keys = {"holdout": [{"id": "a", "judge_score": 0.5}, {"id": "b", "judge_score": 1.0}]}
    judged = tmp_path / "rejudged.json"
    judged.write_text(
        '{"hybrid": {"results": [{"item_id": "a", "score": 1.0}, {"item_id": "b", "score": 1.0}]}}'
    )
    assert rescored_holdout_keys(keys, judged) == [
        {"id": "a", "judge_score": 1.0},
        {"id": "b", "judge_score": 1.0},
    ]


def test_suspect_claim_without_contradicts_gold_still_validates():
    # Haiku left contradicts_gold out on hop1_msft_products and crashed the run.
    raw = {
        "overall_correctness": 0.5,
        "rationale": "Misses Azure and Xbox.",
        "fact_judgments": [{"fact": "Mentions Azure", "covered": False}],
        "suspect_claims": [
            {"claim": "Microsoft produces Dynamics 365.", "supported_by_cited_passage": True, "note": "In Item 1."}
        ],
    }
    out = JudgeOutput.model_validate(raw)
    assert out.suspect_claims[0].contradicts_gold is False


def test_judge_retries_as_fresh_requests_without_reask():
    class _Flaky(_FakeJudge):
        def _create(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                raise RuntimeError("malformed tool output")
            return self.output

    fake = _Flaky(_covered_output([]))
    verdict = judge_answer(_apple_item(), "iPhone, Mac, and AppleCare.", client=fake)
    assert verdict.overall_correctness == 1.0
    assert len(fake.calls) == 2
    assert all(call["max_retries"] == 1 for call in fake.calls)
