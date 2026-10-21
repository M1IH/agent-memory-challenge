"""Score externally generated predictions against public development cases.

Prediction JSONL rows have exactly ``case_id`` and ``answer``. This tool does
not call a model. Frozen holdout scoring requires an explicit opt-in.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from benchmarks.public_eval_schema import load_suite


CHOICE_LABEL = re.compile(r"^\(([a-z])\)$", re.IGNORECASE)
LEADING_CHOICE_LABEL = re.compile(r"^\s*(\([a-d]\))(?=$|[\s.:;,])", re.IGNORECASE)


def extract_leading_choice_label(value: str) -> str | None:
    """Read a model's unambiguous first option label for diagnostic scoring."""
    match = LEADING_CHOICE_LABEL.match(value)
    return match.group(1).lower() if match else None


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def score_answer(case: dict, prediction: str) -> bool:
    if case["scorer"] == "multiple_choice":
        answer = normalize_text(prediction)
        correct = case["reference_answers"]
        if any(answer == normalize_text(choice) for choice in correct):
            return True
        label = CHOICE_LABEL.fullmatch(answer)
        if label:
            return any(choice.casefold().startswith(label.group(0).casefold() + " ") for choice in correct)
        return False
    if case["scorer"] == "exact_match":
        return any(normalize_text(prediction) == normalize_text(answer) for answer in case["reference_answers"])
    raise ValueError(f"unsupported local answer scorer: {case['scorer']}")


def load_predictions(path: Path) -> dict[str, str]:
    predictions = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if set(row) != {"case_id", "answer"} or not all(isinstance(value, str) and value.strip() for value in row.values()):
            raise ValueError(f"invalid prediction on line {number}")
        if row["case_id"] in predictions:
            raise ValueError(f"duplicate prediction for {row['case_id']}")
        predictions[row["case_id"]] = row["answer"]
    return predictions


def score_suite(suite: dict, predictions: dict[str, str], *, split: str = "development") -> dict:
    cases = [case for case in suite["cases"] if case["split"] == split]
    if not cases:
        raise ValueError(f"suite has no cases for split {split}")
    expected = {case["case_id"] for case in cases}
    missing = expected - predictions.keys()
    extra = predictions.keys() - expected
    if missing or extra:
        raise ValueError(f"prediction IDs mismatch: missing={len(missing)} extra={len(extra)}")
    correct = 0
    groups: dict[str, list[bool]] = defaultdict(list)
    for case in cases:
        passed = score_answer(case, predictions[case["case_id"]])
        correct += passed
        for capability in case["capabilities"]:
            groups[capability].append(passed)
    return {
        "split": split,
        "case_count": len(cases),
        "correct": correct,
        "accuracy": correct / len(cases),
        "by_capability": {
            name: {"case_count": len(values), "correct": sum(values), "accuracy": sum(values) / len(values)}
            for name, values in sorted(groups.items())
        },
        "note": "Local public answer metric; not an official AML or dataset score.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "frozen_holdout"), default="development")
    parser.add_argument("--allow-frozen-holdout", action="store_true")
    args = parser.parse_args()
    if args.split == "frozen_holdout" and not args.allow_frozen_holdout:
        parser.error("frozen_holdout requires --allow-frozen-holdout")
    suite = load_suite(args.suite)
    result = score_suite(suite, load_predictions(args.predictions), split=args.split)
    result["suite_sha256"] = suite["file_sha256"]
    result["predictions_sha256"] = hashlib.sha256(args.predictions.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("split", "case_count", "correct", "accuracy")}))


if __name__ == "__main__":
    main()
