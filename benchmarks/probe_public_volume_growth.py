"""Measure SQLite volume growth from pinned public Add histories only.

This probe does not send data to a remote service and never writes questions,
answers, options, gold source IDs, or BEAM rubrics to the memory store.
The output contains aggregate sizes only; temporary databases live under data/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from collections.abc import Iterable, Iterator
from pathlib import Path

from app.store import MemoryStore
from benchmarks.adapt_longmemeval import _split as longmemeval_split
from benchmarks.adapt_longmemeval import _timestamp_ms as longmemeval_timestamp
from benchmarks.adapt_personamem import _sessions as personamem_sessions
from benchmarks.adapt_personamem import _split as personamem_split
from benchmarks.probe_beam_100k import load_rows as load_beam_rows


SOURCE_HASHES = {
    "longmemeval_s_cleaned.json": "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442",
    "questions_32k.csv": "cccd34cf53e0bc4d9536c04cff5ca045156d9a4e227e83327112482840bbc93c",
    "shared_contexts_32k.jsonl": "217247ebfec9e8442fc53570c795ab69f21aad08745f7de78d9beab51b122d4a",
    "beam-100k.parquet": "c0519be25907005ba873c927c50877471d550873039d96c041554d0075a78ace",
}
CHECKPOINTS = (100, 500, 1000, 2500, 5000, 10000)


def file_hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verified(path: Path) -> Path:
    expected = SOURCE_HASHES[path.name]
    if file_hash(path) != expected:
        raise ValueError(f"source hash mismatch: {path.name}")
    return path


def longmemeval_batches(data_dir: Path) -> Iterator[tuple[str, str, list[dict]]]:
    records = json.loads(verified(data_dir / "longmemeval_s_cleaned.json").read_text(encoding="utf-8"))
    for record in records:
        if longmemeval_split(record["question_id"]) != "development":
            continue
        user_id = f"volume-longmemeval:{record['question_id']}"
        for index, (session, session_id, date) in enumerate(zip(
            record["haystack_sessions"], record["haystack_session_ids"], record["haystack_dates"]
        )):
            timestamp = longmemeval_timestamp(date)
            messages = [
                {"role": turn["role"], "content": turn["content"], "timestamp": timestamp}
                for turn in session
            ]
            yield user_id, f"{session_id}:{index}", messages


def personamem_batches(data_dir: Path) -> Iterator[tuple[str, str, list[dict]]]:
    contexts = {}
    path = verified(data_dir / "shared_contexts_32k.jsonl")
    for line in path.read_text(encoding="utf-8").splitlines():
        contexts.update(json.loads(line))
    with verified(data_dir / "questions_32k.csv").open(encoding="utf-8-sig", newline="") as handle:
        for record in csv.DictReader(handle):
            context_id = record["shared_context_id"]
            if personamem_split(context_id) != "development":
                continue
            user_id = f"volume-personamem:{record['question_id']}"
            for memory in personamem_sessions(
                context_id, contexts[context_id], int(record["end_index_in_shared_context"])
            ):
                yield user_id, memory["memory_id"], memory["turns"]


def beam_batches(data_dir: Path) -> Iterator[tuple[str, str, list[dict]]]:
    for conversation in load_beam_rows(verified(data_dir / "beam-100k.parquet")):
        conversation_id = int(conversation["conversation_id"])
        if not 1 <= conversation_id <= 14:
            continue
        user_id = f"volume-beam:{conversation_id}"
        for batch_index, batch in enumerate(conversation["chat"]):
            for message in batch:
                yield (
                    user_id,
                    f"batch:{batch_index + 1}:message:{message['id']}",
                    [{"role": message["role"], "content": message["content"]}],
                )


def chunks(messages: list[dict], max_chars: int) -> Iterator[list[dict]]:
    """Keep Add requests within the service's 20-message/character bounds."""
    pending: list[dict] = []
    pending_chars = 0
    for message in messages:
        content = message["content"]
        if not isinstance(content, str) or not content.strip():
            continue
        for start in range(0, len(content), max_chars):
            part = {**message, "content": content[start:start + max_chars]}
            if pending and (len(pending) == 20 or pending_chars + len(part["content"]) > max_chars):
                yield pending
                pending, pending_chars = [], 0
            pending.append(part)
            pending_chars += len(part["content"])
    if pending:
        yield pending


def disk_sizes(path: Path) -> dict[str, int]:
    sizes = {
        "db": path.stat().st_size if path.exists() else 0,
        "wal": Path(f"{path}-wal").stat().st_size if Path(f"{path}-wal").exists() else 0,
        "shm": Path(f"{path}-shm").stat().st_size if Path(f"{path}-shm").exists() else 0,
    }
    sizes["total"] = sum(sizes.values())
    return sizes


