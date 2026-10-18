import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.store import MemoryStore, RetrievalConfig, temporal_state, temporal_validity


class TemporalStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "temporal.db"

    def tearDown(self):
        self.temporary.cleanup()

    def test_explicit_state_is_persisted_without_changing_ranking(self):
        store = MemoryStore(self.database, embedder=False)
        store.add(
            "future", "user", "session",
            [{
                "role": "user",
                "content": "The new office opens next month.",
                "observed_at": 1704067200000,
                "valid_from": 1706745600000,
                "valid_to": 1738368000000,
                "retracted_at": 1738454400000,
            }],
        )
        memory = store._load_user_memories("user")[0]
        self.assertIsNone(memory.timestamp_ms)
        self.assertEqual(1704067200000, memory.observed_at_ms)
        self.assertEqual(1706745600000, memory.valid_from_ms)
        self.assertEqual(1738368000000, memory.valid_to_ms)
        self.assertEqual(1738454400000, memory.retracted_at_ms)
        self.assertIn("new office", store.search(
            "user", "Which office opens?", 1, query_at_ms=1705000000000
        )[0]["content"])

    def test_legacy_timestamp_maps_to_observed_at_and_keeps_memory_id(self):
        store = MemoryStore(self.database, embedder=False)
        message = {"role": "user", "content": "Legacy fact.", "timestamp": 1704067200000}
        store.add("request", "user", "session", [message])
        first = store._load_user_memories("user")[0]
        self.assertEqual(first.timestamp_ms, first.observed_at_ms)
        store.add("request", "user", "session", [message])
        second = store._load_user_memories("user")[0]
        self.assertEqual(first.id, second.id)

    def test_fact_triple_is_persisted_without_changing_unstructured_identity(self):
        store = MemoryStore(self.database, embedder=False)
        legacy = {"role": "user", "content": "The project office is Harbor Tower."}
        store.add("legacy", "user", "legacy", [legacy])
        legacy_memory = store._load_user_memories("user")[0]

        structured = {
            **legacy,
            "fact_subject": "project office",
            "fact_relation": "located at",
            "fact_object": "Harbor Tower",
            "observed_at": 10,
        }
        store.add("structured", "user", "structured", [structured])
        memories = store._load_user_memories("user")
        structured_memory = next(item for item in memories if item.request_id == "structured")

        self.assertEqual("project office", structured_memory.fact_subject)
        self.assertEqual("located at", structured_memory.fact_relation)
        self.assertEqual("Harbor Tower", structured_memory.fact_object)
        self.assertNotEqual(legacy_memory.id, structured_memory.id)

    def test_partial_or_blank_fact_triples_fail_closed(self):
        store = MemoryStore(self.database, embedder=False)
        invalid = (
            {"fact_subject": "office"},
            {"fact_subject": "office", "fact_relation": "located at", "fact_object": ""},
        )
        for index, fields in enumerate(invalid):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                store.add(
                    f"invalid-{index}", "user", "session",
                    [{"role": "user", "content": "fact", **fields}],
                )

    def test_legacy_database_is_migrated_and_backfilled(self):
        connection = sqlite3.connect(self.database)
        try:
            connection.execute(
                """
                CREATE TABLE memories (
                    id TEXT PRIMARY KEY, request_id TEXT NOT NULL, user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
                    timestamp_ms INTEGER, created_at TEXT NOT NULL, terms TEXT NOT NULL,
                    embedding BLOB
                )
                """
            )
            connection.execute(
                """
                INSERT INTO memories VALUES
                ('m1', 'r1', 'u1', 's1', 'user', 'user: legacy', 1704067200000,
                 '2024-01-01T00:00:00Z', 'user legacy', NULL)
                """
            )
            connection.commit()
        finally:
            connection.close()
        store = MemoryStore(self.database, embedder=False)
        memory = store._load_user_memories("u1")[0]
        self.assertEqual(1704067200000, memory.observed_at_ms)
        self.assertIsNone(memory.valid_from_ms)
        self.assertIsNone(memory.valid_to_ms)
        self.assertIsNone(memory.retracted_at_ms)

    def test_invalid_intervals_and_conflicting_aliases_fail(self):
        invalid = (
            {"timestamp": 10, "observed_at": 11},
            {"valid_from": 20, "valid_to": 19},
            {"observed_at": 20, "retracted_at": 19},
            {"observed_at": True},
        )
        for message in invalid:
            with self.subTest(message=message), self.assertRaises(ValueError):
                temporal_state(message)

    def add_state(self, store, request_id, content, **temporal):
        store.add(
            request_id, "user", request_id,
            [{"role": "user", "content": content, **temporal}],
        )

    def test_validity_states_use_half_open_windows_and_retraction(self):
        store = MemoryStore(self.database, embedder=False)
        self.add_state(
            store, "state", "Office state.",
            observed_at=10, valid_from=20, valid_to=40, retracted_at=35,
        )
        memory = store._load_user_memories("user")[0]
        self.assertEqual("unknown", temporal_validity(memory, None))
        self.assertEqual("not_yet_valid", temporal_validity(memory, 19))
        self.assertEqual("valid", temporal_validity(memory, 20))
        self.assertEqual("retracted", temporal_validity(memory, 35))
        self.assertEqual("retracted", temporal_validity(memory, 40))

    def test_query_time_switches_historical_and_current_valid_fact(self):
        store = MemoryStore(self.database, embedder=False)
        self.add_state(
            store, "old", "The project office is Harbor Tower.",
            observed_at=10, valid_from=10, valid_to=30,
        )
        self.add_state(
            store, "new", "The project office is Cedar House.",
            observed_at=20, valid_from=30,
        )
        old_result = store.search(
            "user", "Where is the project office?", 2, query_at_ms=25
        )
        new_result = store.search(
            "user", "Where is the project office?", 2, query_at_ms=35
        )
        self.assertIn("Harbor Tower", old_result[0]["content"])
        self.assertIn("Cedar House", new_result[0]["content"])
        self.assertEqual(2, len(old_result))
        self.assertEqual(2, len(new_result))

    def test_future_expired_and_retracted_evidence_remain_but_do_not_lead(self):
        store = MemoryStore(self.database, embedder=False)
        self.add_state(
            store, "active", "The studio access code is active-code.",
            valid_from=100, valid_to=300,
        )
        self.add_state(
            store, "future", "The studio access code is future-code.",
            valid_from=300,
        )
        self.add_state(
            store, "expired", "The studio access code is expired-code.",
            valid_to=100,
        )
        self.add_state(
            store, "retracted", "The studio access code is retracted-code.",
            retracted_at=150,
        )
        results = store.search(
            "user", "What is the studio access code?", 4, query_at_ms=200
        )
        self.assertIn("active-code", results[0]["content"])
        self.assertEqual(4, len(results))
        combined = "\n".join(result["content"] for result in results)
        self.assertIn("future-code", combined)
        self.assertIn("expired-code", combined)
        self.assertIn("retracted-code", combined)

    def test_missing_query_or_validity_metadata_preserves_prior_order(self):
        store = MemoryStore(self.database, embedder=False)
        self.add_state(store, "first", "The archive office is North Hall.", observed_at=10)
        self.add_state(store, "second", "The archive office is South Hall.", observed_at=20)
        without_query_time = store.search("user", "Where is the archive office?", 2)
        with_query_time = store.search(
            "user", "Where is the archive office?", 2, query_at_ms=100
        )
        self.assertEqual(
            [item["id"] for item in without_query_time],
            [item["id"] for item in with_query_time],
        )

    def test_temporal_ablation_ignores_explicit_validity(self):
        store = MemoryStore(
            self.database, embedder=False,
            retrieval_config=RetrievalConfig(temporal_enabled=False),
        )
        self.add_state(store, "a", "The lab office is Alpha Wing.", valid_from=10)
        self.add_state(store, "b", "The lab office is Beta Wing.", valid_from=100)
        early = store.search("user", "Where is the lab office?", 2, query_at_ms=50)
        late = store.search("user", "Where is the lab office?", 2, query_at_ms=150)
        self.assertEqual([item["id"] for item in early], [item["id"] for item in late])


if __name__ == "__main__":
    unittest.main()
