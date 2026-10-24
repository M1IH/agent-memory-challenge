"""Offline upper-bound probe for compressing existing SQLite text columns.

Uses pinned public development histories. This does not change production
storage format: compressed database copies are deliberately unreadable by the
service and are measured only to decide whether a real migration is worthwhile.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import tempfile
import zlib
from contextlib import closing
from pathlib import Path

from app.store import MemoryStore
from benchmarks.probe_public_volume_growth import (
    beam_batches,
    chunks,
    longmemeval_batches,
    personamem_batches,
)


def measure(name: str, batches, data_dir: Path, limit: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="compression-", dir=data_dir) as temp:
        root = Path(temp)
        source = root / "original.db"
        store = MemoryStore(source, embedder=False)
        count = 0
        requests = 0
        for user_id, session_id, messages in batches:
            for part in chunks(messages, store.max_add_chars):
                part = part[:limit - count]
                if not part:
                    break
                store.add(
                    request_id=f"compression:{name}:{requests}",
                    user_id=user_id,
                    session_id=session_id,
                    messages=part,
                )
                count += len(part)
                requests += 1
            if count >= limit:
                break
        with closing(sqlite3.connect(source)) as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            rows = db.execute("SELECT rowid, content, terms FROM memories").fetchall()
        if len(rows) != count:
            raise AssertionError("unexpected stored row count")
        original = source.stat().st_size
        measures = {}
        for columns in (("content",), ("terms",), ("content", "terms")):
            target = root / ("-".join(columns) + ".db")
            shutil.copy2(source, target)
            with closing(sqlite3.connect(target)) as db:
                if "content" in columns:
                    db.executemany(
                        "UPDATE memories SET content = ? WHERE rowid = ?",
                        ((zlib.compress(content.encode("utf-8"), level=6), rowid)
                         for rowid, content, _ in rows),
                    )
                if "terms" in columns:
                    db.executemany(
                        "UPDATE memories SET terms = ? WHERE rowid = ?",
                        ((zlib.compress(terms.encode("utf-8"), level=6), rowid)
                         for rowid, _, terms in rows),
                    )
                db.commit()
                db.execute("VACUUM")
                db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            measures["+".join(columns)] = target.stat().st_size
        return {
            "dataset": name,
            "messages": count,
            "original_db_bytes": original,
            "compressed_db_bytes": measures,
            "compression_fraction": {
                key: round(1 - value / original, 4)
                for key, value in measures.items()
            },
            "warning": "Compressed copies are not a supported service format.",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--limit-messages", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=Path("data/volume-compression.json"))
    args = parser.parse_args()
    if args.limit_messages < 100:
        parser.error("--limit-messages must be at least 100")
    os.environ["AML_EMBED_ENABLED"] = "false"
    os.environ["AML_MEMORY_CACHE_USERS"] = "1"
    data_dir = args.data_dir.resolve()
    results = [
        measure(name, batches(data_dir), data_dir, args.limit_messages)
        for name, batches in (
            ("LongMemEval-S development", longmemeval_batches),
            ("PersonaMem-v1 development", personamem_batches),
            ("BEAM 100K development", beam_batches),
        )
    ]
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results))


if __name__ == "__main__":
    main()
