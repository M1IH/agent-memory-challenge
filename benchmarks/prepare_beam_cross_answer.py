"""Prepare paired BEAM evidence for the fixed local answerer after reranking."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path


SOURCE_SHA256 = "c0519be25907005ba873c927c50877471d550873039d96c041554d0075a78ace"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/beam-100k.parquet"))
    parser.add_argument("--ranking", type=Path, default=Path("data/beam-100k-dev-14-top300.json"))
    parser.add_argument("--reranked", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sha256(args.source) != SOURCE_SHA256:
        raise ValueError("BEAM source hash mismatch")

    import pyarrow.parquet as parquet

    ranking = json.loads(args.ranking.read_text(encoding="utf-8"))
    reranked = json.loads(args.reranked.read_text(encoding="utf-8"))
    if (reranked["source_sha256"] != SOURCE_SHA256
            or reranked["ranking_sha256"] != sha256(args.ranking)):
        raise ValueError("reranked report identity mismatch")
    conversations = {}
    for item in parquet.read_table(args.source).to_pylist():
        conversations[str(item["conversation_id"])] = {
            "messages": {message["id"]: message for batch in item["chat"] for message in batch},
            "questions": ast.literal_eval(item["probing_questions"]),
        }
    baseline_by_key = {
        (row["conversation_id"], row["category"], row["question_index"]): row
        for row in ranking["rows"]
    }
    rows = []
    for candidate in reranked["rows"]:
        key = (candidate["conversation_id"], candidate["category"], candidate["question_index"])
        baseline = baseline_by_key[key]
        conversation = conversations[candidate["conversation_id"]]
        messages = conversation["messages"]
        question = conversation["questions"][candidate["category"]][candidate["question_index"]]["question"]
        def results(ids: list[int]) -> list[dict]:
            return [
                {
                    "rank": rank,
                    "kind": "source",
                    "source_id": message_id,
                    "source_ids": [message_id],
                    "content": f"{messages[message_id]['role']}: {messages[message_id]['content']}",
                    "chars": len(messages[message_id]["role"]) + 2 + len(messages[message_id]["content"]),
                }
                for rank, message_id in enumerate(ids, start=1)
            ]
        rows.append({
            "conversation_id": candidate["conversation_id"],
            "category": candidate["category"],
            "question_index": candidate["question_index"],
            "question": question,
            "baseline_results": results(baseline["ranked_message_ids"][:100]),
            "candidate_results": results(candidate["candidate_message_ids"]),
        })
    report = {
        "kind": "beam_cross_reranker_answer_evidence",
        "source_sha256": SOURCE_SHA256,
        "ranking_sha256": sha256(args.ranking),
        "reranked_sha256": sha256(args.reranked),
        "rows": rows,
        "note": "Only public chat and question text enter answer evidence; reference answers and rubric remain separate.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cases": len(rows), "output": str(args.output)}))


if __name__ == "__main__":
    main()
