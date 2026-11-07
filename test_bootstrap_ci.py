"""Pure tests for the paired bootstrap. No judged file required."""

from __future__ import annotations

import pytest

from bootstrap_ci import (
    DEFAULT_JUDGED,
    LEGACY_FULL_RUN_HYBRID_SCORE,
    bootstrap_paired,
    load_pairs,
    mean_of_runs,
    percentile,
)


def test_percentile_endpoints_and_midpoint():
    assert percentile([0.0, 10.0], 0.0) == 0.0
    assert percentile([0.0, 10.0], 1.0) == 10.0
    assert percentile([0.0, 10.0], 0.5) == 5.0
    assert percentile([0.0, 1.0, 2.0, 3.0], 0.0) == 0.0


def test_constant_gap_interval_collapses():
    pairs = [(1.0, 0.9), (0.5, 0.4), (0.0, -0.1)]
    result = bootstrap_paired(pairs, n_resamples=200, seed=1)
    assert result["gap_mean"] == pytest.approx(0.1)
    assert result["gap_low"] == pytest.approx(0.1)
    assert result["gap_high"] == pytest.approx(0.1)


def test_point_estimate_is_the_original_mean():
    pairs = [(1.0, 0.0), (0.0, 0.0)]
    result = bootstrap_paired(pairs, n_resamples=50, seed=2)
    assert result["hybrid_mean"] == pytest.approx(0.5)
    assert result["vector_mean"] == pytest.approx(0.0)
    assert result["gap_mean"] == pytest.approx(0.5)
    assert result["gap_low"] >= 0.0
    assert result["gap_high"] <= 1.0


def test_same_seed_is_stable():
    pairs = [(1.0, 0.2), (0.5, 0.5), (0.0, 1.0), (1.0, 1.0)]
    first = bootstrap_paired(pairs, n_resamples=100, seed=7)
    second = bootstrap_paired(pairs, n_resamples=100, seed=7)
    assert first == second


def test_legacy_judged_file_uses_full_run_jpm_score():
    assert LEGACY_FULL_RUN_HYBRID_SCORE["hop2_jpm_credit_vs_market"] == 0.375
    slices = load_pairs(DEFAULT_JUDGED)
    hop2 = slices["hop_2"]
    assert len(hop2) == 8
    assert 0.375 in [pair[0] for pair in hop2]
    assert abs(sum(pair[0] for pair in hop2) / 8 - 0.8803) < 0.001


def test_p6_file_keeps_written_jpm_score(tmp_path):
    """New comparison files must not inherit the legacy 0.375 override."""
    from pathlib import Path
    import json
    import shutil

    src = Path("benchmarks/results/multi_company_smoke_temp0_p6.json")
    if not src.exists():
        pytest.skip("p6 result missing")
    dest = tmp_path / "multi_company_smoke_temp0_p6.json"
    shutil.copy(src, dest)
    slices = load_pairs(dest)
    hop2 = {  # rebuild id→hybrid from file to assert JPM
        row["item_id"]: float(row["score"])
        for row in json.loads(src.read_text(encoding="utf-8"))["hybrid"]["results"]
        if int(row["hop"]) == 2 and not row["must_refuse"]
    }
    pairs_by_order = slices["hop_2"]
    assert len(pairs_by_order) == 8
    assert hop2["hop2_jpm_credit_vs_market"] == pytest.approx(1.0)
    assert 0.375 not in [pair[0] for pair in pairs_by_order]


def test_mean_of_runs_averages_per_run_means(tmp_path):
    import json

    def _fake(path, hybrid, vector, hop2_h, hop2_v):
        payload = {
            "hybrid": {
                "mean_score": hybrid,
                "accuracy_by_hop": {
                    "hop_0": 1.0,
                    "hop_1": 1.0,
                    "hop_2": hop2_h,
                    "oos": 1.0,
                },
                "results": [],
            },
            "vector_only": {
                "mean_score": vector,
                "accuracy_by_hop": {
                    "hop_0": 1.0,
                    "hop_1": 1.0,
                    "hop_2": hop2_v,
                    "oos": 1.0,
                },
                "results": [],
            },
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _fake(a, 0.90, 0.80, 1.0, 0.5)
    _fake(b, 0.80, 0.90, 1.0, 1.0)
    summary = mean_of_runs([a, b])
    assert summary["hybrid_mean"] == pytest.approx(0.85)
    assert summary["vector_mean"] == pytest.approx(0.85)
    assert summary["gap_mean"] == pytest.approx(0.0)
    assert summary["by_hop"]["hop_2"]["hybrid_mean"] == pytest.approx(1.0)
    assert summary["by_hop"]["hop_2"]["vector_mean"] == pytest.approx(0.75)


def test_pooled_pairs_average_item_scores(tmp_path):
    import json
    from bootstrap_ci import load_pooled_pairs

    def _run(path, hybrid_score, vector_score):
        row_h = {
            "item_id": "hop2_x",
            "score": hybrid_score,
            "hop": 2,
            "must_refuse": False,
        }
        row_v = {
            "item_id": "hop2_x",
            "score": vector_score,
            "hop": 2,
            "must_refuse": False,
        }
        path.write_text(
            json.dumps(
                {
                    "hybrid": {"results": [row_h], "mean_score": hybrid_score},
                    "vector_only": {"results": [row_v], "mean_score": vector_score},
                }
            ),
            encoding="utf-8",
        )

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _run(a, 1.0, 0.5)
    _run(b, 0.5, 1.0)
    slices = load_pooled_pairs([a, b])
    assert slices["overall"] == [(0.75, 0.75)]
    assert slices["hop_2"] == [(0.75, 0.75)]


def test_empty_and_bad_level():
    with pytest.raises(ValueError):
        bootstrap_paired([])
    with pytest.raises(ValueError):
        bootstrap_paired([(1.0, 0.0)], level=0.0)
