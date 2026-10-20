"""Faithfully adapt pinned LongMemEval S records to the public eval schema.

The downloaded source belongs in ignored ``data/``. ``has_answer`` annotations
are deliberately excluded from retrieval inputs; only the upstream session IDs
define source-level evidence. The output's exact match scorer is a local proxy,
not the dataset's official answer evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.public_eval_schema import SCHEMA_VERSION, validate_suite


DATASET_REVISION = "98d7416c24c778c2fee6e6f3006e7a073259d48f"
SOURCE_SHA256 = "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442"
SOURCE_FILENAME = "longmemeval_s_cleaned.json"
SPLIT_SALT = "aml-longmemeval-s-v1"


def _timestamp_ms(source_date: str) -> int:
    # Upstream dates omit timezone. UTC is an ordering convention here, not a
    # claim about the actual timezone of the source conversation.
    parsed = datetime.strptime(source_date, "%Y/%m/%d (%a) %H:%M")
    return int(parsed.replace(tzinfo=timezone.utc).timestamp() * 1000)


def _split(question_id: str) -> str:
    digest = hashlib.sha256(f"{SPLIT_SALT}:{question_id}".encode()).digest()
    return "frozen_holdout" if int.from_bytes(digest[:8], "big") % 5 == 0 else "development"


def adapt_record(record: dict[str, Any]) -> dict[str, Any]:
    question_id = record["question_id"]
    session_ids = record["haystack_session_ids"]
    sessions = record["haystack_sessions"]
    dates = record["haystack_dates"]
    if len(session_ids) != len(sessions) or len(sessions) != len(dates):
        raise ValueError(f"session/date length mismatch for {question_id}")
    if not set(record["answer_session_ids"]) <= set(session_ids):
        raise ValueError(f"unknown answer session ID for {question_id}")
    counts = Counter(session_ids)
    if any(counts[session_id] != 1 for session_id in record["answer_session_ids"]):
        raise ValueError(f"ambiguous answer session ID for {question_id}")

    memories = []
    occurrences: defaultdict[str, int] = defaultdict(int)
    for session_id, session, date in zip(session_ids, sessions, dates):
        occurrences[session_id] += 1
        memory_id = session_id if occurrences[session_id] == 1 else f"{session_id}#duplicate-{occurrences[session_id]}"
        turns = [{"role": turn["role"], "content": turn["content"]} for turn in session]
        if not turns:
            raise ValueError(f"empty session {session_id} for {question_id}")
        memories.append({
            "memory_id": memory_id,
            "source_session_id": session_id,
            "role": "tool",  # Aggregate wrapper only; replay uses original turn roles.
            "timestamp": _timestamp_ms(date),
            "source_date_text": date,
            "turns": turns,
            "content": "\n".join(f"[{turn['role']}] {turn['content']}" for turn in turns),
        })

    raw_answer = record["answer"]
    if not isinstance(raw_answer, (str, int)) or isinstance(raw_answer, bool):
        raise ValueError(f"unsupported answer type for {question_id}")
    return {
        "case_id": f"longmemeval-s:{question_id}",
        "dataset": "LongMemEval-S cleaned",
        "dataset_version": DATASET_REVISION,
        "source_record_id": question_id,
        "license": "MIT",
        "split": _split(question_id),
        "language": "en",
        "capabilities": [record["question_type"]],
        "memories": memories,
        "question": record["question"],
        "query_time": _timestamp_ms(record["question_date"]),
        "source_question_date_text": record["question_date"],
        "evidence_memory_ids": list(record["answer_session_ids"]),
        "reference_answers": [str(raw_answer)],
        "source_answer_raw": raw_answer,
        "scorer": "exact_match",
        "score_note": "Normalized exact match proxy; not the official LongMemEval judge",
    }


def adapt_source(source: Path, *, limit: int | None = None) -> dict[str, Any]:
    if source.name != SOURCE_FILENAME:
        raise ValueError(f"expected {SOURCE_FILENAME}")
    with source.open("rb") as source_file:
        source_hash = hashlib.file_digest(source_file, "sha256").hexdigest()
    if source_hash != SOURCE_SHA256:
        raise ValueError("LongMemEval source SHA-256 does not match pinned data")
    records = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(records, list) or len(records) != 500:
        raise ValueError("expected 500 LongMemEval-S records")
    if limit is not None and not 1 <= limit <= len(records):
        raise ValueError("limit must be between 1 and 500")
    cases = [adapt_record(record) for record in records[:limit]]
    document = {
        "schema_version": SCHEMA_VERSION,
        "source_file": SOURCE_FILENAME,
        "source_sha256": source_hash,
        "dataset_version": DATASET_REVISION,
        "split_method": f"sha256({SPLIT_SALT}:question_id) first 8 bytes modulo 5; zero=holdout",
        "cases": cases,
    }
    validate_suite(document)
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data") / SOURCE_FILENAME)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None, help="diagnostic subset only")
    args = parser.parse_args()
    document = adapt_source(args.source, limit=args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"cases={len(document['cases'])} output_sha256={hashlib.sha256(args.output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
