import io
import tempfile
import unittest
from pathlib import Path

from botocore.exceptions import ClientError

from app.overflow import OverflowJournal
from app.store import MemoryStore


class _Bucket:
    def __init__(self):
        self.objects = {}
        self.fail_put = False

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, *, Bucket, Key, Body):
        if self.fail_put:
            raise RuntimeError("bucket unavailable")
        self.objects[Key] = Body

    def get_paginator(self, operation):
        return self

    def paginate(self, *, Bucket, Prefix):
        yield {"Contents": [{"Key": key} for key in sorted(self.objects)
                            if key.startswith(Prefix)]}


class OverflowTests(unittest.TestCase):
    def test_rebuilds_from_seed_and_durable_adds(self):
        with tempfile.TemporaryDirectory() as directory:
            seed = Path(directory) / "seed.db"
            runtime = Path(directory) / "runtime.db"
            original = MemoryStore(seed, embedder=False, compress_text=True)
            original.add("before", "user", "s1", [{"role": "user", "content": "before"}])
            journal = OverflowJournal.__new__(OverflowJournal)
            journal.bucket = "test"
            journal.client = _Bucket()
            keys = journal.prepare(seed_path=seed, runtime_path=runtime)
            self.assertEqual(keys, [])
            store = MemoryStore(runtime, embedder=False, compress_text=True, journal=journal)
            store.add("after", "user", "s2", [{"role": "user", "content": "after"}])
            self.assertEqual(len(journal.client.objects), 1)
            keys = journal.prepare(seed_path=seed, runtime_path=runtime)
            rebuilt = MemoryStore(runtime, embedder=False, compress_text=True, journal=journal)
            self.assertEqual(journal.replay(rebuilt, keys), 1)
            with rebuilt._connection() as connection:
                rows = connection.execute("SELECT request_id FROM memories ORDER BY request_id").fetchall()
            self.assertEqual([row[0] for row in rows], ["after", "before"])
            rebuilt.add("after", "user", "s2", [{"role": "user", "content": "after"}])
            self.assertEqual(len(journal.client.objects), 1)

    def test_bucket_failure_rolls_back_add(self):
        with tempfile.TemporaryDirectory() as directory:
            seed = Path(directory) / "seed.db"
            MemoryStore(seed, embedder=False)
            journal = OverflowJournal.__new__(OverflowJournal)
            journal.bucket = "test"
            journal.client = _Bucket()
            runtime = Path(directory) / "runtime.db"
            journal.prepare(seed_path=seed, runtime_path=runtime)
            store = MemoryStore(runtime, embedder=False, journal=journal)
            journal.client.fail_put = True
            with self.assertRaisesRegex(RuntimeError, "bucket unavailable"):
                store.add("failed", "user", "s1", [{"role": "user", "content": "text"}])
            with store._connection() as connection:
                count = connection.execute("SELECT count(*) FROM memories").fetchone()[0]
            self.assertEqual(count, 0)

    def test_retry_after_journal_write_keeps_original_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            seed = Path(directory) / "seed.db"
            MemoryStore(seed, embedder=False)
            journal = OverflowJournal.__new__(OverflowJournal)
            journal.bucket = "test"
            journal.client = _Bucket()
            messages = [{"role": "user", "content": "text"}]
            import hashlib
            import json
            payload_hash = hashlib.sha256(json.dumps(
                {"session_id": "s1", "messages": messages}, ensure_ascii=False,
                sort_keys=True, separators=(",", ":")
            ).encode("utf-8")).hexdigest()
            journal.record(request_id="retry", user_id="user", session_id="s1",
                           messages=messages, created_at="2026-11-01T00:00:00Z",
                           payload_hash=payload_hash)
            runtime = Path(directory) / "runtime.db"
            journal.prepare(seed_path=seed, runtime_path=runtime)
            store = MemoryStore(runtime, embedder=False, journal=journal)
            store.add("retry", "user", "s1", messages)
            with store._connection() as connection:
                created_at = connection.execute(
                    "SELECT created_at FROM memories WHERE request_id = 'retry'"
                ).fetchone()[0]
            self.assertEqual(created_at, "2026-11-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
