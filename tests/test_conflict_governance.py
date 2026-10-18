import tempfile
import unittest
from pathlib import Path

from app.store import MemoryStore, RetrievalConfig


class ConflictGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temporary.cleanup()

    def store(self, name="conflict.db", *, enabled=True):
        return MemoryStore(
            Path(self.temporary.name) / name,
            embedder=False,
            retrieval_config=RetrievalConfig(conflict_enabled=enabled),
        )

    @staticmethod
    def add_fact(store, request_id, object_value, observed_at, **temporal):
        store.add(
            request_id,
            "user",
            request_id,
            [{
                "role": "user",
                "content": f"The project office is {object_value}.",
                "observed_at": observed_at,
                "fact_subject": "project office",
                "fact_relation": "located at",
                "fact_object": object_value,
                **temporal,
            }],
        )

    def test_current_historical_and_comparison_intents_switch_one_conflict_chain(self):
        store = self.store()
        self.add_fact(store, "old", "Harbor Tower", 10)
        self.add_fact(store, "new", "Cedar House", 20)

        current = store.search("user", "Where is the project office currently?", 2)
        historical = store.search("user", "Where was the project office originally?", 2)
        comparison = store.search(
            "user", "Where is the project office now compared with originally?", 2
        )

        self.assertIn("Cedar House", current[0]["content"])
        self.assertIn("Harbor Tower", historical[0]["content"])
        self.assertIn("Cedar House", comparison[0]["content"])
        self.assertEqual(2, len(comparison))
        self.assertIn("Harbor Tower", comparison[1]["content"])

    def test_query_time_uses_valid_member_and_preserves_the_history_chain(self):
        store = self.store("validity.db")
        self.add_fact(store, "old", "Harbor Tower", 10, valid_from=10, valid_to=30)
        self.add_fact(store, "new", "Cedar House", 20, valid_from=30)

        result = store.search(
            "user", "Where was the project office originally?", 2, query_at_ms=25
        )

        self.assertIn("Harbor Tower", result[0]["content"])
        self.assertEqual(2, len(result))
        self.assertIn("Cedar House", result[1]["content"])

    def test_unrelated_conflict_group_gets_no_bonus(self):
        store = self.store("unrelated.db")
        self.add_fact(store, "old", "Harbor Tower", 10)
        self.add_fact(store, "new", "Cedar House", 20)
        store.add(
            "locker", "user", "locker",
            [{"role": "user", "content": "The current locker code is ZX-19."}],
        )

        result = store.search("user", "What is the current locker code?", 1)
        self.assertIn("ZX-19", result[0]["content"])

    def test_conflict_ablation_removes_intent_switch_but_keeps_all_evidence(self):
        enabled = self.store("enabled.db", enabled=True)
        disabled = self.store("disabled.db", enabled=False)
        for store in (enabled, disabled):
            self.add_fact(store, "old", "Harbor Tower", 10)
            self.add_fact(store, "new", "Cedar House", 20)

        active_current = enabled.search(
            "user", "Where is the project office currently?", 2
        )
        active_historical = enabled.search(
            "user", "Where was the project office originally?", 2
        )
        ablated_current = disabled.search(
            "user", "Where is the project office currently?", 2
        )
        ablated_historical = disabled.search(
            "user", "Where was the project office originally?", 2
        )

        self.assertNotEqual(active_current[0]["id"], active_historical[0]["id"])
        self.assertEqual(
            [item["id"] for item in ablated_current],
            [item["id"] for item in ablated_historical],
        )
        self.assertEqual(2, len(active_current))
        self.assertEqual(2, len(active_historical))


if __name__ == "__main__":
    unittest.main()
