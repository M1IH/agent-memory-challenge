import argparse
import unittest

from benchmarks.run_fts_probe import fts_expression, positive_int, probe_case


class FtsProbeTests(unittest.TestCase):
    def test_expression_is_deduplicated_and_quoted(self):
        self.assertEqual('"room-101" OR "key"', fts_expression(["room-101", "key", "key"]))
        self.assertEqual("", fts_expression([]))

    def test_positive_candidate_limit(self):
        self.assertEqual(5, positive_int("5"))
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_int("0")

    def test_direct_filter_exposes_zero_overlap_bridge_loss(self):
        report = probe_case(
            {
                "name": "bridge",
                "category": "multi_hop",
                "query": "Who is responsible for Project Juniper's access?",
                "expected_source_ids": ["room", "key"],
                "memories": [
                    {
                        "source_id": "room",
                        "content": "Project Juniper uses the Cedar room.",
                    },
                    {
                        "source_id": "key",
                        "content": "Mei keeps the Cedar room key.",
                    },
                    {"source_id": "noise", "content": "The menu changes weekly."},
                ],
            },
            candidate_limit=10,
        )

        self.assertIn("room", report["covered_source_ids"])
        self.assertIn("key", report["missing_source_ids"])


if __name__ == "__main__":
    unittest.main()
