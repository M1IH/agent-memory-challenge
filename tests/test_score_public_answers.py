import tempfile
import unittest
from pathlib import Path

from benchmarks.score_public_answers import load_predictions, score_answer, score_suite


def case(case_id, *, split="development", scorer="multiple_choice"):
    return {
        "case_id": case_id,
        "split": split,
        "scorer": scorer,
        "reference_answers": ["(b) Folk music" if scorer == "multiple_choice" else "Folk music"],
        "capabilities": ["preference"],
    }


class PublicAnswerScoringTests(unittest.TestCase):
    def test_multiple_choice_accepts_exact_label_or_full_choice_only(self):
        item = case("a")
        self.assertTrue(score_answer(item, "(b)"))
        self.assertTrue(score_answer(item, " (b) folk music "))
        self.assertFalse(score_answer(item, "b"))
        self.assertFalse(score_answer(item, "(a)"))
        self.assertFalse(score_answer(item, "The answer is (b)"))

    def test_exact_match_is_explicit_proxy(self):
        item = case("a", scorer="exact_match")
        self.assertTrue(score_answer(item, "  FOLK   MUSIC "))
        self.assertFalse(score_answer(item, "Folk"))

    def test_missing_or_extra_prediction_fails(self):
        suite = {"cases": [case("a"), case("b"), case("h", split="frozen_holdout")]}
        with self.assertRaisesRegex(ValueError, "missing=1 extra=1"):
            score_suite(suite, {"a": "(b)", "h": "(b)"})

    def test_aggregate_uses_only_selected_split(self):
        suite = {"cases": [case("a"), case("b"), case("h", split="frozen_holdout")]}
        result = score_suite(suite, {"a": "(b)", "b": "(a)"})
        self.assertEqual(2, result["case_count"])
        self.assertEqual(0.5, result["accuracy"])
        self.assertEqual(2, result["by_capability"]["preference"]["case_count"])

    def test_prediction_file_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.jsonl"
            path.write_text('{"case_id":"a","answer":"(b)"}\n{"case_id":"a","answer":"(b)"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate prediction"):
                load_predictions(path)


if __name__ == "__main__":
    unittest.main()
