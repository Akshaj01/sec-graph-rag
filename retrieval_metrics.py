"""
WP2 retrieval metrics.

recall@k: fraction of gold chunk ids that appear in the first k unique
retrieved ids. Each question is weighted equally (macro-average).

MRR: reciprocal rank of the first gold id in that same unique list.
1.0 means the top chunk is gold. 0.0 means no gold id was retrieved.
With several gold ids, only the earliest one sets the rank.

Out-of-scope items have no gold chunks and are not scored.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence


def unique_in_order(chunk_ids: Iterable[str]) -> List[str]:
    """Drop blanks and later duplicates. Rank is first occurrence."""
    seen: set[str] = set()
    ordered: List[str] = []
    for chunk_id in chunk_ids:
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        ordered.append(chunk_id)
    return ordered


def interleave_ids(first: Sequence[str], second: Sequence[str]) -> List[str]:
    """Alternate two id lists, starting with `first`.

    A chunk already placed is skipped, and the next chunk from that same
    side is used. When one side runs out, the rest of the other side follows.
    """
    left = unique_in_order(first)
    right = unique_in_order(second)
    out: List[str] = []
    seen: set[str] = set()
    i = 0
    j = 0
    take_left = True
    while i < len(left) or j < len(right):
        if take_left:
            while i < len(left) and left[i] in seen:
                i += 1
            if i < len(left):
                out.append(left[i])
                seen.add(left[i])
                i += 1
        else:
            while j < len(right) and right[j] in seen:
                j += 1
            if j < len(right):
                out.append(right[j])
                seen.add(right[j])
                j += 1
        take_left = not take_left
        if i >= len(left) and j >= len(right):
            break
    return out


def recall_at_k(retrieved: Sequence[str], gold: Sequence[str], k: int) -> float:
    """|gold ∩ top-k unique retrieved| / |gold|."""
    if k < 1:
        raise ValueError("k must be >= 1")
    gold_set = unique_in_order(gold)
    if not gold_set:
        raise ValueError("recall_at_k requires at least one gold chunk id")
    top = set(unique_in_order(retrieved)[:k])
    hits = sum(1 for chunk_id in gold_set if chunk_id in top)
    return hits / len(gold_set)


def reciprocal_rank(retrieved: Sequence[str], gold: Sequence[str]) -> float:
    """1 / rank of the first gold id, or 0 when none of the gold ids appear."""
    gold_set = set(unique_in_order(gold))
    if not gold_set:
        raise ValueError("reciprocal_rank requires at least one gold chunk id")
    for rank, chunk_id in enumerate(unique_in_order(retrieved), start=1):
        if chunk_id in gold_set:
            return 1.0 / rank
    return 0.0


def mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)
