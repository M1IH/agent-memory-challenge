import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.store import MemoryStore


class FakeEmbedder:
    """Tiny deterministic encoder used to test fusion without a model download."""

    def encode(self, texts):
        vectors = []
        for text in texts:
            lowered = text.lower()
            if "avoid" in lowered or "cilantro" in lowered:
                vectors.append(np.array([1.0, 0.0], dtype=np.float32))
            else:
                vectors.append(np.array([0.0, 1.0], dtype=np.float32))
        return vectors


class HybridRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = MemoryStore(
            Path(self.temp_dir.name) / "hybrid.db",
            embedder=FakeEmbedder(),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dense_channel_recalls_zero_lexical_overlap(self):
        self.store.add(
            request_id="req-1",
            user_id="alice",
            session_id="session-1",
            messages=[
                {
                    "role": "user",
                    "content": "I cannot stand cilantro in any dish.",
                    "timestamp": 1704067200000,
                },
                {
                    "role": "user",
                    "content": "The restaurant serves basil and mint.",
                    "timestamp": 1704153600000,
                },
            ],
        )
        results = self.store.search(
            "alice", "Which ingredient should recommendations avoid?", 10
        )
        self.assertIn("cilantro", results[0]["content"])

    def test_embeddings_are_persisted_in_sqlite(self):
        self.store.add(
            request_id="req-1",
            user_id="alice",
            session_id="session-1",
            messages=[
                {"role": "user", "content": "cilantro", "timestamp": None}
            ],
        )
        with self.store._connection() as connection:
            row = connection.execute(
                "SELECT embedding FROM memories LIMIT 1"
            ).fetchone()
        self.assertIsNotNone(row["embedding"])


if __name__ == "__main__":
    unittest.main()
