import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.store import MemoryStore
from benchmarks.run_longmemeval_local_answerer import run_case, select_cases


class LongMemEvalLocalAnswererTests(unittest.TestCase):
    def test_selection_excludes_frozen_holdout(self):
        suite = {"cases": [
            {"case_id": "a", "split": "development", "capabilities": ["temporal"]},
            {"case_id": "b", "split": "frozen_holdout", "capabilities": ["temporal"]},
            {"case_id": "c", "split": "development", "capabilities": ["temporal"]},
            {"case_id": "d", "split": "development", "capabilities": ["multi"]},
        ]}
        self.assertEqual(["a", "d"], [case["case_id"] for case in select_cases(suite, 1)])
        self.assertEqual(["a"], [case["case_id"] for case in select_cases(suite, 1, "temporal")])

    def test_replays_history_and_reports_evidence_source(self):
        case = {
            "case_id": "fixture", "question": "Where is the festival?",
            "scorer": "exact_match", "reference_answers": ["Kyoto"],
            "evidence_memory_ids": ["source"], "capabilities": ["single"],
            "memories": [{
                "memory_id": "source", "timestamp": 1_700_000_000_000,
                "turns": [{"role": "user", "content": "The festival is in Kyoto."}],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "test.db", embedder=False)
            with patch("benchmarks.run_longmemeval_local_answerer.ask", side_effect=[("Unknown", 0.1), ("Kyoto", 0.2)]) as ask:
                result = run_case(store, case, 5)
        self.assertFalse(result["without_exact"])
        self.assertTrue(result["with_exact"])
        self.assertTrue(result["evidence_source_complete"])
        self.assertEqual(2, ask.call_count)
        self.assertIn("festival", ask.call_args_list[1].args[1][0])


if __name__ == "__main__":
    unittest.main()
