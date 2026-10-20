"""Adapt pinned PersonaMem-v1 32K multiple-choice cases without persona leakage.

Upstream system turns contain the synthetic persona and are deliberately excluded
from memory input. PersonaMem provides no evidence-source labels, so these cases
are for answer-level evaluation only, not source-level retrieval metrics.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path

from benchmarks.public_eval_schema import SCHEMA_VERSION, validate_suite


REVISION = "a8076d5608c93ba2a28983cd78aa99b01a163ae7"
QUESTIONS_SHA256 = "cccd34cf53e0bc4d9536c04cff5ca045156d9a4e227e83327112482840bbc93c"
CONTEXTS_SHA256 = "217247ebfec9e8442fc53570c795ab69f21aad08745f7de78d9beab51b122d4a"
SPLIT_SALT = "aml-personamem-v1-32k-context-v1"


def _file_hash(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _split(context_id: str) -> str:
    digest = hashlib.sha256(f"{SPLIT_SALT}:{context_id}".encode()).digest()
    return "frozen_holdout" if int.from_bytes(digest[:8], "big") % 5 == 0 else "development"


def _sessions(context_id: str, turns: list[dict], end_index: int) -> list[dict]:
    if not 0 <= end_index < len(turns):
        raise ValueError(f"context cutoff outside {context_id}")
    grouped: list[list[dict]] = []
    for turn in turns[: end_index + 1]:
        role = turn.get("role")
        if role == "system":
            grouped.append([])
            continue
        if role not in {"user", "assistant"} or not isinstance(turn.get("content"), str):
            raise ValueError(f"unsupported turn in {context_id}")
        if not grouped:
            raise ValueError(f"missing system boundary in {context_id}")
        if turn["content"].strip():
            grouped[-1].append({"role": role, "content": turn["content"]})
    memories = []
    for index, session in enumerate(grouped):
        if not session:
            continue
        memories.append({
            "memory_id": f"{context_id}:session:{index}",
            "role": "tool",
            "timestamp": None,
            "turns": session,
            "content": "\n".join(f"[{turn['role']}] {turn['content']}" for turn in session),
        })
    if not memories:
        raise ValueError(f"no conversation turns in {context_id}")
    return memories


def adapt_source(questions: Path, contexts: Path) -> dict:
    if questions.name != "questions_32k.csv" or contexts.name != "shared_contexts_32k.jsonl":
        raise ValueError("expected official PersonaMem-v1 32K filenames")
    if _file_hash(questions) != QUESTIONS_SHA256 or _file_hash(contexts) != CONTEXTS_SHA256:
        raise ValueError("PersonaMem source SHA-256 does not match pinned data")
    context_map = {}
    for line in contexts.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if not isinstance(record, dict) or len(record) != 1:
            raise ValueError("invalid shared context record")
        context_id, turns = next(iter(record.items()))
        if context_id in context_map:
            raise ValueError(f"duplicate shared context {context_id}")
        context_map[context_id] = turns
    with questions.open(encoding="utf-8-sig", newline="") as source:
        records = list(csv.DictReader(source))
    if len(records) != 589 or len(context_map) != 37:
        raise ValueError("unexpected PersonaMem-v1 32K source shape")
    cases = []
    for record in records:
        context_id = record["shared_context_id"]
        if context_id not in context_map:
            raise ValueError(f"missing shared context {context_id}")
        options = ast.literal_eval(record["all_options"])
        if not isinstance(options, list) or any(not isinstance(option, str) for option in options):
            raise ValueError(f"invalid options for {record['question_id']}")
        correct = record["correct_answer"].strip()
        matches = [option for option in options if option.startswith(correct + " ")]
        if len(matches) != 1:
            raise ValueError(f"ambiguous correct option for {record['question_id']}")
        case = {
            "case_id": f"personamem-v1-32k:{record['question_id']}",
            "dataset": "PersonaMem-v1 32K",
            "dataset_version": REVISION,
            "source_record_id": record["question_id"],
            "license": "MIT",
            "split": _split(context_id),
            "language": "en",
            "capabilities": [record["question_type"]],
            "memories": _sessions(context_id, context_map[context_id], int(record["end_index_in_shared_context"])),
            "question": record["user_question_or_message"],
            "choices": options,
            "reference_answers": matches,
            "source_answer_raw": correct,
            "scorer": "multiple_choice",
            "shared_context_id": context_id,
            "source_end_index_in_shared_context": int(record["end_index_in_shared_context"]),
            "score_note": "Answer-level multiple-choice only; no evidence labels; upstream system persona excluded",
        }
        cases.append(case)
    document = {
        "schema_version": SCHEMA_VERSION,
        "source_files": [questions.name, contexts.name],
        "source_sha256": {questions.name: QUESTIONS_SHA256, contexts.name: CONTEXTS_SHA256},
        "dataset_version": REVISION,
        "split_method": f"sha256({SPLIT_SALT}:shared_context_id) first 8 bytes modulo 5; zero=holdout",
        "cases": cases,
    }
    validate_suite(document)
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("data/questions_32k.csv"))
    parser.add_argument("--contexts", type=Path, default=Path("data/shared_contexts_32k.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = adapt_source(args.questions, args.contexts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"cases={len(document['cases'])} output_sha256={_file_hash(args.output)}")


if __name__ == "__main__":
    main()
