"""Pure tests for snap, weighted κ, and Spearman. No API."""

from __future__ import annotations

import pytest

from calibration_metrics import raw_agreement, snap_score, spearman, weighted_kappa


def test_snap_maps_fractions_onto_three_bins():
    assert snap_score(0.0) == 0.0
    assert snap_score(0.125) == 0.0
    assert snap_score(0.24) == 0.0
    assert snap_score(0.25) == 0.5
    assert snap_score(0.375) == 0.5
    assert snap_score(0.5) == 0.5
    assert snap_score(0.6675) == 0.5
    assert snap_score(0.74) == 0.5
    assert snap_score(0.75) == 1.0
    assert snap_score(1.0) == 1.0


def test_snap_rejects_out_of_range():
    with pytest.raises(ValueError):
        snap_score(1.1)


def test_perfect_mixed_labels_have_kappa_one():
    labels = [0.0, 0.5, 1.0, 1.0]
    assert weighted_kappa(labels, labels) == 1.0
    assert raw_agreement(labels, labels) == 1.0
    assert spearman(labels, labels) == pytest.approx(1.0)


def test_linear_kappa_hand_example():
    # One one-step miss. See calibration_metrics docstring for the weight.
    # num = 0.5, den = 2.0 → κ = 0.75
    left = [0.0, 0.0, 1.0, 1.0]
    right = [0.0, 0.5, 1.0, 1.0]
    assert weighted_kappa(left, right, weights="linear") == pytest.approx(0.75)
    assert raw_agreement(left, right) == 0.75


def test_quadratic_discounts_a_one_step_miss_more_than_linear():
    left = [0.0, 0.0, 1.0, 1.0]
    right = [0.0, 0.5, 1.0, 1.0]
    linear = weighted_kappa(left, right, weights="linear")
    quadratic = weighted_kappa(left, right, weights="quadratic")
    assert linear == pytest.approx(0.75)
    assert quadratic == pytest.approx(1 - 0.25 / 1.75)
    assert quadratic > linear


def test_constant_raters_leave_kappa_undefined():
    assert weighted_kappa([1.0, 1.0, 1.0], [1.0, 1.0, 1.0]) is None
    assert spearman([1.0, 1.0], [0.5, 1.0]) is None


def test_length_mismatch():
    with pytest.raises(ValueError):
        weighted_kappa([1.0], [1.0, 0.0])
