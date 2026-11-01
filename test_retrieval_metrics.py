"""Pure tests for recall@k and MRR. No database or API."""

from __future__ import annotations

import pytest

from retrieval_metrics import mean, recall_at_k, reciprocal_rank, unique_in_order


def test_unique_in_order_keeps_first_occurrence():
    assert unique_in_order(["a", "", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_recall_at_k_partial_and_perfect():
    gold = ["g1", "g2"]
    retrieved = ["miss", "g1", "g2", "other"]
    assert recall_at_k(retrieved, gold, 1) == 0.0
    assert recall_at_k(retrieved, gold, 2) == 0.5
    assert recall_at_k(retrieved, gold, 5) == 1.0


def test_recall_ignores_duplicate_ranks():
    # Second copy of "miss" must not push the gold id out of the top 2.
    assert recall_at_k(["miss", "miss", "gold"], ["gold"], 2) == 1.0


def test_reciprocal_rank_first_hit():
    assert reciprocal_rank(["gold", "other"], ["gold", "later"]) == 1.0
    assert reciprocal_rank(["miss", "gold"], ["gold"]) == 0.5
    assert reciprocal_rank(["miss", "other"], ["gold"]) == 0.0


def test_empty_gold_is_not_a_score():
    with pytest.raises(ValueError):
        recall_at_k(["a"], [], 5)
    with pytest.raises(ValueError):
        reciprocal_rank(["a"], [])


def test_mean_empty():
    assert mean([]) is None
    assert mean([0.0, 1.0]) == 0.5
