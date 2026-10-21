"""Check literal answer evidence in retrieved LongMemEval development snippets.

Literal presence is a narrow diagnostic, not an answer correctness metric.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import unicodedata
from pathlib import Path

from app.store import MemoryStore
from benchmarks.public_eval_schema import load_suite


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def eligible_literal(answer: str) -> bool:
    value = normalize(answer)
    return 4 <= len(value) <= 80 and len(value.split()) <= 10 and any(char.isalpha() for char in value)


def contains_literal(text: str, answer: str) -> bool:
    value = normalize(answer)
    return bool(re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", normalize(text)))


def analyze_case(store: MemoryStore, case: dict, top_k: int) -> dict:
    user_id = f"fragment-probe:{case['case_id']}"
    for index, memory in enumerate(case["memories"]):
        store.add(
            request_id=f"{case['case_id']}:{index}", user_id=user_id,
            session_id=memory["memory_id"],
            messages=[
                {"role": turn["role"], "content": turn["content"], "timestamp": memory["timestamp"]}
                for turn in memory["turns"]
            ],
        )
    results = store.search(user_id=user_id, query=case["question"], options=None, top_k=top_k)
    with store._connection() as connection:
        sources = {
            row["id"]: row["session_id"]
            for row in connection.execute("SELECT id, session_id FROM memories WHERE user_id = ?", (user_id,))
        }
    required = set(case["evidence_memory_ids"])
    source_ids = [sources[result["id"]] for result in results]
    eligible = [answer for answer in case["reference_answers"] if eligible_literal(answer)]
    source_text = "\n".join(
        turn["content"] for memory in case["memories"] if memory["memory_id"] in required
        for turn in memory["turns"]
    )
    returned_text = "\n".join(result["content"] for result in results)
    required_returned_text = "\n".join(
        result["content"] for result, source in zip(results, source_ids, strict=True) if source in required
    )
    return {
        "case_id": case["case_id"],
        "capability": case["capabilities"][0],
        "required_source_complete": required <= set(source_ids),
        "eligible_literal_count": len(eligible),
        "literal_in_required_source": any(contains_literal(source_text, answer) for answer in eligible),
        "literal_in_top_k": any(contains_literal(returned_text, answer) for answer in eligible),
        "literal_in_required_source_snippet": any(
            contains_literal(required_returned_text, answer) for answer in eligible
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=Path("data/longmemeval-s-normalized.json"))
    parser.add_argument("--answer-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    suite = load_suite(args.suite)
    answer_report_bytes = args.answer_report.read_bytes()
    answer_report = json.loads(answer_report_bytes)
    if answer_report["suite_sha256"] != suite["file_sha256"]:
        raise ValueError("answer report and suite hashes differ")
    selected_ids = [row["case_id"] for row in answer_report["rows"]]
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("duplicate case ID in answer report")
    by_id = {case["case_id"]: case for case in suite["cases"] if case["split"] == "development"}
    if not set(selected_ids) <= by_id.keys():
        raise ValueError("answer report contains unknown or non-development cases")
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        store = MemoryStore(Path(directory) / "fragments.db", embedder=False)
        for case_id in selected_ids:
            rows.append(analyze_case(store, by_id[case_id], answer_report["top_k"]))
    for row, answered in zip(rows, answer_report["rows"], strict=True):
        row["with_exact"] = answered["with_exact"]
    report = {
        "kind": "longmemeval_literal_fragment_diagnostic",
        "suite_sha256": suite["file_sha256"],
        "answer_report_sha256": hashlib.sha256(answer_report_bytes).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "top_k": answer_report["top_k"],
        "case_count": len(rows),
        "rows": rows,
        "note": "Short literal reference substring probe only; misses paraphrases and inferred answers.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "case_count": len(rows),
        "eligible": sum(bool(row["eligible_literal_count"]) for row in rows),
        "literal_in_required_source": sum(row["literal_in_required_source"] for row in rows),
        "literal_in_required_source_snippet": sum(row["literal_in_required_source_snippet"] for row in rows),
    }))


if __name__ == "__main__":
    main()
