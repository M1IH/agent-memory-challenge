import unittest

from benchmarks.public_eval_metrics import aggregate_retrieval, score_retrieval


CASE = {
    "memories": [
        {"memory_id": "old"},
        {"memory_id": "bridge"},
        {"memory_id": "answer"},
    ],
    "evidence_memory_ids": ["bridge", "answer"],
}


class PublicEvalMetricsTests(unittest.TestCase):
    def test_two_required_sources_count_partial_then_complete_coverage(self):
        score = score_retrieval(CASE, ["old", "bridge", "answer"])
        self.assertEqual(0.0, score["hit_at_1"])
        self.assertEqual(1.0, score["hit_at_3"])
        self.assertEqual(1.0, score["recall_at_3"])
        self.assertEqual(1.0, score["complete_at_3"])
        self.assertEqual(0.5, score["mrr"])

    def test_duplicate_sources_do_not_inflate_recall(self):
        score = score_retrieval(CASE, ["bridge", "bridge", "old"])
        self.assertEqual(0.5, score["recall_at_3"])
        self.assertEqual(0.0, score["complete_at_100"])

    def test_unknown_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown ranked memory ID"):
            score_retrieval(CASE, ["other-user-memory"])

    def test_macro_average(self):
        full = score_retrieval(CASE, ["bridge", "answer"])
        missing = score_retrieval(CASE, [])
        average = aggregate_retrieval([full, missing])
        self.assertEqual(0.5, average["complete_at_5"])
        self.assertEqual(0.5, average["mrr"])


if __name__ == "__main__":
    unittest.main()
