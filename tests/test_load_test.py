import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.run_load_test import (
    current_rss_bytes,
    latency_summary,
    main,
    mixed_schedule,
    nonnegative_int,
    percentile,
    positive_int,
)


class LoadTestTests(unittest.TestCase):
    def test_current_rss_is_positive_when_supported(self):
        rss = current_rss_bytes()
        self.assertTrue(rss is None or rss > 0)

    def test_mixed_schedule_spreads_operations_across_submission_order(self):
        schedule = mixed_schedule(2, 6)

        self.assertEqual(2, schedule.count("add"))
        self.assertEqual(6, schedule.count("search"))
        self.assertEqual(["search", "search", "search", "add"], schedule[:4])
        self.assertEqual(["search", "search", "search", "add"], schedule[4:])
        self.assertEqual([], mixed_schedule(0, 0))

    def test_positive_int_and_percentile_validation(self):
        self.assertEqual(3, positive_int("3"))
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_int("0")
        self.assertEqual(0, nonnegative_int("0"))
        with self.assertRaises(argparse.ArgumentTypeError):
            nonnegative_int("-1")
        with self.assertRaises(ValueError):
            percentile([], 0.5)
        with self.assertRaises(ValueError):
            percentile([1.0], 1.1)
        self.assertEqual(1.0, percentile([1.0, 2.0, 3.0, 4.0], 0.25))
        self.assertEqual(4.0, percentile([1.0, 2.0, 3.0, 4.0], 0.95))

    def test_latency_summary_has_required_percentiles(self):
        summary = latency_summary([1.0, 2.0, 3.0, 4.0])
        self.assertEqual({"mean_seconds", "p50_seconds", "p95_seconds", "p99_seconds"}, set(summary))
        self.assertEqual(2.5, summary["mean_seconds"])

    def test_small_no_embedding_run_writes_machine_readable_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "load.json"
            argv = [
                "load-test",
                "--add-requests", "2",
                "--messages-per-request", "2",
                "--search-requests", "2",
                "--add-workers", "2",
                "--search-workers", "2",
                "--mixed-add-requests", "1",
                "--mixed-search-requests", "2",
                "--top-k", "4",
                "--no-embeddings",
                "--json-output", str(output),
            ]
            with patch("sys.argv", argv):
                main()
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(4, report["config"]["memory_count"])
        self.assertEqual(4, report["config"]["preloaded_memory_count"])
        self.assertEqual(6, report["config"]["expected_final_memory_count"])
        self.assertEqual(
            "proportional_interleave", report["config"]["mixed_submission_order"]
        )
        self.assertFalse(report["config"]["embeddings_enabled"])
        self.assertIsNone(report["config"]["embedding_batch_size"])
        self.assertEqual(0, report["config"]["memory_cache_users"])
        self.assertEqual(
            64 * 1024 * 1024, report["config"]["memory_cache_max_bytes"]
        )
        self.assertEqual("nearest-rank", report["config"]["percentile_method"])
        self.assertEqual(
            "current_process_resident_set", report["memory"]["measurement"]
        )
        self.assertIn("rss_after_add_bytes", report["memory"])
        self.assertIn("rss_after_search_bytes", report["memory"])
        self.assertIn("rss_search_delta_bytes", report["memory"])
        self.assertEqual(0, report["memory"]["estimated_cached_snapshot_bytes"])
        self.assertEqual(0, report["add"]["errors"])
        self.assertEqual(0, report["search"]["errors"])
        self.assertEqual(1.0, report["search"]["top_1_accuracy"])
        self.assertEqual([], report["search"]["incorrect_searches"])
        self.assertEqual(0, report["mixed"]["add_errors"])
        self.assertEqual(0, report["mixed"]["search_errors"])
        self.assertEqual(2, report["mixed"]["search_top_1_correct"])
        self.assertEqual([], report["mixed"]["incorrect_searches"])
        self.assertEqual(2, report["mixed"]["successful_messages"])
        self.assertGreater(report["mixed"]["add_throughput_messages_per_second"], 0)
        self.assertGreater(report["mixed"]["search_throughput_requests_per_second"], 0)


if __name__ == "__main__":
    unittest.main()
