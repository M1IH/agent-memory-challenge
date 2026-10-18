import multiprocessing
import queue
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.store import MemoryStore


def add_then_wait_for_termination(database_path: str, ready) -> None:
    store = MemoryStore(database_path, embedder=False)
    store.add(
        "terminated-process-request",
        "alice",
        "long-session",
        [{"role": "user", "content": "durable before termination"}],
    )
    ready.put("committed")
    time.sleep(60)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "recovery.db"

    def tearDown(self):
        self.directory.cleanup()

    def test_committed_add_survives_process_termination_and_idempotent_replay(self):
        context = multiprocessing.get_context("spawn")
        ready = context.Queue()
        process = context.Process(
            target=add_then_wait_for_termination,
            args=(str(self.path), ready),
        )
        process.start()
        self.assertEqual("committed", ready.get(timeout=15))
        process.terminate()
        process.join(timeout=15)
        self.assertFalse(process.is_alive())

        reopened = MemoryStore(self.path, embedder=False)
        payload = [{"role": "user", "content": "durable before termination"}]
        self.assertIn("durable before termination", reopened.search("alice", "durable", 1)[0]["content"])
        reopened.add("terminated-process-request", "alice", "long-session", payload)
        with reopened._connection() as connection:
            self.assertEqual(1, connection.execute(
                "SELECT COUNT(*) FROM memories WHERE request_id = ?",
                ("terminated-process-request",),
            ).fetchone()[0])
            self.assertEqual(1, connection.execute(
                "SELECT COUNT(*) FROM add_requests WHERE request_id = ?",
                ("terminated-process-request",),
            ).fetchone()[0])

    def test_sqlite_busy_waits_then_commits_without_partial_state(self):
        store = MemoryStore(self.path, embedder=False)
        blocker = sqlite3.connect(self.path, timeout=30)
        blocker.execute("BEGIN EXCLUSIVE")
        outcomes: queue.Queue[BaseException | str] = queue.Queue()

        def add() -> None:
            try:
                store.add(
                    "busy-request",
                    "alice",
                    "session",
                    [{"role": "user", "content": "committed after busy lock"}],
                )
                outcomes.put("committed")
            except BaseException as exc:
                outcomes.put(exc)

        worker = threading.Thread(target=add)
        worker.start()
        time.sleep(0.2)
        self.assertTrue(worker.is_alive())
        blocker.rollback()
        blocker.close()
        worker.join(timeout=15)
        self.assertEqual("committed", outcomes.get_nowait())
        self.assertIn("committed after busy lock", store.search("alice", "busy lock", 1)[0]["content"])

    def test_disk_full_rolls_back_request_ledger_and_memories(self):
        store = MemoryStore(self.path, embedder=False)
        store.add("seed", "alice", "session", [{"role": "user", "content": "seed"}])
        real_connect = sqlite3.connect

        def capacity_limited_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            page_count = connection.execute("PRAGMA page_count").fetchone()[0]
            connection.execute(f"PRAGMA max_page_count={page_count}")
            return connection

        with (
            patch("app.store.sqlite3.connect", side_effect=capacity_limited_connect),
            self.assertRaisesRegex(sqlite3.OperationalError, "full"),
        ):
            store.add(
                "disk-full-request",
                "alice",
                "session",
                [{"role": "user", "content": "x" * 150_000}],
            )

        with store._connection() as connection:
            self.assertEqual(0, connection.execute(
                "SELECT COUNT(*) FROM add_requests WHERE request_id = ?",
                ("disk-full-request",),
            ).fetchone()[0])
            self.assertEqual(0, connection.execute(
                "SELECT COUNT(*) FROM memories WHERE request_id = ?",
                ("disk-full-request",),
            ).fetchone()[0])


if __name__ == "__main__":
    unittest.main()
