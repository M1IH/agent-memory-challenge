import argparse
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.extended_cases import build_extended_cases
from benchmarks.run_benchmark import evaluation_code_manifest, main, positive_int
from benchmarks.evidence import complete_at, source_ranks, validate_source_case


class ExtendedBenchmarkTests(unittest.TestCase):
    def test_holdout_is_disjoint_strict_and_high_distractor(self):
        root = Path(__file__).resolve().parents[1] / "benchmarks"
        holdout = json.loads((root / "holdout_cases.json").read_text(encoding="utf-8"))
        canonical_hash = hashlib.sha256(
            json.dumps(holdout, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        baseline = json.loads(
            (root / "holdout-baseline.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            canonical_hash,
            "9ed70912360b2253c87c767609fdf33520156ed0512169393e082c86468eeeee",
            "holdout changed; create a development copy instead of tuning it in place",
        )
        self.assertEqual(baseline["suite_sha256"], canonical_hash)
        known_names = set()
        for filename in ("hard_cases.json", "confirmation_cases.json"):
            known_names.update(
                case["name"]
                for case in json.loads((root / filename).read_text(encoding="utf-8"))
            )
        self.assertGreaterEqual(len(holdout), 6)
        self.assertFalse({case["name"] for case in holdout} & known_names)
        self.assertEqual(len(holdout), len({case["name"] for case in holdout}))
        for case in holdout:
            validate_source_case(case)
            self.assertGreaterEqual(
                len(case["memories"]) - len(case["expected_source_ids"]), 15
            )

    def test_confirmation_cases_are_separate_strict_high_distractor_cases(self):
        root = Path(__file__).resolve().parents[1] / "benchmarks"
        confirmation = json.loads((root / "confirmation_cases.json").read_text(encoding="utf-8"))
        hard = json.loads((root / "hard_cases.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(confirmation), 6)
        self.assertFalse({case["name"] for case in confirmation} & {case["name"] for case in hard})
        self.assertEqual(len(confirmation), len({case["name"] for case in confirmation}))
        for case in confirmation:
            validate_source_case(case)
            self.assertGreaterEqual(
                len(case["memories"]) - len(case["expected_source_ids"]), 15
            )

    def test_hard_cases_have_known_sources_and_more_than_ten_distractors(self):
        cases = json.loads((Path(__file__).resolve().parents[1] / "benchmarks/hard_cases.json").read_text(encoding="utf-8"))
        self.assertEqual(6, len(cases))
        self.assertEqual(len(cases), len({case["name"] for case in cases}))
        for case in cases:
            validate_source_case(case)
            self.assertGreater(len(case["memories"]) - len(case["expected_source_ids"]), 10)

    def test_source_scoring_does_not_credit_answer_words_in_distractor(self):
        results = [{"id": "wrong", "content": "Thursday"}, {"id": "right", "content": "Thursday"}]
        mapping = {"wrong": "distractor", "right": "schedule"}
        self.assertEqual([2, None], source_ranks(["schedule", "manager"], results, mapping))
        self.assertFalse(complete_at([1, None], 5))
        self.assertFalse(complete_at([1, 6], 5))
        self.assertTrue(complete_at([1, 5], 5))
        self.assertFalse(complete_at([], 5))
        self.assertEqual([None], source_ranks(["schedule"], results[:1], mapping))

    def test_invalid_source_cases_fail_fast(self):
        invalid = [
            {"memories": [{"source_id": "a"}, {"source_id": "a"}], "expected_source_ids": ["a"]},
            {"memories": [{"source_id": "a"}], "expected_source_ids": ["missing"]},
            {"memories": [{"source_id": "a"}], "expected_source_ids": []},
            {"memories": [{"source_id": "a"}], "expected_source_ids": ["a"], "single_add": True},
        ]
        for case in invalid:
            with self.subTest(case=case), self.assertRaises(ValueError):
                validate_source_case(case)

    def test_hard_runner_records_source_traces_and_effective_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            with patch.dict(os.environ, {"AML_EMBED_ENABLED": "false"}):
                with patch("sys.argv", ["benchmark", "--suite", "hard", "--quiet", "--top-k", "1", "--json-output", str(output)]):
                    main()
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertIsNone(report["embedding_model"])
        self.assertEqual(6, len(report["case_traces"]))
        self.assertEqual(64, len(report["suite_sha256"]))
        self.assertEqual(3, report["evaluation_version"])
        self.assertIsNone(report["embedding_identity"])
        self.assertEqual(
            {
                "app/store.py",
                "app/embedding.py",
                "benchmarks/run_benchmark.py",
                "benchmarks/evidence.py",
                "benchmarks/extended_cases.py",
            },
            set(report["evaluation_code"]["files"]),
        )
        self.assertEqual(64, len(report["evaluation_code"]["sha256"]))
        self.assertEqual(1200, report["runtime"]["max_context_chars"])
        self.assertEqual(200000, report["runtime"]["max_add_chars"])
        self.assertEqual(200000, report["runtime"]["max_search_chars"])
        self.assertEqual(report["complete_at_1"], report["complete_at_k"])
        for trace in report["case_traces"]:
            self.assertEqual("source_id", trace["matching"])
            self.assertTrue(all(result["source_id"] for result in trace["results"]))
            self.assertLessEqual(len(trace["results"]), 1)

    def test_top_k_must_be_positive(self):
        self.assertEqual(3, positive_int("3"))
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_int("0")

    def test_evaluation_manifest_changes_when_scoring_code_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative_path in (
                "app/store.py", "app/embedding.py", "benchmarks/run_benchmark.py",
                "benchmarks/evidence.py", "benchmarks/extended_cases.py",
            ):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative_path, encoding="utf-8")
            before = evaluation_code_manifest(root)
            (root / "benchmarks/evidence.py").write_text("changed", encoding="utf-8")
            after = evaluation_code_manifest(root)

        self.assertNotEqual(before["sha256"], after["sha256"])
        self.assertNotEqual(
            before["files"]["benchmarks/evidence.py"],
            after["files"]["benchmarks/evidence.py"],
        )

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
