import unittest

from benchmarks.extended_cases import build_extended_cases


class ExtendedBenchmarkTests(unittest.TestCase):
    def test_extended_suite_has_100_unique_well_formed_cases(self):
        cases = build_extended_cases()
        self.assertEqual(100, len(cases))
        self.assertEqual(100, len({case["name"] for case in cases}))
        for case in cases:
            self.assertTrue(case["category"])
            self.assertTrue(case["query"])
            self.assertGreaterEqual(len(case["memories"]), 2)
            self.assertTrue(case.get("expected") or case.get("expected_all"))


if __name__ == "__main__":
    unittest.main()
