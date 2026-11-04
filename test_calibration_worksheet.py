"""Slice rules and worksheet parsing. Uses the repo's calibration files."""

from __future__ import annotations

from calibration_worksheet import (
    DEBUG_IDS,
    SELF_AGREEMENT_IDS,
    holdout_ids,
    load_suite,
    parse_filled_scores,
    parse_legacy_worksheet,
)
from pathlib import Path


def test_holdout_is_the_items_outside_the_debug_sheet():
    suite_ids = [item["id"] for item in load_suite()["items"]]
    holdout = holdout_ids(suite_ids)
    assert set(holdout).isdisjoint(DEBUG_IDS)
    assert len(holdout) == 20
    assert len(suite_ids) == len(DEBUG_IDS) + len(holdout)


def test_self_agreement_slice_is_inside_the_debug_sheet():
    assert set(SELF_AGREEMENT_IDS) <= set(DEBUG_IDS)
    assert len(SELF_AGREEMENT_IDS) == 15
    assert "hop0_jpm_credit_risk" in SELF_AGREEMENT_IDS
    assert "hop2_jpm_credit_vs_market" in SELF_AGREEMENT_IDS


def test_legacy_sheet_has_a_score_for_every_debug_item():
    text = Path("benchmarks/judge_calibration_hybrid.md").read_text()
    parsed = parse_legacy_worksheet(text)
    assert set(parsed) == set(DEBUG_IDS)
    assert parsed["hop0_jpm_credit_risk"]["first_pass_score"] == 0.5
    assert parsed["hop2_jpm_credit_vs_market"]["first_pass_score"] == 0.375
    assert "Judge rationale" not in parsed["hop0_aapl_applecare"]["body"]
    assert parsed["hop0_jpm_credit_risk"]["body"].strip().endswith("- note:")
    assert "- your_score:\n" in parsed["hop0_aapl_applecare"]["body"]


def test_blank_score_parses_as_missing():
    text = """# header

## `one`

- your_score:
- note:

## `two`

- your_score: 0.5
- note:
"""
    assert parse_filled_scores(text) == {"one": None, "two": 0.5}
