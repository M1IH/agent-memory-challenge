import unittest

from benchmarks.probe_session_round_robin import complete_rank, literal_rank, session_cap_two, session_round_robin


class SessionRoundRobinTests(unittest.TestCase):
    def test_preserves_all_results_and_round_robins_sources(self):
        results = [{"id": str(i), "content": str(i)} for i in range(6)]
        sources = ["a", "a", "b", "a", "c", "b"]
        reranked, reranked_sources = session_round_robin(results, sources)
        self.assertEqual(["0", "2", "4", "1", "5", "3"], [item["id"] for item in reranked])
        self.assertEqual(["a", "b", "c", "a", "b", "a"], reranked_sources)
        self.assertEqual({item["id"] for item in results}, {item["id"] for item in reranked})

    def test_source_gain_can_hide_answer_bearing_second_snippet(self):
        results = [
            {"content": "festival Osaka"}, {"content": "festival Kyoto"},
            {"content": "unrelated"}, {"content": "unrelated"},
        ]
        sources = ["a", "a", "b", "c"]
        reranked, reranked_sources = session_round_robin(results, sources)
        self.assertEqual(4, complete_rank({"a", "b", "c"}, sources))
        self.assertEqual(3, complete_rank({"a", "b", "c"}, reranked_sources))
        self.assertEqual(2, literal_rank({"a"}, ["Kyoto"], results, sources))
        self.assertEqual(4, literal_rank({"a"}, ["Kyoto"], reranked, reranked_sources))

    def test_cap_two_preserves_second_hit_before_deferring_third(self):
        results = [{"id": str(i), "content": str(i)} for i in range(7)]
        sources = ["a", "a", "a", "b", "b", "b", "c"]
        reranked, reranked_sources = session_cap_two(results, sources)
        self.assertEqual(["0", "1", "3", "4", "6", "2", "5"], [item["id"] for item in reranked])
        self.assertEqual(["a", "a", "b", "b", "c", "a", "b"], reranked_sources)


if __name__ == "__main__":
    unittest.main()
