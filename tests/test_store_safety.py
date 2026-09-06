import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from app.store import MemoryStore, entity_terms


class StoreSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "safety.db"

    def tearDown(self):
        self.directory.cleanup()

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
