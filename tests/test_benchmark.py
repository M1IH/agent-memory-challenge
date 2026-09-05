import argparse
import unittest

from benchmarks.extended_cases import build_extended_cases
from benchmarks.run_benchmark import positive_int


class ExtendedBenchmarkTests(unittest.TestCase):
    def test_top_k_must_be_positive(self):
        self.assertEqual(3, positive_int("3"))
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_int("0")

    def test_extended_suite_has_110_unique_well_formed_cases(self):
        cases = build_extended_cases()
        self.assertEqual(110, len(cases))
        self.assertEqual(110, len({case["name"] for case in cases}))
        for case in cases:
            self.assertTrue(case["category"])
            self.assertTrue(case["query"])
            self.assertGreaterEqual(len(case["memories"]), 2)
            self.assertTrue(case.get("expected") or case.get("expected_all"))


if __name__ == "__main__":
    unittest.main()
