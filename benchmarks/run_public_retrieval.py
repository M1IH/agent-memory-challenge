"""Run source-level public retrieval on development cases only by default."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from app.store import MemoryStore
from benchmarks.public_eval_metrics import aggregate_retrieval, score_retrieval
from benchmarks.public_eval_schema import load_suite


def run_case(store: MemoryStore, case: dict, *, top_k: int) -> tuple[dict[str, float], list[str]]:
    user_id = f"public-eval:{case['case_id']}"
    for index, memory in enumerate(case["memories"]):
        messages = [
            {"role": turn["role"], "content": turn["content"], "timestamp": memory["timestamp"]}
            for turn in memory["turns"]
        ]
        store.add(
            request_id=f"{case['case_id']}:{index}",
            user_id=user_id,
            session_id=memory["memory_id"],
            messages=messages,
        )
    with store._connection() as connection:
        rows = connection.execute(
            "SELECT id, session_id FROM memories WHERE user_id = ?", (user_id,)
        ).fetchall()
    source_by_id = {row["id"]: row["session_id"] for row in rows}
    results = store.search(user_id=user_id, query=case["question"], options=None, top_k=top_k)
    ranked_sources = [source_by_id[result["id"]] for result in results]
    return score_retrieval(case, ranked_sources), ranked_sources


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=Path("data/longmemeval-s-normalized.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=5, help="first N development cases in source order")
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--embeddings", action="store_true", help="load pinned local BGE model")
    args = parser.parse_args()
    if args.limit < 1 or args.top_k < 1:
        parser.error("limit and top-k must be positive")
    suite = load_suite(args.suite)
    cases = [case for case in suite["cases"] if case["split"] == "development"][: args.limit]
    if not cases:
        raise ValueError("suite has no development cases")
    rows = []
    with tempfile.TemporaryDirectory() as temp_dir:
        store = MemoryStore(Path(temp_dir) / "public-eval.db", embedder=None if args.embeddings else False)
        for case in cases:
            metrics, ranked_sources = run_case(store, case, top_k=args.top_k)
            rows.append({
                "case_id": case["case_id"],
                "capabilities": case["capabilities"],
                "metrics": metrics,
                "ranked_source_ids": list(dict.fromkeys(ranked_sources)),
            })
    report = {
        "kind": "public_retrieval_development",
        "source_sha256": suite["source_sha256"],
        "suite_file_sha256": suite["file_sha256"],
        "code_git_sha": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "code_file_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                Path("app/store.py"),
                Path("app/embedding.py"),
                Path("benchmarks/adapt_longmemeval.py"),
                Path("benchmarks/public_eval_metrics.py"),
                Path("benchmarks/run_public_retrieval.py"),
            )
        },
        "top_k": args.top_k,
        "embeddings": args.embeddings,
        "case_count": len(rows),
        "aggregate": aggregate_retrieval(row["metrics"] for row in rows),
        "cases": rows,
        "note": "Source-level retrieval proxy; no final-answer scoring or official AML result.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"case_count": len(rows), "aggregate": report["aggregate"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
