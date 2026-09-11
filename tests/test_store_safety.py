import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from app.store import (
    MemoryStore,
    entity_terms,
    memory_snapshot_size_bytes,
    nonnegative_cache_users,
    PayloadTooLargeError,
    positive_cache_bytes,
    positive_context_chars,
    positive_payload_chars,
)


class StoreSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "safety.db"

    def tearDown(self):
        self.directory.cleanup()

    def test_context_character_limit_must_be_positive_integer(self):
        self.assertEqual(1200, positive_context_chars("1200"))
        for value in ("0", "-1", "invalid"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "AML_MAX_CONTEXT_CHARS"
            ):
                positive_context_chars(value)

    def test_context_character_limit_is_validated_when_store_starts(self):
        with patch.dict("os.environ", {"AML_MAX_CONTEXT_CHARS": "invalid"}):
            with self.assertRaisesRegex(ValueError, "AML_MAX_CONTEXT_CHARS"):
                MemoryStore(self.path, embedder=False)

    def test_payload_character_limits_must_be_positive_integers(self):
        self.assertEqual(200000, positive_payload_chars("200000", "LIMIT"))
        for value in ("0", "-1", "invalid"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "LIMIT"):
                positive_payload_chars(value, "LIMIT")

    def test_oversized_add_is_rejected_before_embedding(self):
        encoder = Mock()
        encoder.encode.return_value = [np.array([1.0], dtype=np.float32)]
        store = MemoryStore(self.path, embedder=encoder)
        store.max_add_chars = 3

        with self.assertRaises(PayloadTooLargeError):
            store.add(
                "large", "alice", "session",
                [{"role": "user", "content": "four"}],
            )

        encoder.encode.assert_not_called()
        with store._connection() as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM add_requests").fetchone()[0])

        store.add(
            "large", "alice", "session",
            [{"role": "user", "content": "ok"}],
        )

        encoder.encode.assert_called_once()
        with store._connection() as connection:
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM add_requests").fetchone()[0])

    def test_memory_cache_user_limit_must_be_non_negative_integer(self):
        self.assertEqual(0, nonnegative_cache_users("0"))
        self.assertEqual(2, nonnegative_cache_users("2"))
        for value in ("-1", "invalid"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "AML_MEMORY_CACHE_USERS"
            ):
                nonnegative_cache_users(value)

    def test_memory_cache_byte_limit_must_be_positive_integer(self):
        self.assertEqual(1, positive_cache_bytes("1"))
        for value in ("0", "-1", "invalid"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "AML_MEMORY_CACHE_MAX_BYTES"
            ):
                positive_cache_bytes(value)

    def test_oversized_snapshot_is_not_cached(self):
        with patch.dict(
            "os.environ",
            {"AML_MEMORY_CACHE_USERS": "2", "AML_MEMORY_CACHE_MAX_BYTES": "1"},
        ):
            store = MemoryStore(self.path, embedder=False)
        store.add("one", "alice", "session", [{"role": "user", "content": "tea"}])

        memories = store._load_user_memories("alice")

        self.assertGreater(memory_snapshot_size_bytes(memories), 1)
        self.assertEqual({}, store._memory_cache)
        self.assertEqual(0, store._memory_cache_bytes)

    def test_concurrent_oversized_snapshot_is_loaded_once_for_waiters(self):
        with patch.dict(
            "os.environ",
            {"AML_MEMORY_CACHE_USERS": "1", "AML_MEMORY_CACHE_MAX_BYTES": "1"},
        ):
            store = MemoryStore(self.path, embedder=False)
        store.add("one", "alice", "session", [{"role": "user", "content": "tea"}])
        original_connection = store._connection
        original_estimate = memory_snapshot_size_bytes
        connection_count = 0
        count_lock = threading.Lock()
        estimate_started = threading.Event()
        waiter_checked_generation = threading.Event()

        @contextmanager
        def controlled_connection():
            nonlocal connection_count
            with count_lock:
                connection_count += 1
                call_number = connection_count
            with original_connection() as connection:
                yield connection
            if call_number == 3:
                waiter_checked_generation.set()

        def controlled_estimate(memories):
            estimate_started.set()
            if not waiter_checked_generation.wait(timeout=5):
                raise AssertionError("waiting loader did not reach generation check")
            return original_estimate(memories)

        with (
            patch.object(store, "_connection", controlled_connection),
            patch("app.store.memory_snapshot_size_bytes", controlled_estimate),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            first = executor.submit(store._load_user_memories, "alice")
            self.assertTrue(estimate_started.wait(timeout=5))
            second = executor.submit(store._load_user_memories, "alice")
            snapshots = [first.result(timeout=10), second.result(timeout=10)]

        self.assertIs(snapshots[0], snapshots[1])
        self.assertEqual(3, connection_count)
        self.assertEqual({}, store._memory_cache)
        self.assertEqual({}, store._cache_loads)

    def test_memory_cache_evicts_users_to_stay_within_byte_budget(self):
        with patch.dict("os.environ", {"AML_MEMORY_CACHE_USERS": "3"}):
            store = MemoryStore(self.path, embedder=False)
        for user_id in ("alice", "bob"):
            store.add(
                f"add-{user_id}", user_id, "session",
                [{"role": "user", "content": user_id}],
            )
        store._load_user_memories("alice")
        alice_bytes = store._memory_cache["alice"][1]
        store.memory_cache_max_bytes = alice_bytes

        store._load_user_memories("bob")

        self.assertNotIn("alice", store._memory_cache)
        self.assertIn("bob", store._memory_cache)
        self.assertLessEqual(store._memory_cache_bytes, store.memory_cache_max_bytes)

    def test_memory_cache_is_reused_then_invalidated_by_add(self):
        with patch.dict("os.environ", {"AML_MEMORY_CACHE_USERS": "2"}):
            store = MemoryStore(self.path, embedder=False)
        store.add("one", "alice", "session", [{"role": "user", "content": "tea"}])

        first = store._load_user_memories("alice")
        second = store._load_user_memories("alice")
        store.add("two", "alice", "session", [{"role": "user", "content": "coffee"}])
        third = store._load_user_memories("alice")

        self.assertIs(first, second)
        self.assertIsNot(second, third)
        self.assertEqual(2, len(third))

    def test_memory_cache_detects_add_from_another_store_instance(self):
        with patch.dict("os.environ", {"AML_MEMORY_CACHE_USERS": "2"}):
            first_store = MemoryStore(self.path, embedder=False)
            second_store = MemoryStore(self.path, embedder=False)
        first_store.add(
            "one", "alice", "session", [{"role": "user", "content": "tea"}]
        )
        cached = first_store._load_user_memories("alice")

        second_store.add(
            "two", "alice", "session", [{"role": "user", "content": "coffee"}]
        )
        refreshed = first_store._load_user_memories("alice")

        self.assertIsNot(cached, refreshed)
        self.assertEqual(2, len(refreshed))

    def test_memory_cache_evicts_least_recently_used_user(self):
        with patch.dict("os.environ", {"AML_MEMORY_CACHE_USERS": "2"}):
            store = MemoryStore(self.path, embedder=False)
        for user_id in ("alice", "bob", "carol"):
            store.add(
                f"add-{user_id}",
                user_id,
                "session",
                [{"role": "user", "content": user_id}],
            )

        alice = store._load_user_memories("alice")
        store._load_user_memories("bob")
        self.assertIs(alice, store._load_user_memories("alice"))
        store._load_user_memories("carol")

        self.assertEqual(["alice", "carol"], list(store._memory_cache))
        self.assertNotIn("bob", store._memory_cache)

    def test_concurrent_cache_miss_uses_one_loaded_snapshot(self):
        with patch.dict("os.environ", {"AML_MEMORY_CACHE_USERS": "1"}):
            store = MemoryStore(self.path, embedder=False)
        store.add(
            "batch",
            "alice",
            "session",
            [
                {"role": "user", "content": f"record {index}"}
                for index in range(200)
            ],
        )
        barrier = threading.Barrier(16)

        def load(_: int) -> list:
            barrier.wait(timeout=5)
            return store._load_user_memories("alice")

        with ThreadPoolExecutor(max_workers=16) as executor:
            snapshots = list(executor.map(load, range(16)))

        self.assertEqual(1, len({id(snapshot) for snapshot in snapshots}))

    def test_failed_cache_load_wakes_waiter_and_allows_retry(self):
        with patch.dict("os.environ", {"AML_MEMORY_CACHE_USERS": "1"}):
            store = MemoryStore(self.path, embedder=False)
        store.add("one", "alice", "session", [{"role": "user", "content": "tea"}])
        original_connection = store._connection
        connection_count = 0
        count_lock = threading.Lock()
        failed_load_started = threading.Event()
        waiter_checked_generation = threading.Event()

        @contextmanager
        def controlled_connection():
            nonlocal connection_count
            with count_lock:
                connection_count += 1
                call_number = connection_count
            if call_number == 2:
                failed_load_started.set()
                if not waiter_checked_generation.wait(timeout=5):
                    raise AssertionError("waiting loader did not reach generation check")
                raise sqlite3.OperationalError("simulated load failure")
            with original_connection() as connection:
                yield connection
            if call_number == 3:
                waiter_checked_generation.set()

        def load() -> list:
            return store._load_user_memories("alice")

        with patch.object(store, "_connection", controlled_connection):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(load)]
                self.assertTrue(failed_load_started.wait(timeout=5))
                futures.append(executor.submit(load))
                outcomes = []
                for future in futures:
                    try:
                        outcomes.append(future.result(timeout=10))
                    except sqlite3.OperationalError:
                        outcomes.append("failed")

        self.assertEqual(1, outcomes.count("failed"))
        successful = next(result for result in outcomes if result != "failed")
        self.assertEqual(1, len(successful))
        self.assertIs(successful, store._load_user_memories("alice"))
        self.assertEqual({}, store._cache_loads)

    def test_delimiter_in_identifiers_does_not_drop_another_users_memory(self):
        store = MemoryStore(self.path, embedder=False)
        for request_id, user_id in (("a\0b", "c"), ("a", "b\0c")):
            store.add(request_id, user_id, "session", [{"role": "user", "content": "tea"}])
        for user_id in ("c", "b\0c"):
            self.assertEqual(1, len(store.search(user_id, "tea", 10)))

    def test_replay_and_conflict_do_not_require_working_encoder(self):
        encoder = Mock()
        encoder.encode.return_value = [np.array([1.0], dtype=np.float32)]
        store = MemoryStore(self.path, embedder=encoder)
        messages = [{"role": "user", "content": "tea"}]
        store.add("req", "alice", "session", messages)
        encoder.encode.side_effect = RuntimeError("encoder offline")
        store.add("req", "alice", "session", messages)
        with self.assertRaises(ValueError):
            store.add("req", "alice", "session", [{"role": "user", "content": "coffee"}])
        self.assertEqual(1, encoder.encode.call_count)

    def test_connection_is_closed_if_pragma_fails(self):
        store = MemoryStore(self.path, embedder=False)
        connection = Mock()
        connection.execute.side_effect = sqlite3.OperationalError("database locked")
        with patch("app.store.sqlite3.connect", return_value=connection):
            with self.assertRaises(sqlite3.OperationalError):
                store._connect()
        connection.close.assert_called_once()

    def test_legacy_request_without_ledger_is_not_duplicated(self):
        store = MemoryStore(self.path, embedder=False)
        messages = [{"role": "user", "content": "tea"}]
        store.add("req", "alice", "session", messages)
        with store._connection() as connection:
            connection.execute("DELETE FROM add_requests")
        with self.assertRaisesRegex(ValueError, "legacy request_id"):
            store.add("req", "alice", "session", messages)
        self.assertEqual(1, len(store.search("alice", "tea", 10)))
        with store._connection() as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM add_requests").fetchone()[0])

    def test_tied_ranks_do_not_depend_on_insertion_order(self):
        first = MemoryStore(self.path, embedder=False)
        second = MemoryStore(Path(self.directory.name) / "other.db", embedder=False)
        for store, requests in ((first, ["a", "b"]), (second, ["b", "a"])):
            for request in requests:
                store.add(request, "alice", "s", [{"role": "user", "content": "tea"}])
        self.assertEqual(
            [row["id"] for row in first.search("alice", "tea", 2)],
            [row["id"] for row in second.search("alice", "tea", 2)],
        )

    def test_know_does_not_trigger_now_temporal_boost(self):
        store = MemoryStore(self.path, embedder=False)
        store.add("a", "alice", "s", [{"role": "user", "content": "My desk location is Room-204."}])
        store.add("b", "alice", "s", [{"role": "user", "content": "My lunch changed to soup."}])
        self.assertIn("Room-204", store.search("alice", "Do you know my desk location?", 1)[0]["content"])

    def test_nonfinite_persisted_vector_falls_back_to_lexical_search(self):
        encoder = Mock()
        encoder.index_identity = "test:finite-v1"
        encoder.encode.return_value = [np.array([1.0, 0.0], dtype=np.float32)]
        store = MemoryStore(self.path, embedder=encoder)
        store.add(
            "req",
            "alice",
            "session",
            [{"role": "user", "content": "My recovery phrase is amber kite."}],
        )
        with store._connection() as connection:
            connection.execute(
                "UPDATE memories SET embedding = ? WHERE user_id = ?",
                (np.array([np.nan, 0.0], dtype=np.float32).tobytes(), "alice"),
            )

        results = store.search("alice", "recovery phrase amber kite", 1)

        self.assertEqual(1, len(results))
        self.assertIn("amber kite", results[0]["content"])
        self.assertTrue(np.isfinite(results[0]["score"]))

    def test_query_encoder_failure_falls_back_to_lexical_search(self):
        encoder = Mock()
        encoder.index_identity = "test:failure-v1"
        encoder.encode.return_value = [np.array([1.0, 0.0], dtype=np.float32)]
        store = MemoryStore(self.path, embedder=encoder)
        store.add(
            "req",
            "alice",
            "session",
            [{"role": "user", "content": "My fallback phrase is copper moon."}],
        )
        encoder.encode.side_effect = RuntimeError("encoder unavailable")

        with self.assertLogs("app.store", level="WARNING"):
            results = store.search("alice", "fallback phrase copper moon", 1)

        self.assertEqual(1, len(results))
        self.assertIn("copper moon", results[0]["content"])

    def test_search_prefers_query_specific_encoder_when_available(self):
        encoder = Mock()
        encoder.index_identity = "test:query-priority-v1"
        encoder.supports_query_priority = True
        encoder.encode.return_value = [np.array([1.0, 0.0], dtype=np.float32)]
        encoder.encode_query.return_value = [np.array([1.0, 0.0], dtype=np.float32)]
        store = MemoryStore(self.path, embedder=encoder)
        store.add(
            "req",
            "alice",
            "session",
            [{"role": "user", "content": "priority query phrase"}],
        )

        results = store.search("alice", "priority query phrase", 1)

        self.assertEqual(1, len(results))
        encoder.encode_query.assert_called_once()

    def test_nonfinite_query_vector_falls_back_to_lexical_search(self):
        encoder = Mock()
        encoder.index_identity = "test:query-finite-v1"
        encoder.encode.return_value = [np.array([1.0, 0.0], dtype=np.float32)]
        store = MemoryStore(self.path, embedder=encoder)
        store.add(
            "req",
            "alice",
            "session",
            [{"role": "user", "content": "My stable phrase is silver pine."}],
        )
        encoder.encode.return_value = [np.array([np.inf, 0.0], dtype=np.float32)]

        with self.assertLogs("app.store", level="WARNING"):
            results = store.search("alice", "stable phrase silver pine", 1)

        self.assertEqual(1, len(results))
        self.assertIn("silver pine", results[0]["content"])

    def test_failed_add_encoding_does_not_claim_request_id(self):
        encoder = Mock()
        encoder.index_identity = "test:add-retry-v1"
        encoder.encode.side_effect = RuntimeError("encoder unavailable")
        store = MemoryStore(self.path, embedder=encoder)
        payload = [{"role": "user", "content": "retry after recovery"}]

        with self.assertRaisesRegex(RuntimeError, "encoder unavailable"):
            store.add("req", "alice", "session", payload)
        with store._connection() as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM add_requests").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

        encoder.encode.side_effect = None
        encoder.encode.return_value = [np.array([1.0, 0.0], dtype=np.float32)]
        store.add("req", "alice", "session", payload)
        self.assertEqual(1, len(store.search("alice", "retry recovery", 10)))

    def test_generation_failure_rolls_back_add_and_allows_same_request_retry(self):
        store = MemoryStore(self.path, embedder=False)
        payload = [{"role": "user", "content": "retry atomic transaction"}]
        with store._connection() as connection:
            connection.execute(
                """
                CREATE TRIGGER fail_generation BEFORE INSERT ON memory_generations
                BEGIN
                    SELECT RAISE(ABORT, 'forced generation failure');
                END
                """
            )

        with self.assertRaisesRegex(sqlite3.IntegrityError, "forced generation failure"):
            store.add("atomic-request", "alice", "session", payload)

        with store._connection() as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM add_requests").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
            self.assertEqual(
                0,
                connection.execute("SELECT COUNT(*) FROM memory_generations").fetchone()[0],
            )
            connection.execute("DROP TRIGGER fail_generation")

        store.add("atomic-request", "alice", "session", payload)
        self.assertIn(
            "retry atomic transaction",
            store.search("alice", "atomic transaction", 1)[0]["content"],
        )
        with store._connection() as connection:
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM add_requests").fetchone()[0])
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
            self.assertEqual(
                1,
                connection.execute(
                    "SELECT generation FROM memory_generations WHERE user_id = ?",
                    ("alice",),
                ).fetchone()["generation"],
            )

    def test_float64_add_embeddings_are_stored_as_float32_vectors(self):
        encoder = Mock()
        encoder.index_identity = "test:dtype-v1"
        encoder.encode.return_value = [np.array([0.25, 0.75], dtype=np.float64)]
        store = MemoryStore(self.path, embedder=encoder)

        store.add(
            "req", "alice", "session",
            [{"role": "user", "content": "vector dtype boundary"}],
        )

        [memory] = store._load_user_memories("alice")
        self.assertEqual(np.dtype(np.float32), memory.embedding.dtype)
        np.testing.assert_allclose([0.25, 0.75], memory.embedding)

    def test_invalid_add_embedding_does_not_claim_request_id(self):
        encoder = Mock()
        encoder.index_identity = "test:add-vector-validation-v1"
        encoder.encode.return_value = [np.array([np.nan], dtype=np.float32)]
        store = MemoryStore(self.path, embedder=encoder)

        with self.assertRaisesRegex(RuntimeError, "invalid vector"):
            store.add(
                "req", "alice", "session",
                [{"role": "user", "content": "reject invalid vector"}],
            )

        with store._connection() as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM add_requests").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

    def test_missing_add_embedding_does_not_silently_create_lexical_only_row(self):
        encoder = Mock()
        encoder.index_identity = "test:add-missing-vector-v1"
        encoder.encode.return_value = [None]
        store = MemoryStore(self.path, embedder=encoder)

        with self.assertRaisesRegex(RuntimeError, "invalid vector"):
            store.add(
                "req", "alice", "session",
                [{"role": "user", "content": "missing vector"}],
            )

        with store._connection() as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM add_requests").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

    def test_inconsistent_add_embedding_dimensions_are_rejected_atomically(self):
        encoder = Mock()
        encoder.index_identity = "test:add-vector-dimensions-v1"
        encoder.encode.return_value = [
            np.array([1.0], dtype=np.float32),
            np.array([1.0, 0.0], dtype=np.float32),
        ]
        store = MemoryStore(self.path, embedder=encoder)

        with self.assertRaisesRegex(RuntimeError, "inconsistent vector dimensions"):
            store.add(
                "req", "alice", "session",
                [
                    {"role": "user", "content": "first vector"},
                    {"role": "assistant", "content": "second vector"},
                ],
            )

        with store._connection() as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM add_requests").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

    def test_direct_retrieval_skips_corpus_wide_entity_extraction(self):
        store = MemoryStore(self.path, embedder=False)
        for index in range(40):
            store.add(
                f"req-{index}",
                "alice",
                "session",
                [{"role": "user", "content": f"project code token-{index}"}],
            )

        with patch("app.store.entity_terms", wraps=entity_terms) as extractor:
            results = store.search("alice", "project code token-17", 1)

        self.assertIn("token-17", results[0]["content"])
        self.assertLessEqual(extractor.call_count, 6)
