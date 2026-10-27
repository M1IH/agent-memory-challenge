"""Measure token volume of fixed BEAM Search rankings, without answer text."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path


SOURCE_SHA256 = "c0519be25907005ba873c927c50877471d550873039d96c041554d0075a78ace"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/beam-100k.parquet"))
    parser.add_argument("--ranking", type=Path, default=Path("data/beam-100k-dev-14-top300.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget", type=int, default=117760)
    args = parser.parse_args()
    if args.budget < 1:
        parser.error("budget must be positive")
    if sha256(args.source) != SOURCE_SHA256:
        raise ValueError("BEAM source hash mismatch")

    import pyarrow.parquet as parquet
    import tiktoken

    ranking = json.loads(args.ranking.read_text(encoding="utf-8"))
    if ranking["source_sha256"] != SOURCE_SHA256 or not ranking["ranking_diagnostics"]:
        raise ValueError("ranking does not bind the expected source and diagnostics")
    conversations = {
        str(item["conversation_id"]): {
            message["id"]: message
            for batch in item["chat"] for message in batch
        }
        for item in parquet.read_table(args.source).to_pylist()
    }
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    rows = []
    for row in ranking["rows"]:
        messages = conversations[row["conversation_id"]]
        ids = row["ranked_message_ids"][:100]
        contents = [
            f"{messages[message_id]['role']}: {messages[message_id]['content']}"
            for message_id in ids
        ]
        expected_lengths = row["ranked_result_chars"][:100]
        if [len(content) for content in contents] != expected_lengths:
            raise ValueError(f"Search content reconstruction failed: {row['conversation_id']}")
        token_counts = {0: 0}
        def count_prefix(rank: int) -> int:
            if rank not in token_counts:
                token_counts[rank] = len(encoding.encode("\n\n".join(contents[:rank])))
            return token_counts[rank]

        top100_tokens = count_prefix(len(contents))
        top5_tokens = count_prefix(min(5, len(contents)))
        if top100_tokens <= args.budget:
            fitting_count = len(contents)
        else:
            low, high = 0, len(contents)
            while low + 1 < high:
                middle = (low + high) // 2
                if count_prefix(middle) <= args.budget:
                    low = middle
                else:
                    high = middle
            fitting_count = low
        required_ranks = [rank for rank in row["required_ranks"].values() if rank is not None]
        rows.append({
            "conversation_id": row["conversation_id"],
            "category": row["category"],
            "question_index": row["question_index"],
            "result_count": len(contents),
            "content_tokens_top100": top100_tokens,
            "content_tokens_top5": top5_tokens,
            "results_fitting_content_budget": fitting_count,
            "required_count": row["required_count"],
            "required_ranks": row["required_ranks"],
            "all_required_in_top100": len(required_ranks) == row["required_count"]
                and max(required_ranks, default=0) <= 100,
            "all_required_within_content_budget": len(required_ranks) == row["required_count"]
                and max(required_ranks, default=0) <= fitting_count,
        })
    groups = defaultdict(list)
    for row in rows:
        groups[row["category"]].append(row)
    aggregate = {}
    for category, items in groups.items():
        counts = sorted(item["content_tokens_top100"] for item in items)
        aggregate[category] = {
            "cases": len(items),
            "median_content_tokens_top100": statistics.median(counts),
            "max_content_tokens_top100": counts[-1],
            "over_content_budget": sum(count > args.budget for count in counts),
            "all_required_in_top100": sum(item["all_required_in_top100"] for item in items),
            "all_required_within_content_budget": sum(item["all_required_within_content_budget"] for item in items),
        }
    report = {
        "kind": "beam_content_token_window_diagnostic",
        "source_sha256": SOURCE_SHA256,
        "ranking_sha256": sha256(args.ranking),
        "tokenizer": "gpt-4o-mini / " + encoding.name,
        "tiktoken_version": tiktoken.__version__,
        "content_budget_tokens": args.budget,
        "note": "Content only; official Answer formatting and truncation are unknown. Source ranks are a proxy, not answer scores.",
        "aggregate": aggregate,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(aggregate, ensure_ascii=False))


if __name__ == "__main__":
    main()
