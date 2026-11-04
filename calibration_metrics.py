"""
WP3 judge calibration metrics.

Scores live on {0, 0.5, 1}. A raw judge fraction is snapped onto that scale
before κ, so a 0.67 and a human 0.5 can agree as "partial".

Linear weighted Cohen's κ uses disagreement weights |i-j| / (k-1).
A one-step miss (1 vs 0.5) counts half as much as a full miss (1 vs 0).
Quadratic weights square that distance. The reported number is linear.

κ is undefined when the weight of chance disagreement is 0 (both raters
used only one category). That is a result, not a perfect score.
"""

from __future__ import annotations

from typing import Optional, Sequence

ORDINAL = (0.0, 0.5, 1.0)


def snap_score(score: float) -> float:
    """Nearest of 0, 0.5, 1. Exact midpoints 0.25 and 0.75 snap upward."""
    value = float(score)
    if value < 0.0 or value > 1.0:
        raise ValueError(f"score must be in [0, 1], got {score}")
    if value < 0.25:
        return 0.0
    if value < 0.75:
        return 0.5
    return 1.0


def raw_agreement(left: Sequence[float], right: Sequence[float]) -> float:
    """Fraction of items whose snapped scores match."""
    pairs = _pairs(left, right)
    matches = sum(1 for a, b in pairs if a == b)
    return matches / len(pairs)


def weighted_kappa(
    left: Sequence[float],
    right: Sequence[float],
    *,
    weights: str = "linear",
) -> Optional[float]:
    """
    Weighted Cohen's κ on the snapped 3-point scale.

    Returns None when expected disagreement weight is 0.
    """
    pairs = _pairs(left, right)
    index = {category: i for i, category in enumerate(ORDINAL)}
    k = len(ORDINAL)
    observed = [[0.0 for _ in range(k)] for _ in range(k)]
    for a, b in pairs:
        observed[index[a]][index[b]] += 1.0

    n = float(len(pairs))
    row = [sum(observed[i]) for i in range(k)]
    col = [sum(observed[i][j] for i in range(k)) for j in range(k)]

    numerator = 0.0
    denominator = 0.0
    for i in range(k):
        for j in range(k):
            weight = _disagreement_weight(i, j, k, weights)
            expected = row[i] * col[j] / n
            numerator += weight * observed[i][j]
            denominator += weight * expected
    if denominator == 0.0:
        return None
    return 1.0 - numerator / denominator


def spearman(left: Sequence[float], right: Sequence[float]) -> Optional[float]:
    """Spearman rank correlation on snapped scores. None if either side is constant."""
    pairs = _pairs(left, right)
    return _pearson(_average_ranks([a for a, _ in pairs]), _average_ranks([b for _, b in pairs]))


def _pairs(left: Sequence[float], right: Sequence[float]) -> list[tuple[float, float]]:
    if len(left) != len(right):
        raise ValueError("raters must score the same items")
    if not left:
        raise ValueError("need at least one scored item")
    return [(snap_score(a), snap_score(b)) for a, b in zip(left, right)]


def _disagreement_weight(i: int, j: int, k: int, weights: str) -> float:
    distance = abs(i - j) / (k - 1)
    if weights == "linear":
        return distance
    if weights == "quadratic":
        return distance * distance
    raise ValueError(f"unknown weight scheme: {weights}")


def _average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(values):
        end = start
        while end + 1 < len(values) and values[order[end + 1]] == values[order[start]]:
            end += 1
        average = (start + 1 + end + 1) / 2.0
        for position in range(start, end + 1):
            ranks[order[position]] = average
        start = end + 1
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> Optional[float]:
    n = len(left)
    mean_left = sum(left) / n
    mean_right = sum(right) / n
    numerator = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
    left_scale = sum((a - mean_left) ** 2 for a in left) ** 0.5
    right_scale = sum((b - mean_right) ** 2 for b in right) ** 0.5
    if left_scale == 0.0 or right_scale == 0.0:
        return None
    return numerator / (left_scale * right_scale)
