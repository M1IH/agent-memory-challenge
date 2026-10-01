"""Offline ordering diagnostics for frozen synthetic source-scored reports."""

import hashlib
import json
from pathlib import Path


def ordering_diagnostic(cases: list[dict], report: dict) -> dict:
    suite_hash = hashlib.sha256(
        json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    if report["suite_sha256"] != suite_hash:
        raise ValueError("report does not match the frozen suite")
    traces = {trace["name"]: trace for trace in report["case_traces"]}
    if len(traces) != len(cases) or set(traces) != {case["name"] for case in cases}:
        raise ValueError("report must contain exactly one trace per case")
    counts = {"preferred_first": 0, "reversed": 0, "missing": 0}
    pairs = []
    for case in cases:
        ranks = {
            row["source_id"]: rank
            for rank, row in enumerate(traces[case["name"]]["results"], 1)
        }
        for preferred, other in case.get("preferred_source_pairs", []):
            left, right = ranks.get(preferred), ranks.get(other)
            outcome = (
                "missing" if left is None or right is None
                else "preferred_first" if left < right else "reversed"
            )
            counts[outcome] += 1
            pairs.append({"case": case["name"], "preferred": preferred, "other": other,
                          "ranks": [left, right], "outcome": outcome})
    return {
        "scope": "Synthetic ordering diagnostic; not downstream answer accuracy",
        "suite_sha256": suite_hash,
        "analyzer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "counts": counts, "pairs": pairs,
    }
