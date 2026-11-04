"""Recall gate tests. The v4 file is a fixture, not a live retrieval."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from recall_gate import (
    DEFAULT_BASELINE,
    DEFAULT_RESULTS,
    build_baseline,
    degrade_first,
    evaluate,
    macro_recall,
)

RESULTS = json.loads(DEFAULT_RESULTS.read_text(encoding="utf-8"))
BASELINE = json.loads(DEFAULT_BASELINE.read_text(encoding="utf-8"))


def test_saved_report_passes_the_pinned_baseline():
    result = evaluate(RESULTS, BASELINE)
    assert result["ok"]
    assert result["drop"] == pytest.approx(0.0)


def test_two_point_drop_still_passes():
    report = json.loads(json.dumps(RESULTS))
    items = report["systems"]["hybrid"]["items"]
    # 0.02 * 32 = 0.64, spread so no score goes negative.
    take = 0.02
    for item in items:
        item["recall_at_10"] = float(item["recall_at_10"]) - take
    result = evaluate(report, BASELINE)
    assert result["drop"] == pytest.approx(0.02)
    assert result["ok"]


def test_zeroing_one_hit_fails():
    report = degrade_first(RESULTS)
    result = evaluate(report, BASELINE)
    assert result["ok"] is False
    assert result["drop"] > 0.02


def test_changed_item_list_fails():
    report = json.loads(json.dumps(RESULTS))
    report["systems"]["hybrid"]["items"].pop()
    result = evaluate(report, BASELINE)
    assert result["ok"] is False
    assert result["drop"] is None


def test_baseline_matches_the_report():
    fresh = build_baseline(RESULTS)
    score, ids = macro_recall(RESULTS)
    assert fresh["recall_at_10"] == pytest.approx(score)
    assert fresh["item_ids"] == ids
    assert Path(DEFAULT_BASELINE).exists()
