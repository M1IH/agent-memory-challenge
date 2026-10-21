import unittest

from benchmarks.probe_clbench_schema_memory import CARDS, question_query, score_dependencies


class CLBenchSchemaMemoryTests(unittest.TestCase):
    def test_scoring_respects_top_k_and_multiple_dependencies(self):
        result = score_dependencies(["SCHEMA_MAP", "PRICE_FMT"], ["PRICE_FMT", "GROUP_ID", "SCHEMA_MAP"], 2)
        self.assertEqual(0.5, result["recall"])
        self.assertFalse(result["complete"])
        self.assertTrue(score_dependencies(["SCHEMA_MAP", "PRICE_FMT"], ["PRICE_FMT", "SCHEMA_MAP"], 2)["complete"])

    def test_unknown_dependency_is_rejected(self):
        self.assertGreaterEqual(len(CARDS), 10)
        with self.assertRaisesRegex(ValueError, "unknown"):
            score_dependencies(["FUTURE_LABEL"], ["SCHEMA_MAP"], 5)

    def test_query_never_includes_reference_answer_or_sql(self):
        case = {"question": "What is the current price?", "answer": "SECRET_ANSWER", "sql": "SECRET_SQL"}
        self.assertEqual(case["question"], question_query(case, "pre_migration", True))
        post = question_query(case, "post_migration", True)
        self.assertIn("schema migration", post)
        self.assertNotIn("SECRET_ANSWER", post)
        self.assertNotIn("SECRET_SQL", post)


if __name__ == "__main__":
    unittest.main()