def replay(
    name: str,
    batches: Iterable[tuple[str, str, list[dict]]],
    *,
    data_dir: Path,
    limit_messages: int,
    compress_text: bool = False,
) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"volume-{name}-", dir=data_dir) as temp_dir:
        path = Path(temp_dir) / "memory.db"
        store = MemoryStore(path, embedder=False, compress_text=compress_text)
        initial = disk_sizes(path)
        max_total = initial["total"]
        message_count = 0
        request_count = 0
        input_bytes = 0
        input_chars = 0
        users = set()
        snapshots = []
        next_checkpoint = 0
        for user_id, session_id, messages in batches:
            for part in chunks(messages, store.max_add_chars):
                remaining = limit_messages - message_count
                if remaining <= 0:
                    break
                part = part[:remaining]
                store.add(
                    request_id=f"volume:{name}:{request_count}",
                    user_id=user_id,
                    session_id=session_id,
                    messages=part,
                )
                users.add(user_id)
                request_count += 1
                message_count += len(part)
                input_bytes += sum(len(item["content"].encode("utf-8")) for item in part)
                input_chars += sum(len(item["content"]) for item in part)
                sizes = disk_sizes(path)
                max_total = max(max_total, sizes["total"])
                while next_checkpoint < len(CHECKPOINTS) and message_count >= CHECKPOINTS[next_checkpoint]:
                    snapshots.append({"messages": message_count, **sizes})
                    next_checkpoint += 1
            if message_count >= limit_messages:
                break
        before_checkpoint = disk_sizes(path)
        with closing(sqlite3.connect(path)) as connection:
            rows = connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            requests = connection.execute("SELECT COUNT(*) FROM add_requests").fetchone()[0]
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
            page_count = connection.execute("PRAGMA page_count").fetchone()[0]
            checkpoint_result = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        after_checkpoint = disk_sizes(path)
        if rows != message_count or requests != request_count:
            raise AssertionError("stored row/request count differs from replay")
        incremental = max(after_checkpoint["total"] - initial["total"], 1)
        per_message = incremental / message_count
        return {
            "dataset": name,
            "input_messages": message_count,
            "distinct_users": len(users),
            "add_requests": request_count,
            "input_utf8_bytes": input_bytes,
            "input_characters": input_chars,
            "mean_input_utf8_bytes_per_message": input_bytes / message_count,
            "initial_sizes": initial,
            "snapshots": snapshots,
            "before_checkpoint_sizes": before_checkpoint,
            "after_checkpoint_sizes": after_checkpoint,
            "peak_sampled_db_wal_shm_bytes": max_total,
            "sqlite_page_size": page_size,
            "sqlite_page_count": page_count,
            "wal_checkpoint_truncate": checkpoint_result,
            "incremental_bytes": incremental,
            "incremental_bytes_per_message": per_message,
            "sqlite_to_input_utf8_ratio": incremental / input_bytes,
            "estimated_messages_in_empty_500mb_volume": int(500_000_000 / per_message),
            "estimated_additional_messages_after_historical_65mb": int(435_000_000 / per_message),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--limit-messages", type=int, default=5000)
    parser.add_argument("--compress-text", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("data/public-volume-growth.json"))
    args = parser.parse_args()
    if args.limit_messages < 100:
        parser.error("--limit-messages must be at least 100")
    data_dir = args.data_dir.resolve()
    if not data_dir.is_dir():
        parser.error("data directory is missing")
    os.environ["AML_EMBED_ENABLED"] = "false"
    os.environ["AML_MEMORY_CACHE_USERS"] = "1"
    sources = (
        ("LongMemEval-S development", longmemeval_batches(data_dir)),
        ("PersonaMem-v1 development", personamem_batches(data_dir)),
        ("BEAM 100K development conversations 1-14", beam_batches(data_dir)),
    )
    results = [
        replay(
            name, batches, data_dir=data_dir,
            limit_messages=args.limit_messages,
            compress_text=args.compress_text,
        )
        for name, batches in sources
    ]
    report = {
        "method": "MemoryStore.add, lexical, one-user cache; separate temporary SQLite DB per source; max 20 messages and 200000 characters per Add; development histories only; no Search",
        "compress_text": args.compress_text,
        "source_sha256": SOURCE_HASHES,
        "output_scope": "aggregate metrics only; raw histories and temporary DBs not retained",
        "volume_limit_bytes_decimal": 500_000_000,
        "historical_production_used_bytes_approximate": 65_000_000,
        "datasets": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "datasets": [
            {
                "dataset": row["dataset"],
                "messages": row["input_messages"],
                "bytes_per_message": round(row["incremental_bytes_per_message"], 1),
                "estimated_empty_volume_messages": row["estimated_messages_in_empty_500mb_volume"],
            }
            for row in results
        ],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
