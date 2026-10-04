import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.public_eval_schema import CaseValidationError, load_suite, validate_case


def valid_case():
    return {
        "case_id": "dataset:record-1",
        "dataset": "Example Dataset",
        "dataset_version": "immutable-revision",
        "source_record_id": "record-1",
        "license": "Example-License",
        "split": "development",
        "language": "en",
        "capabilities": ["temporal", "conflict"],
        "memories": [
            {"memory_id": "m1", "role": "user", "timestamp": 10, "content": "Old office: A."},
            {"memory_id": "m2", "role": "user", "timestamp": 20, "content": "Current office: B."},
        ],
        "question": "Where is the current office?",
        "query_time": 30,
        "evidence_memory_ids": ["m2"],
        "reference_answers": ["B"],
        "scorer": "exact_match",
    }


class PublicEvalSchemaTests(unittest.TestCase):
    def test_valid_case_accepts_provenance_and_temporal_fields(self):
        validate_case(valid_case())

    def test_unknown_evidence_is_rejected(self):
        case = valid_case()
        case["evidence_memory_ids"] = ["missing"]
        with self.assertRaisesRegex(CaseValidationError, "known memory IDs"):
            validate_case(case)

    def test_multiple_choice_requires_reference_choice(self):
        case = valid_case()
        case.update({"scorer": "multiple_choice", "choices": ["A", "C"]})
        with self.assertRaisesRegex(CaseValidationError, "match a choice"):
            validate_case(case)

    def test_frozen_split_name_is_explicit(self):
        case = valid_case()
        case["split"] = "test"
        with self.assertRaisesRegex(CaseValidationError, "frozen_holdout"):
            validate_case(case)

    def test_load_suite_validates_unique_ids_and_records_file_hash(self):
        document = {"schema_version": 1, "cases": [valid_case()]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "suite.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            loaded = load_suite(path)
        self.assertEqual(64, len(loaded["file_sha256"]))

    def test_duplicate_case_ids_are_rejected(self):
        document = {"schema_version": 1, "cases": [valid_case(), valid_case()]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "suite.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(CaseValidationError, "case_id"):
                load_suite(path)


if __name__ == "__main__":
    unittest.main()

