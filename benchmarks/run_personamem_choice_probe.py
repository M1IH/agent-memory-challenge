"""Small, deterministic PersonaMem lexical choice probe; not a model answerer.

Runs development cases only. Each option is searched against the fourth-version
lexical store, and its strongest evidence score is length-normalized. This is a
diagnostic lower baseline, not a proxy for the official answer model.
"""

from __future__ import annotations

import argparse
import json
import math
import tempfile
from pathlib import Path

from app.store import MemoryStore, tokenize
from benchmarks.public_eval_schema import load_suite
from benchmarks.score_public_answers import score_answer


def choose(store: MemoryStore, user_id: str, choices: list[str]) -> tuple[str, list[dict]]:
    ranked = []
    details = []
    for index, option in enumerate(choices):
        text = option.split(" ", 1)[1] if " " in option else option
        results = store.search(user_id=user_id, query=text, options=None, top_k=3)
        raw_score = max((result["score"] or 0.0 for result in results), default=0.0)
        distinct_terms = max(1, len(set(tokenize(text))))
        score = raw_score / math.sqrt(distinct_terms)
        details.append({
            "label": option.split(" ", 1)[0],
            "score": score,
            "raw_score": raw_score,
            "distinct_terms": distinct_terms,
            "top_result_id": results[0]["id"] if results else None,
        })
        ranked.append((score, -index, option))
    return max(ranked)[2], details


def run_case(store: MemoryStore, case: dict) -> dict:
    user_id = "choice-probe:" + case["case_id"]
    for index, memory in enumerate(case["memories"]):
        store.add(
            request_id=f"{case['case_id']}:{index}",
            user_id=user_id,
            session_id=memory["memory_id"],
            messages=[{"role": turn["role"], "content": turn["content"]} for turn in memory["turns"]],
        )
    prediction, scores = choose(store, user_id, case["choices"])
    return {
        "case_id": case["case_id"],
        "capability": case["capabilities"][0],
        "correct": score_answer(case, prediction),
        "predicted_label": prediction.split(" ", 1)[0],
        "reference_label": case["source_answer_raw"],
        "scores": scores,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=Path("data/personamem-v1-32k-normalized.json"))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("limit must be positive")
    suite = load_suite(args.suite)
    cases = [case for case in suite["cases"] if case["split"] == "development"][: args.limit]
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        store = MemoryStore(Path(directory) / "choice-probe.db", embedder=False)
        for case in cases:
            rows.append(run_case(store, case))
    report = {
        "kind": "personamem_lexical_choice_probe",
        "suite_sha256": suite["file_sha256"],
        "case_count": len(rows),
        "correct": sum(row["correct"] for row in rows),
        "accuracy": sum(row["correct"] for row in rows) / len(rows),
        "rows": rows,
        "note": "Development subset, deterministic lexical heuristic; not official or fixed LLM answer accuracy.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("case_count", "correct", "accuracy")}))


if __name__ == "__main__":
    main()
