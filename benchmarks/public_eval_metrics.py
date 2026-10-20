"""Source-level retrieval metrics for normalized public evaluation cases.

These metrics measure evidence placement, not final-answer correctness.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


K_VALUES = (1, 3, 5, 10, 100)


def score_retrieval(case: dict[str, Any], ranked_memory_ids: Iterable[str]) -> dict[str, float]:
    """Score one case using the first occurrence of each ranked memory ID.

    Unknown IDs are rejected so an adapter cannot silently count evidence from
    a different case. Duplicates are ignored because repeated snippets do not
    add new source coverage.
    """

    known = {memory["memory_id"] for memory in case["memories"]}
    required = set(case["evidence_memory_ids"])
    ranked: list[str] = []
    seen: set[str] = set()
    for memory_id in ranked_memory_ids:
        if memory_id not in known:
            raise ValueError(f"unknown ranked memory ID: {memory_id}")
        if memory_id not in seen:
            seen.add(memory_id)
            ranked.append(memory_id)

    metrics: dict[str, float] = {}
    for k in K_VALUES:
        found = required.intersection(ranked[:k])
        metrics[f"hit_at_{k}"] = float(bool(found))
        metrics[f"recall_at_{k}"] = len(found) / len(required)
        metrics[f"complete_at_{k}"] = float(found == required)
    first_rank = next((index for index, memory_id in enumerate(ranked, 1) if memory_id in required), None)
    metrics["mrr"] = 1.0 / first_rank if first_rank else 0.0
    return metrics


def aggregate_retrieval(results: Iterable[dict[str, float]]) -> dict[str, float]:
    """Macro-average per-case metrics, preserving each case's evidence weight."""

    rows = list(results)
    if not rows:
        raise ValueError("at least one scored case is required")
    keys = set(rows[0])
    if any(set(row) != keys for row in rows[1:]):
        raise ValueError("scored cases must contain the same metrics")
    return {key: sum(row[key] for row in rows) / len(rows) for key in sorted(keys)}
