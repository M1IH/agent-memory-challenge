import tempfile
import unittest
from pathlib import Path

from app.store import MemoryStore
from benchmarks.run_public_retrieval import run_case


class PublicRetrievalRunnerTests(unittest.TestCase):
    def test_replays_original_turns_and_scores_source_sessions(self):
        case = {
            "case_id": "fixture:1",
            "question": "Which city has the lantern festival?",
            "evidence_memory_ids": ["answer-session"],
            "memories": [
                {
                    "memory_id": "noise-session",
                    "timestamp": 1_700_000_000_000,
                    "turns": [{"role": "user", "content": "I bought a blue umbrella."}],
                },
                {
                    "memory_id": "answer-session",
                    "timestamp": 1_700_000_100_000,
                    "turns": [
                        {"role": "user", "content": "Kyoto has the lantern festival."},
                        {"role": "assistant", "content": "The festival is in Kyoto."},
                    ],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            store = MemoryStore(Path(temp_dir) / "fixture.db", embedder=False)
            metrics, ranked_sources = run_case(store, case, top_k=10)
        self.assertIn("answer-session", ranked_sources)
        self.assertEqual(1.0, metrics["hit_at_10"])
        self.assertEqual(1.0, metrics["complete_at_10"])


if __name__ == "__main__":
    unittest.main()
