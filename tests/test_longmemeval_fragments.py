import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.store import MemoryStore
from benchmarks.analyze_longmemeval_fragments import analyze_case, contains_literal, eligible_literal


class LongMemEvalFragmentTests(unittest.TestCase):
    def test_literal_boundaries_and_eligibility(self):
        self.assertTrue(contains_literal("We met in The Suburbs.", "the suburbs"))
        self.assertFalse(contains_literal("We met in suburban Seattle.", "suburb"))
        self.assertFalse(eligible_literal("4"))
        self.assertTrue(eligible_literal("Kyoto"))

    def test_source_can_be_returned_without_literal_answer_snippet(self):
        case = {
            "case_id": "fixture", "question": "Where was the festival?",
            "reference_answers": ["Kyoto"], "evidence_memory_ids": ["required"],
            "capabilities": ["single-session-user"],
            "memories": [{
                "memory_id": "required", "timestamp": 1_700_000_000_000,
                "turns": [
                    {"role": "user", "content": "The festival was in Osaka."},
                    {"role": "assistant", "content": "Correction: it was in Kyoto."},
                ],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "test.db", embedder=False)
            def source_only(*, user_id, **_kwargs):
                with store._connection() as connection:
                    memory_id = connection.execute(
                        "SELECT id FROM memories WHERE user_id = ? LIMIT 1", (user_id,)
                    ).fetchone()["id"]
                return [{"id": memory_id, "content": "The festival was in Osaka."}]

            with patch.object(store, "search", side_effect=source_only):
                row = analyze_case(store, case, top_k=1)
        self.assertTrue(row["required_source_complete"])
        self.assertTrue(row["literal_in_required_source"])
        self.assertFalse(row["literal_in_required_source_snippet"])


if __name__ == "__main__":
    unittest.main()
