"""Offline session-diversity rerank on public LongMemEval development cases.

This candidate only reorders the same Top-100 Search results. It never uses
reference answers to choose results, and never changes the production store.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from collections import OrderedDict
from pathlib import Path

from app.store import MemoryStore
from benchmarks.analyze_longmemeval_fragments import contains_literal, eligible_literal
from benchmarks.public_eval_schema import load_suite


def session_round_robin(results: list[dict], source_ids: list[str]) -> tuple[list[dict], list[str]]:
    if len(results) != len(source_ids):
        raise ValueError("results and source IDs differ in length")
    groups: OrderedDict[str, list[dict]] = OrderedDict()
    for result, source in zip(results, source_ids, strict=True):
        groups.setdefault(source, []).append(result)
    reranked = []
    reranked_sources = []
    for depth in range(max(map(len, groups.values()), default=0)):
        for source, group in groups.items():
            if depth < len(group):
                reranked.append(group[depth])
                reranked_sources.append(source)
    return reranked, reranked_sources


def complete_rank(required: set[str], sources: list[str]) -> int | None:
    seen: set[str] = set()
    for rank, source in enumerate(sources, 1):
        seen.add(source)
        if required <= seen:
            return rank
    return None


def literal_rank(
    required: set[str], answers: list[str], results: list[dict], sources: list[str],
) -> int | None:
    return next((
        rank for rank, (result, source) in enumerate(zip(results, sources, strict=True), 1)
        if source in required and any(contains_literal(result["content"], answer) for answer in answers)
    ), None)


def run_case(store: MemoryStore, case: dict) -> dict:
    user_id = f"session-rr:{case['case_id']}"
    for index, memory in enumerate(case["memories"]):
        store.add(
            request_id=f"{case['case_id']}:{index}", user_id=user_id,
            session_id=memory["memory_id"],
            messages=[
                {"role": turn["role"], "content": turn["content"], "timestamp": memory["timestamp"]}
                for turn in memory["turns"]
            ],
        )
    results = store.search(user_id=user_id, query=case["question"], options=None, top_k=100)
    with store._connection() as connection:
        source_by_id = {
            row["id"]: row["session_id"]
            for row in connection.execute("SELECT id, session_id FROM memories WHERE user_id = ?", (user_id,))
        }
    sources = [source_by_id[result["id"]] for result in results]
    candidate, candidate_sources = session_round_robin(results, sources)
    required = set(case["evidence_memory_ids"])
    eligible = [answer for answer in case["reference_answers"] if eligible_literal(answer)]
    required_text = "\n".join(
        turn["content"] for memory in case["memories"] if memory["memory_id"] in required
        for turn in memory["turns"]
    )
    return {
        "case_id": case["case_id"],
        "capability": case["capabilities"][0],
        "result_count": len(results),
        "literal_in_required_source": any(contains_literal(required_text, answer) for answer in eligible),
        "baseline_complete_rank": complete_rank(required, sources),
        "candidate_complete_rank": complete_rank(required, candidate_sources),
        "baseline_literal_rank": literal_rank(required, eligible, results, sources),
        "candidate_literal_rank": literal_rank(required, eligible, candidate, candidate_sources),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=Path("data/longmemeval-s-normalized.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=390)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("limit must be positive")
    suite = load_suite(args.suite)
    cases = [case for case in suite["cases"] if case["split"] == "development"][:args.limit]
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        store = MemoryStore(Path(directory) / "session-rr.db", embedder=False)
        for case in cases:
            rows.append(run_case(store, case))
    report = {
        "kind": "offline_session_round_robin_development",
        "suite_sha256": suite["file_sha256"],
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "store_sha256": hashlib.sha256(Path("app/store.py").read_bytes()).hexdigest(),
        "code_git_sha": subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip(),
        "case_count": len(rows),
        "top_k": 100,
        "rows": rows,
        "note": "Offline source and literal placement only; not final answer or official AML score.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "case_count": len(rows),
        "baseline_complete_at_5": sum(r["baseline_complete_rank"] is not None and r["baseline_complete_rank"] <= 5 for r in rows),
        "candidate_complete_at_5": sum(r["candidate_complete_rank"] is not None and r["candidate_complete_rank"] <= 5 for r in rows),
        "baseline_literal_at_5": sum(r["baseline_literal_rank"] is not None and r["baseline_literal_rank"] <= 5 for r in rows),
        "candidate_literal_at_5": sum(r["candidate_literal_rank"] is not None and r["candidate_literal_rank"] <= 5 for r in rows),
    }))


if __name__ == "__main__":
    main()
