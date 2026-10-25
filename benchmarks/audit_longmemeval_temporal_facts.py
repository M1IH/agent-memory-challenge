"""Record retrieved fragments from required sources for public temporal cases.

This is a local diagnostic. Reference answers are never used for ranking.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from app.store import MemoryStore
from benchmarks.public_eval_schema import load_suite
from benchmarks.run_longmemeval_local_answerer import select_cases


def audit_case(store: MemoryStore, case: dict) -> dict:
    user_id = f"temporal-facts:{case['case_id']}"
    for index, memory in enumerate(case["memories"]):
        store.add(
            request_id=f"{case['case_id']}:{index}", user_id=user_id,
            session_id=memory["memory_id"],
            messages=[
                {"role": turn["role"], "content": turn["content"], "timestamp": memory["timestamp"]}
                for turn in memory["turns"]
            ],
        )
    with store._connection() as connection:
        source_by_id = {
            row["id"]: row["session_id"]
            for row in connection.execute("SELECT id, session_id FROM memories WHERE user_id = ?", (user_id,))
        }
    results = store.search(user_id=user_id, query=case["question"], options=None, top_k=100)
    required = set(case["evidence_memory_ids"])
    return {
        "case_id": case["case_id"],
        "question": case["question"],
        "query_time": case.get("query_time"),
        "source_question_date_text": case.get("source_question_date_text"),
        "reference_answers": case["reference_answers"],
        "required_sources": [
            {"source_id": memory["memory_id"], "turns": memory["turns"]}
            for memory in case["memories"] if memory["memory_id"] in required
        ],
        "retrieved_from_required": [
            {"rank": rank, "source_id": source_by_id[result["id"]], "content": result["content"]}
            for rank, result in enumerate(results, 1) if source_by_id[result["id"]] in required
        ],
        "returned_count": len(results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=Path("data/longmemeval-s-normalized.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-capability", type=int, default=5)
    args = parser.parse_args()
    suite = load_suite(args.suite)
    cases = select_cases(suite, args.per_capability, "temporal-reasoning")
    with tempfile.TemporaryDirectory() as directory:
        store = MemoryStore(Path(directory) / "facts.db", embedder=False)
        rows = [audit_case(store, case) for case in cases]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cases": len(rows), "output": str(args.output)}))


if __name__ == "__main__":
    main()
