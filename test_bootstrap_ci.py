"""Pure tests for the paired bootstrap. No judged file required."""

from __future__ import annotations

import pytest

from bootstrap_ci import bootstrap_paired, percentile


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


def test_empty_and_bad_level():
    with pytest.raises(ValueError):
        bootstrap_paired([])
    with pytest.raises(ValueError):
        bootstrap_paired([(1.0, 0.0)], level=0.0)
