from __future__ import annotations

import argparse
import json
from pathlib import Path


WORKLOAD_KEYS = (
    "add_requests",
    "messages_per_request",
    "search_requests",
    "add_workers",
    "search_workers",
    "users",
    "mixed_add_requests",
    "mixed_search_requests",
    "soak_seconds",
    "soak_add_workers",
    "soak_search_workers",
    "top_k",
    "embeddings_enabled",
    "embedding_concurrency",
    "embedding_batch_size",
    "memory_cache_users",
    "memory_cache_max_bytes",
)


def workload_mismatches(
    baseline: dict, candidate: dict
) -> dict[str, tuple[object, object]]:
    baseline_config = baseline.get("config", {})
    candidate_config = candidate.get("config", {})
    return {
        key: (baseline_config.get(key), candidate_config.get(key))
        for key in WORKLOAD_KEYS
        if baseline_config.get(key) != candidate_config.get(key)
    }


def comparison(baseline: dict, candidate: dict) -> dict:
    mismatches = workload_mismatches(baseline, candidate)
    if mismatches:
        details = ", ".join(
            f"{key}={before!r}->{after!r}"
            for key, (before, after) in mismatches.items()
        )
        raise ValueError(f"load reports are not comparable: {details}")

    def delta(section: str, field: str) -> float:
        return candidate[section][field] - baseline[section][field]

    return {
        "comparable": True,
        "peak_rss_delta_bytes": delta("memory", "peak_rss_bytes"),
        "add_p95_delta_seconds": delta("add", "p95_seconds"),
        "search_p95_delta_seconds": delta("search", "p95_seconds"),
        "search_top_1_delta": delta("search", "top_1_correct"),
        "candidate_passed": bool(
            candidate["memory"]["rss_limit_passed"]
            and candidate["add"]["p95_limit_passed"]
            and candidate["search"]["p95_limit_passed"]
            and not candidate["add"]["errors"]
            and not candidate["search"]["errors"]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare load reports only when their workloads match."
    )
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    try:
        result = comparison(baseline, candidate)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
