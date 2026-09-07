import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.store import MemoryStore, RetrievalConfig


class FakeEmbedder:
    """Tiny deterministic encoder used to test fusion without a model download."""

    index_identity = "fake-v1"

    def encode(self, texts):
        vectors = []
        for text in texts:
            lowered = text.lower()
            if "avoid" in lowered or "cilantro" in lowered:
                vectors.append(np.array([1.0, 0.0], dtype=np.float32))
            else:
                vectors.append(np.array([0.0, 1.0], dtype=np.float32))
        return vectors


class WrongCountEmbedder:
    def encode(self, texts):
        return []


class ThreeDimensionalEmbedder:
    index_identity = "fake-v1"

    def encode(self, texts):
        return [np.array([1.0, 0.0, 0.0], dtype=np.float32) for _ in texts]


class AlternateSameDimensionEmbedder:
    index_identity = "alternate-same-dimension-v1"

    def encode(self, texts):
        return [np.array([0.0, 1.0], dtype=np.float32) for _ in texts]


class AdversarialIdentifierEmbedder:
    index_identity = "adversarial-identifier-v1"

    def encode(self, texts):
        vectors = []
        for text in texts:
            lowered = text.lower()
            if lowered.startswith("find ") or "project-code-81-16" in lowered:
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

    def test_completed_event_evidence_survives_hybrid_list_fusion(self):
        memories = [
            "I put the travel adapter in my bag for the Lumen conference.",
            "My Lumen conference badge is packed in the front pocket.",
            "I packed the green notebook for Lumen.",
            "The allergy medicine went into my Lumen conference suitcase.",
            "I planned a tablet for Lumen but left it at home.",
            "The Lumen packing list suggested cards; I did not bring any.",
            "My colleague packed a monitor for Lumen.",
            "The Lumen conference badge has a yellow stripe.",
        ]
        for index, content in enumerate(memories):
            self.store.add(
                f"list-{index}", "alice", "session-1",
                [{"role": "user", "content": content}],
            )
        results = self.store.search(
            "alice", "List every item I actually packed for the Lumen conference.", 4
        )
        contents = "\n".join(result["content"] for result in results)
        for expected in ("adapter", "badge", "notebook", "medicine"):
            self.assertIn(expected, contents)
        self.assertNotIn("colleague", contents)
        self.assertNotIn("did not", contents)

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

    def test_encoder_cannot_silently_drop_messages(self):
        store = MemoryStore(
            Path(self.temp_dir.name) / "wrong-count.db", embedder=WrongCountEmbedder()
        )
        with self.assertRaises(RuntimeError):
            store.add("req", "alice", "session", [{"role": "user", "content": "x"}])

    def test_changed_embedding_dimension_falls_back_to_lexical_search(self):
        self.store.add(
            "req", "alice", "session", [{"role": "user", "content": "unique keyword"}]
        )
        reopened = MemoryStore(
            Path(self.temp_dir.name) / "hybrid.db", embedder=ThreeDimensionalEmbedder()
        )
        results = reopened.search("alice", "unique keyword", 1)
        self.assertEqual(1, len(results))
        self.assertIn("unique keyword", results[0]["content"])

    def test_same_dimension_different_embedding_identity_is_rejected(self):
        self.store.add(
            "req", "alice", "session", [{"role": "user", "content": "unique keyword"}]
        )
        with self.assertRaisesRegex(RuntimeError, "embedding identity"):
            MemoryStore(
                Path(self.temp_dir.name) / "hybrid.db",
                embedder=AlternateSameDimensionEmbedder(),
            )

    def test_legacy_vectors_without_identity_are_rejected(self):
        self.store.add(
            "req", "alice", "session", [{"role": "user", "content": "unique keyword"}]
        )
        with self.store._connection() as connection:
            connection.execute("DELETE FROM store_metadata WHERE key = 'embedding_identity'")
        with self.assertRaisesRegex(RuntimeError, "no verifiable embedding identity"):
            MemoryStore(Path(self.temp_dir.name) / "hybrid.db", embedder=FakeEmbedder())

    def test_empty_index_can_adopt_a_new_embedding_identity(self):
        empty_path = Path(self.temp_dir.name) / "empty.db"
        MemoryStore(empty_path, embedder=FakeEmbedder())
        reopened = MemoryStore(empty_path, embedder=AlternateSameDimensionEmbedder())
        with reopened._connection() as connection:
            identity = connection.execute(
                "SELECT value FROM store_metadata WHERE key = 'embedding_identity'"
            ).fetchone()["value"]
        self.assertEqual("alternate-same-dimension-v1", identity)

    def test_dense_scoring_uses_bounded_matrix_batches(self):
        self.store.add(
            "large-batch",
            "alice",
            "session",
            [
                {"role": "user", "content": f"bounded vector record {index}"}
                for index in range(2050)
            ],
        )

        with patch("app.store.np.vstack", wraps=np.vstack) as stack:
            results = self.store.search("alice", "bounded vector record 2049", 1)

        self.assertEqual(1, len(results))
        self.assertEqual(2, stack.call_count)

    def test_rare_exact_identifier_survives_adversarial_dense_rank(self):
        store = MemoryStore(
            Path(self.temp_dir.name) / "identifier.db",
            embedder=AdversarialIdentifierEmbedder(),
        )
        store.add(
            "target",
            "alice",
            "session",
            [{"role": "user", "content": "Project code project-code-0-16."}],
        )
        for index in range(20):
            code = "project-code-81-16" if index == 19 else f"project-code-{index + 1}-16"
            store.add(
                f"distractor-{index}",
                "alice",
                "session",
                [{"role": "user", "content": f"Project code {code}."}],
            )

        result = store.search("alice", "Find project code project-code-0-16", 1)

        self.assertIn("project-code-0-16", result[0]["content"])

    def test_identifier_guard_does_not_leak_into_dense_only_ablation(self):
        store = MemoryStore(
            Path(self.temp_dir.name) / "identifier-dense-only.db",
            embedder=AdversarialIdentifierEmbedder(),
            retrieval_config=RetrievalConfig(lexical_enabled=False),
        )
        store.add(
            "target",
            "alice",
            "session",
            [{"role": "user", "content": "Project code project-code-0-16."}],
        )
        store.add(
            "dense",
            "alice",
            "session",
            [{"role": "user", "content": "Project code project-code-81-16."}],
        )

        result = store.search("alice", "Find project code project-code-0-16", 1)

        self.assertIn("project-code-81-16", result[0]["content"])

    def test_identifier_guard_does_not_boost_hyphenated_words_without_digits(self):
        store = MemoryStore(
            Path(self.temp_dir.name) / "hyphenated-word.db",
            embedder=AdversarialIdentifierEmbedder(),
        )
        store.add(
            "target",
            "alice",
            "session",
            [{"role": "user", "content": "Project code project-code-alpha-beta."}],
        )
        for index in range(20):
            code = "project-code-81-16" if index == 19 else f"unrelated-code-{index}"
            store.add(
                f"distractor-{index}",
                "alice",
                "session",
                [{"role": "user", "content": f"Project code {code}."}],
            )

        result = store.search(
            "alice", "Find project code project-code-alpha-beta", 1
        )

        self.assertNotIn("project-code-alpha-beta", result[0]["content"])


if __name__ == "__main__":
    unittest.main()
