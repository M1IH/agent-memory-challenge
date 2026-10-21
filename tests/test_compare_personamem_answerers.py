import unittest

from benchmarks.compare_personamem_answerers import compare


def report(correct, answer="(b)"):
    return {
        "suite_sha256": "suite-hash",
        "model_digest": "model-hash",
        "system_prompt_sha256": "prompt-hash",
        "options": {"temperature": 0},
        "top_k": 5,
        "selection": "first-1-source-order",
        "rows": [{
            "case_id": "personamem:1",
            "capability": "preference",
            "no_memory_answer": "(a)",
            "with_memory_answer": answer,
            "with_memory_correct": correct,
        }],
    }


class PairedComparisonTests(unittest.TestCase):
    def setUp(self):
        self.suite = {
            "file_sha256": "suite-hash",
            "cases": [{"case_id": "personamem:1", "reference_answers": ["(b) correct"], "scorer": "multiple_choice"}],
        }

    def test_improvement_is_paired_and_parsed_separately(self):
        result = compare(report(False, "(a)"), report(True, "(b) correct"), self.suite)
        self.assertEqual(1, result["improved"])
        self.assertEqual(0, result["regressed"])
        self.assertEqual(1, result["candidate_parsed_correct"])

    def test_model_mismatch_rejected(self):
        candidate = report(True)
        candidate["model_digest"] = "different-model"
        with self.assertRaisesRegex(ValueError, "model_digest"):
            compare(report(False), candidate, self.suite)


if __name__ == "__main__":
    unittest.main()
