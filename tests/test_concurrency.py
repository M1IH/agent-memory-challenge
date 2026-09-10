import multiprocessing
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

from app.store import MemoryStore


def add_from_fresh_process(database_path: str, index: int) -> int:
    store = MemoryStore(database_path, embedder=False)
    store.add(
        request_id=f"process-request-{index}",
        user_id="alice",
        session_id=f"process-session-{index // 4}",
        messages=[
            {
                "role": "user",
                "content": f"process-memory-token-{index}",
                "timestamp": 1704067200000 + index,
            }
        ],
    )
    return index


class ConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = MemoryStore(
            Path(self.temp_dir.name) / "concurrency.db",
            embedder=False,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_64_concurrent_adds_are_all_searchable(self):
        def add(index: int) -> None:
            self.store.add(
                request_id=f"request-{index}",
                user_id="alice",
                session_id=f"session-{index // 20}",
                messages=[
                    {
                        "role": "user",
                        "content": f"unique-memory-token-{index}",
                        "timestamp": 1704067200000 + index,
                    }
                ],
            )

        with ThreadPoolExecutor(max_workers=64) as executor:
            list(executor.map(add, range(64)))

        for index in range(64):
            results = self.store.search("alice", f"unique-memory-token-{index}", 1)
            self.assertEqual(1, len(results))
            self.assertIn(f"unique-memory-token-{index}", results[0]["content"])

    def test_concurrent_searches_are_deterministic(self):
        for index in range(32):
            self.store.add(
                request_id=f"request-{index}",
                user_id="alice",
                session_id="session-1",
                messages=[
                    {
                        "role": "user",
                        "content": f"project code name is comet-{index}",
                        "timestamp": 1704067200000 + index,
                    }
                ],
            )

        def search(_: int) -> str:
            return self.store.search("alice", "project code name comet-17", 1)[0]["id"]

        with ThreadPoolExecutor(max_workers=32) as executor:
            result_ids = list(executor.map(search, range(64)))
        self.assertEqual(1, len(set(result_ids)))

    def test_same_request_is_idempotent_across_store_instances(self):
        path = Path(self.temp_dir.name) / "multi-instance.db"
        stores = [MemoryStore(path, embedder=False), MemoryStore(path, embedder=False)]
        payload = [{"role": "user", "content": "only once", "timestamp": None}]

        def add(index: int) -> None:
            stores[index % 2].add("same-request", "alice", "session", payload)

        with ThreadPoolExecutor(max_workers=16) as executor:
            list(executor.map(add, range(64)))

        results = stores[0].search("alice", "only once", 10)
        self.assertEqual(1, len(results))

    def test_fresh_processes_can_initialize_and_write_one_database(self):
        path = Path(self.temp_dir.name) / "multi-process.db"
        context = multiprocessing.get_context("spawn")

        with ProcessPoolExecutor(max_workers=8, mp_context=context) as executor:
            completed = list(
                executor.map(
                    add_from_fresh_process,
                    [str(path)] * 16,
                    range(16),
                )
            )

        self.assertEqual(list(range(16)), completed)
        reopened = MemoryStore(path, embedder=False)
        for index in range(16):
            results = reopened.search("alice", f"process-memory-token-{index}", 1)
            self.assertEqual(1, len(results))
            self.assertIn(f"process-memory-token-{index}", results[0]["content"])
        with reopened._connection() as connection:
            generation = connection.execute(
                "SELECT generation FROM memory_generations WHERE user_id = ?",
                ("alice",),
            ).fetchone()["generation"]
            self.assertEqual(16, generation)


if __name__ == "__main__":
    unittest.main()
