import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from app.store import MemoryStore


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
