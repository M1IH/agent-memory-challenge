"""Paired comparison of two PersonaMem local answerer reports."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from benchmarks.public_eval_schema import load_suite
from benchmarks.score_public_answers import extract_leading_choice_label, score_answer


def compare(base: dict, candidate: dict, suite: dict) -> dict:
    for key in ("suite_sha256", "model_digest", "system_prompt_sha256", "options", "top_k", "selection"):
        if base[key] != candidate[key]:
            raise ValueError(f"incompatible reports: {key}")
    if base.get("split", "development") != candidate.get("split", "development"):
        raise ValueError("incompatible reports: split")
    if base["suite_sha256"] != suite["file_sha256"]:
        raise ValueError("suite hash differs from reports")
    base_rows = {row["case_id"]: row for row in base["rows"]}
    candidate_rows = {row["case_id"]: row for row in candidate["rows"]}
    if base_rows.keys() != candidate_rows.keys() or len(base_rows) != len(base["rows"]) or len(candidate_rows) != len(candidate["rows"]):
        raise ValueError("reports must have identical unique case IDs")
    cases = {case["case_id"]: case for case in suite["cases"]}
    if not base_rows.keys() <= cases.keys():
        raise ValueError("report contains unknown cases")
    paired = Counter()
    grouped: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    parsed = Counter()
    no_memory_changed = 0
    for case_id, baseline in base_rows.items():
        current = candidate_rows[case_id]
        pair = (baseline["with_memory_correct"], current["with_memory_correct"])
        paired[pair] += 1
        grouped[baseline["capability"]].append(pair)
        no_memory_changed += baseline["no_memory_answer"] != current["no_memory_answer"]
        case = cases[case_id]
        for label, row in (("baseline", baseline), ("candidate", current)):
            answer = extract_leading_choice_label(row["with_memory_answer"])
            parsed[label] += bool(answer and score_answer(case, answer))
    return {
        "case_count": len(base_rows),
        "baseline_correct": sum(row["with_memory_correct"] for row in base_rows.values()),
        "candidate_correct": sum(row["with_memory_correct"] for row in candidate_rows.values()),
        "baseline_parsed_correct": parsed["baseline"],
        "candidate_parsed_correct": parsed["candidate"],
        "improved": paired[(False, True)],
        "regressed": paired[(True, False)],
        "both_correct": paired[(True, True)],
        "both_wrong": paired[(False, False)],
        "no_memory_answers_changed": no_memory_changed,
        "by_capability": {
            name: {
                "case_count": len(values),
                "baseline_correct": sum(first for first, _ in values),
                "candidate_correct": sum(second for _, second in values),
                "improved": sum(not first and second for first, second in values),
                "regressed": sum(first and not second for first, second in values),
            }
            for name, values in sorted(grouped.items())
        },
        "note": "Paired public development comparison under one local model; not official AML score.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=Path("data/personamem-v1-32k-normalized.json"))
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(
        json.loads(args.baseline.read_text(encoding="utf-8")),
        json.loads(args.candidate.read_text(encoding="utf-8")),
        load_suite(args.suite),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("case_count", "baseline_correct", "candidate_correct", "improved", "regressed")}))


if __name__ == "__main__":
    main()
