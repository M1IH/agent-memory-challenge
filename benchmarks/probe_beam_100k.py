"""Source-message retrieval proxy for the public BEAM 100K subset.

Only chat messages enter Add, and only probing question text enters Search.
Reference answers, source IDs and rubrics are used after retrieval for scoring.
This is neither BEAM's LLM-rubric score nor an AML score.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import tempfile
from collections import defaultdict
from pathlib import Path

from app.store import MemoryStore, RetrievalConfig
import app.store as store_module


SOURCE_REVISION = "3205395e897e7318c7b094ef4e6047b9b82dbb03"
SOURCE_SHA256 = "c0519be25907005ba873c927c50877471d550873039d96c041554d0075a78ace"
TARGET_CATEGORIES = ("summarization", "multi_session_reasoning", "knowledge_update")
_TITLE_TOKEN = re.compile(r"(?<![\w-])[A-Z][a-z]+(?:-[A-Z]?[a-z]+)?")
_ORIGINAL_ENTITY_TERMS = store_module.entity_terms


def noninitial_entity_terms(text: str) -> set[str]:
    """Experimental: remove English sentence/list starters from link entities."""
    candidates = _ORIGINAL_ENTITY_TERMS(text)
    retained = {item for item in candidates if not item.isascii()}
    for match in _TITLE_TOKEN.finditer(text):
        term = match.group().lower()
        if term not in candidates:
            continue
        preceding = text[:match.start()]
        last_boundary = max(preceding.rfind(mark) for mark in ".?!:\n")
        clause_prefix = preceding[last_boundary + 1:].strip(" \t\r-*0123456789.)")
        if clause_prefix:
            retained.add(term)
    return retained


def flatten_source_ids(value: object) -> list[int]:
    if isinstance(value, bool):
        raise ValueError("boolean source ID")
    if isinstance(value, int):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in flatten_source_ids(child)]
    if isinstance(value, (list, tuple)):
        return [item for child in value for item in flatten_source_ids(child)]
    raise ValueError(f"unsupported source ID type: {type(value).__name__}")


def load_rows(path: Path) -> list[dict]:
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("BEAM 100K source hash mismatch")
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise SystemExit("Install pyarrow in the local environment before running") from exc
    return parquet.read_table(path).to_pylist()


def run_conversation(store: MemoryStore, conversation: dict, *, top_k: int) -> list[dict]:
    conversation_id = str(conversation["conversation_id"])
    user_id = f"beam-100k:{conversation_id}"
    chat = conversation["chat"]
    original_ids = set()
    for batch_index, batch in enumerate(chat):
        for message in batch:
            message_id = message["id"]
            if message_id in original_ids:
                raise ValueError(f"duplicate message ID {conversation_id}:{message_id}")
            original_ids.add(message_id)
            content = message["content"]
            # One source message can exceed the production Add payload bound.
            # Split losslessly and map each stored chunk back to the source ID.
            for chunk_index, start in enumerate(range(0, len(content), store.max_add_chars)):
                store.add(
                    request_id=f"chat:{message_id}:{chunk_index}", user_id=user_id,
                    session_id=f"batch:{batch_index + 1}",
                    messages=[{
                        "role": message["role"],
                        "content": content[start:start + store.max_add_chars],
                    }],
                )
    with store._connection() as connection:
        id_by_memory = {
            row["id"]: int(row["request_id"].split(":")[1])
            for row in connection.execute(
                "SELECT id, request_id FROM memories WHERE user_id = ?", (user_id,)
            )
        }
    if set(id_by_memory.values()) != original_ids:
        raise ValueError(f"Add did not preserve every source message in conversation {conversation_id}")

    questions = ast.literal_eval(conversation["probing_questions"])
    rows = []
    for category in TARGET_CATEGORIES:
        for question_index, item in enumerate(questions[category]):
            required = set(flatten_source_ids(item["source_chat_ids"]))
            if not required or not required <= original_ids:
                raise ValueError(f"invalid evidence IDs for {conversation_id}:{category}:{question_index}")
            results = store.search(
                user_id=user_id, query=item["question"], options=None, top_k=top_k,
            )
            ranked = [id_by_memory[result["id"]] for result in results]
            rows.append({
                "conversation_id": conversation_id,
                "category": category,
                "question_index": question_index,
                "required_count": len(required),
                "hit_at_5": bool(required.intersection(ranked[:5])),
                "complete_at_5": required <= set(ranked[:5]),
                "complete_at_100": required <= set(ranked[:100]),
                "required_ranks": {str(i): ranked.index(i) + 1 if i in ranked else None for i in sorted(required)},
                "result_count": len(ranked),
            })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/beam-100k.parquet"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--development-conversations", type=int, default=14)
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--disable-linkage", action="store_true")
    parser.add_argument("--disable-expansion", action="store_true")
    parser.add_argument("--disable-temporal", action="store_true")
    parser.add_argument("--filter-english-entities", action="store_true")
    args = parser.parse_args()
    if args.development_conversations not in range(1, 15) or args.top_k < 1:
        parser.error("development-conversations must be 1..14 and top-k positive")
    source_rows = load_rows(args.source)
    if len(source_rows) != 20:
        raise ValueError("expected exactly 20 BEAM 100K conversations")
    source_rows.sort(key=lambda item: int(item["conversation_id"]))
    rows = []
    if args.filter_english_entities:
        store_module.entity_terms = noninitial_entity_terms
    config = RetrievalConfig(
        linkage_enabled=not args.disable_linkage,
        expansion_enabled=not args.disable_expansion,
        temporal_enabled=not args.disable_temporal,
    )
    with tempfile.TemporaryDirectory() as directory:
        store = MemoryStore(Path(directory) / "beam.db", embedder=False, retrieval_config=config)
        for conversation in source_rows[: args.development_conversations]:
            rows.extend(run_conversation(store, conversation, top_k=args.top_k))
    groups = defaultdict(list)
    for row in rows:
        groups[row["category"]].append(row)
    aggregate = {
        category: {
            "cases": len(items),
            "hit_at_5": sum(item["hit_at_5"] for item in items),
            "complete_at_5": sum(item["complete_at_5"] for item in items),
            "complete_at_100": sum(item["complete_at_100"] for item in items),
        }
        for category, items in groups.items()
    }
    report = {
        "kind": "beam_100k_source_message_retrieval_proxy",
        "source_revision": SOURCE_REVISION,
        "source_sha256": SOURCE_SHA256,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "store_sha256": hashlib.sha256(Path("app/store.py").read_bytes()).hexdigest(),
        "split": "conversation IDs 1..14 development; 15..20 untouched holdout",
        "development_conversations_run": args.development_conversations,
        "top_k": args.top_k,
        "retrieval_config": {
            "linkage_enabled": config.linkage_enabled,
            "expansion_enabled": config.expansion_enabled,
            "temporal_enabled": config.temporal_enabled,
        },
        "filter_english_entities": args.filter_english_entities,
        "case_count": len(rows),
        "aggregate": aggregate,
        "rows": rows,
        "note": "Source-message retrieval only; not BEAM rubric, AML F1 or answer correctness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"case_count": len(rows), "aggregate": aggregate}))
    if args.filter_english_entities:
        store_module.entity_terms = _ORIGINAL_ENTITY_TERMS


if __name__ == "__main__":
    main()
