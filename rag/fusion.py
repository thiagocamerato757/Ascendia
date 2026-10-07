"""Reciprocal Rank Fusion (spec D2, §7.2).

Pure function: combines ranked lists of ids into one ranking. Each list
contributes ``weight / (k + rank)`` per id (rank starting at 1), so an item that
is high in either list — or decent in both — rises to the top, without needing
the lists' raw scores to be comparable.
"""
from __future__ import annotations

from collections.abc import Hashable, Sequence


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[Hashable]],
    *,
    k: int = 60,
    weights: Sequence[float] | None = None,
) -> list[tuple[Hashable, float]]:
    """``[(id, score), ...]`` sorted by fused score, best first.

    Ties keep the order in which ids were first seen (earlier lists first), so
    the result is deterministic.
    """
    if k < 0:
        raise ValueError('k must be non-negative')
    weights = list(weights) if weights is not None else [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError('one weight per ranking')
    scores: dict[Hashable, float] = {}
    first_seen: dict[Hashable, int] = {}
    for ranking, weight in zip(rankings, weights):
        seen_here = set()
        for position, item in enumerate(ranking, start=1):
            if item in seen_here:
                continue  # an id counts once per list
            seen_here.add(item)
            scores[item] = scores.get(item, 0.0) + weight / (k + position)
            first_seen.setdefault(item, len(first_seen))
    return sorted(scores.items(), key=lambda kv: (-kv[1], first_seen[kv[0]]))
