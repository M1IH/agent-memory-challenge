import argparse
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.extended_cases import build_extended_cases
from benchmarks.run_benchmark import evaluation_code_manifest, git_evidence, main, positive_int
from benchmarks.evidence import complete_at, source_ranks, validate_source_case


class ExtendedBenchmarkTests(unittest.TestCase):
    def test_git_evidence_binds_production_and_harness_commits(self):
        root = Path(__file__).resolve().parents[1]
        evidence = git_evidence(root, "A" * 40)
        self.assertEqual("a" * 40, evidence["production_git_sha"])
        self.assertEqual(40, len(evidence["harness_git_sha"]))
        self.assertIsInstance(evidence["dirty"], bool)

    def test_git_evidence_rejects_ambiguous_production_ref(self):
        root = Path(__file__).resolve().parents[1]
        with self.assertRaisesRegex(ValueError, "40 hexadecimal"):
            git_evidence(root, "main")

    def test_blind7_is_frozen_disjoint_strict_and_high_distractor(self):
        root = Path(__file__).resolve().parents[1] / "benchmarks"
        blind7 = json.loads((root / "blind7_cases.json").read_text(encoding="utf-8"))
        canonical_hash = hashlib.sha256(
            json.dumps(blind7, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        self.assertEqual(
            "5bb3ca36972e0f975773f63eac6d710188dd1282b8701557746454063aac8079",
            canonical_hash,
            "blind7 changed; preserve the first-run confirmation set",
        )
        prior_names = set()
        prior_queries = set()
        prior_memories = set()
        for filename in (
            "hard_cases.json", "confirmation_cases.json", "holdout_cases.json",
            "blind2_cases.json", "blind3_cases.json", "blind4_cases.json",
            "blind5_cases.json", "blind6_cases.json",
        ):
            cases = json.loads((root / filename).read_text(encoding="utf-8"))
            prior_names.update(case["name"] for case in cases)
            prior_queries.update(case["query"].strip().casefold() for case in cases)
            prior_memories.update(
                memory["content"].strip().casefold()
                for case in cases for memory in case["memories"]
            )
        self.assertEqual(6, len(blind7))
        self.assertFalse({case["name"] for case in blind7} & prior_names)
        self.assertFalse(
            {case["query"].strip().casefold() for case in blind7} & prior_queries
        )
        self.assertFalse(
            {
                memory["content"].strip().casefold()
                for case in blind7 for memory in case["memories"]
            } & prior_memories
        )
        for case in blind7:
            validate_source_case(case)
            self.assertGreaterEqual(
                len(case["memories"]) - len(case["expected_source_ids"]), 15
            )

    def test_blind6_is_frozen_disjoint_strict_and_high_distractor(self):
        root = Path(__file__).resolve().parents[1] / "benchmarks"
        blind6 = json.loads((root / "blind6_cases.json").read_text(encoding="utf-8"))
        canonical_hash = hashlib.sha256(
            json.dumps(blind6, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        self.assertEqual(
            "0ee79ec5f5f037f0c6bc85a4de6ec1ce6a103de10395195797b9ddd25fa0efcc",
            canonical_hash,
            "blind6 changed; preserve the first-run confirmation set",
        )
        prior_names = set()
        prior_queries = set()
        prior_memories = set()
        for filename in (
            "hard_cases.json", "confirmation_cases.json", "holdout_cases.json",
            "blind2_cases.json", "blind3_cases.json", "blind4_cases.json",
            "blind5_cases.json",
        ):
            cases = json.loads((root / filename).read_text(encoding="utf-8"))
            prior_names.update(case["name"] for case in cases)
            prior_queries.update(case["query"].strip().casefold() for case in cases)
            prior_memories.update(
                memory["content"].strip().casefold()
                for case in cases for memory in case["memories"]
            )
        self.assertEqual(6, len(blind6))
        self.assertFalse({case["name"] for case in blind6} & prior_names)
        self.assertFalse(
            {case["query"].strip().casefold() for case in blind6} & prior_queries
        )
        self.assertFalse(
            {
                memory["content"].strip().casefold()
                for case in blind6 for memory in case["memories"]
            } & prior_memories
        )
        for case in blind6:
            validate_source_case(case)
            self.assertGreaterEqual(
                len(case["memories"]) - len(case["expected_source_ids"]), 15
            )

    def test_blind5_is_frozen_disjoint_strict_and_high_distractor(self):
        root = Path(__file__).resolve().parents[1] / "benchmarks"
        blind5 = json.loads((root / "blind5_cases.json").read_text(encoding="utf-8"))
        canonical_hash = hashlib.sha256(
            json.dumps(blind5, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        self.assertEqual(
            "687187f181d17b030d9cb8b05bfd4e18f7f0c4e4ed25a379518bb7988ee8d60f",
            canonical_hash,
            "blind5 changed; create a development copy instead of tuning it in place",
        )
        for report_name in (
            "blind5-baseline-bge.json",
            "blind5-baseline-lexical.json",
            "blind5-candidate-bge.json",
            "blind5-candidate-lexical.json",
            "blind5-development-temporal-linkage.json",
        ):
            report = json.loads((root / report_name).read_text(encoding="utf-8"))
            self.assertEqual(canonical_hash, report["suite_sha256"])
        known_names = set()
        for filename in (
            "hard_cases.json", "confirmation_cases.json", "holdout_cases.json",
            "blind2_cases.json", "blind3_cases.json", "blind4_cases.json",
        ):
            known_names.update(
                case["name"]
                for case in json.loads((root / filename).read_text(encoding="utf-8"))
            )
        self.assertEqual(6, len(blind5))
        self.assertFalse({case["name"] for case in blind5} & known_names)
        self.assertEqual(len(blind5), len({case["name"] for case in blind5}))
        for case in blind5:
            validate_source_case(case)
            self.assertGreaterEqual(
                len(case["memories"]) - len(case["expected_source_ids"]), 15
            )

    def test_blind4_is_frozen_disjoint_strict_and_high_distractor(self):
        root = Path(__file__).resolve().parents[1] / "benchmarks"
        blind4 = json.loads((root / "blind4_cases.json").read_text(encoding="utf-8"))
        canonical_hash = hashlib.sha256(
            json.dumps(blind4, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        self.assertEqual(
            "76a1c23f4aa99fe4d794ca935acacde1da69f48db9bba109407eb958101e3918",
            canonical_hash,
            "blind4 changed; create a development copy instead of tuning it in place",
        )
        baseline = json.loads((root / "blind4-baseline.json").read_text(encoding="utf-8"))
        lexical = json.loads((root / "blind4-lexical.json").read_text(encoding="utf-8"))
        self.assertEqual(canonical_hash, baseline["suite_sha256"])
        self.assertEqual(canonical_hash, lexical["suite_sha256"])
        known_names = set()
        for filename in (
            "hard_cases.json", "confirmation_cases.json", "holdout_cases.json",
            "blind2_cases.json", "blind3_cases.json",
        ):
            known_names.update(
                case["name"]
                for case in json.loads((root / filename).read_text(encoding="utf-8"))
            )
        self.assertEqual(6, len(blind4))
        self.assertFalse({case["name"] for case in blind4} & known_names)
        self.assertEqual(len(blind4), len({case["name"] for case in blind4}))
        for case in blind4:
            validate_source_case(case)
            self.assertGreaterEqual(
                len(case["memories"]) - len(case["expected_source_ids"]), 15
            )

    def test_blind3_is_frozen_disjoint_strict_and_high_distractor(self):
        root = Path(__file__).resolve().parents[1] / "benchmarks"
        blind3 = json.loads((root / "blind3_cases.json").read_text(encoding="utf-8"))
        canonical_hash = hashlib.sha256(
            json.dumps(blind3, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        self.assertEqual(
            "b3b0d7f798d45ebe344b7adaada946b2fc2385b79f696ee09c0cefa56ad16840",
            canonical_hash,
            "blind3 changed; create a development copy instead of tuning it in place",
        )
        baseline = json.loads((root / "blind3-baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(canonical_hash, baseline["suite_sha256"])
        known_names = set()
        for filename in (
            "hard_cases.json", "confirmation_cases.json", "holdout_cases.json",
            "blind2_cases.json",
        ):
            known_names.update(
                case["name"]
                for case in json.loads((root / filename).read_text(encoding="utf-8"))
            )
        self.assertEqual(6, len(blind3))
        self.assertFalse({case["name"] for case in blind3} & known_names)
        self.assertEqual(len(blind3), len({case["name"] for case in blind3}))
        for case in blind3:
            validate_source_case(case)
            self.assertGreaterEqual(
                len(case["memories"]) - len(case["expected_source_ids"]), 15
            )

    def test_blind2_is_frozen_disjoint_strict_and_high_distractor(self):
        root = Path(__file__).resolve().parents[1] / "benchmarks"
        blind2 = json.loads((root / "blind2_cases.json").read_text(encoding="utf-8"))
        canonical_hash = hashlib.sha256(
            json.dumps(blind2, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        self.assertEqual(
            "239f934b2769154c094f067cfadd47bff3ea0275631beceee16978dc14ac6386",
            canonical_hash,
            "blind2 changed; create a development copy instead of tuning it in place",
        )
        baseline = json.loads((root / "blind2-baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(canonical_hash, baseline["suite_sha256"])
        known_names = set()
        for filename in ("hard_cases.json", "confirmation_cases.json", "holdout_cases.json"):
            known_names.update(
                case["name"]
                for case in json.loads((root / filename).read_text(encoding="utf-8"))
            )
        self.assertEqual(6, len(blind2))
        self.assertFalse({case["name"] for case in blind2} & known_names)
        self.assertEqual(len(blind2), len({case["name"] for case in blind2}))
        for case in blind2:
            validate_source_case(case)
            self.assertGreaterEqual(
                len(case["memories"]) - len(case["expected_source_ids"]), 15
            )

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
