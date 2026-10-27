"""Offline cross-encoder rerank of fixed public BEAM Top-300 candidates."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path


SOURCE_SHA256 = "c0519be25907005ba873c927c50877471d550873039d96c041554d0075a78ace"
MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/beam-100k.parquet"))
    parser.add_argument("--ranking", type=Path, default=Path("data/beam-100k-dev-14-top300.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path("data/.reranker-cache"))
    parser.add_argument("--development-conversations", type=int, default=2)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-cases", type=int, default=None)
    args = parser.parse_args()
    if (not 1 <= args.development_conversations <= 2 or args.threads < 1
            or args.batch_size < 1 or (args.max_cases is not None and args.max_cases < 1)):
        parser.error("this fixed screen supports 1..2 development conversations; other values must be positive")
    if sha256(args.source) != SOURCE_SHA256:
        raise ValueError("BEAM source hash mismatch")

    import pyarrow.parquet as parquet
    from fastembed.rerank.cross_encoder.text_cross_encoder import TextCrossEncoder

    ranking = json.loads(args.ranking.read_text(encoding="utf-8"))
    if ranking["source_sha256"] != SOURCE_SHA256 or not ranking["ranking_diagnostics"]:
        raise ValueError("ranking does not bind expected source and diagnostics")
    conversations = {}
    for item in parquet.read_table(args.source).to_pylist():
        conversation_id = str(item["conversation_id"])
        conversations[conversation_id] = {
            "messages": {message["id"]: message for batch in item["chat"] for message in batch},
            "questions": ast.literal_eval(item["probing_questions"]),
        }
    model = TextCrossEncoder(model_name=MODEL, cache_dir=str(args.cache), threads=args.threads)
    rows = []
    for row in ranking["rows"]:
        if int(row["conversation_id"]) > args.development_conversations:
            continue
        if args.max_cases is not None and len(rows) >= args.max_cases:
            break
        conversation = conversations[row["conversation_id"]]
        question = conversation["questions"][row["category"]][row["question_index"]]["question"]
        ids = row["ranked_message_ids"]
        documents = [
            f"{conversation['messages'][message_id]['role']}: {conversation['messages'][message_id]['content']}"
            for message_id in ids
        ]
        if [len(document) for document in documents] != row["ranked_result_chars"]:
            raise ValueError(f"Search content reconstruction failed: {row['conversation_id']}")
        started = time.perf_counter()
        scores = list(model.rerank(question, documents, batch_size=args.batch_size))
        elapsed = time.perf_counter() - started
        if len(scores) != len(ids):
            raise ValueError("cross-encoder returned wrong score count")
        selected = sorted(range(len(ids)), key=lambda index: (-scores[index], index))[:100]
        candidate_ids = [ids[index] for index in selected]
        required = {int(source_id) for source_id in row["required_ranks"]}
        base_ids = ids[:100]
        rows.append({
            "conversation_id": row["conversation_id"],
            "category": row["category"],
            "question_index": row["question_index"],
            "candidate_count": len(ids),
            "seconds": elapsed,
            "baseline_complete_top100": required <= set(base_ids),
            "candidate_complete_top100": required <= set(candidate_ids),
            "baseline_required_found": len(required & set(base_ids)),
            "candidate_required_found": len(required & set(candidate_ids)),
            "required_count": len(required),
            "candidate_message_ids": candidate_ids,
        })
    groups = defaultdict(list)
    for row in rows:
        groups[row["category"]].append(row)
    aggregate = {
        category: {
            "cases": len(items),
            "baseline_complete_top100": sum(item["baseline_complete_top100"] for item in items),
            "candidate_complete_top100": sum(item["candidate_complete_top100"] for item in items),
            "improved": sum(not item["baseline_complete_top100"] and item["candidate_complete_top100"] for item in items),
            "regressed": sum(item["baseline_complete_top100"] and not item["candidate_complete_top100"] for item in items),
            "seconds_total": sum(item["seconds"] for item in items),
        }
        for category, items in groups.items()
    }
    report = {
        "kind": "beam_cross_reranker_development_proxy",
        "source_sha256": SOURCE_SHA256,
        "ranking_sha256": sha256(args.ranking),
        "model": MODEL,
        "threads": args.threads,
        "batch_size": args.batch_size,
        "development_conversations": args.development_conversations,
        "aggregate": aggregate,
        "rows": rows,
        "note": "Source-message proxy; no final answer scoring or production capacity evidence.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(aggregate, ensure_ascii=False))


if __name__ == "__main__":
    main()
