import unittest

from benchmarks.adapt_longmemeval import _split, adapt_record
from benchmarks.public_eval_schema import validate_case


def sample_record():
    return {
        "question_id": "example-1",
        "question_type": "knowledge-update",
        "question": "What is current?",
        "answer": "B",
        "question_date": "2023/04/10 (Mon) 23:07",
        "haystack_session_ids": ["s-old", "s-new"],
        "haystack_dates": ["2023/04/09 (Sun) 17:50", "2023/04/10 (Mon) 14:47"],
        "haystack_sessions": [
            [{"role": "user", "content": "Old A", "has_answer": False}],
            [{"role": "user", "content": "New B", "has_answer": True}],
        ],
        "answer_session_ids": ["s-new"],
    }


class LongMemEvalAdapterTests(unittest.TestCase):
    def test_reference_and_source_ids_are_unchanged(self):
        case = adapt_record(sample_record())
        validate_case(case)
        self.assertEqual(["B"], case["reference_answers"])
        self.assertEqual(["s-new"], case["evidence_memory_ids"])
        self.assertEqual(["s-old", "s-new"], [m["memory_id"] for m in case["memories"]])

    def test_answer_annotations_never_enter_retrieval_input(self):
        case = adapt_record(sample_record())
        for memory in case["memories"]:
            self.assertNotIn("has_answer", memory["content"])
            self.assertTrue(all("has_answer" not in turn for turn in memory["turns"]))

    def test_unknown_answer_session_is_rejected(self):
        record = sample_record()
        record["answer_session_ids"] = ["other"]
        with self.assertRaisesRegex(ValueError, "unknown answer session"):
            adapt_record(record)

    def test_duplicate_distractor_id_is_disambiguated_without_dropping_memory(self):
        record = sample_record()
        record["haystack_session_ids"].append("s-old")
        record["haystack_dates"].append(record["haystack_dates"][0])
        record["haystack_sessions"].append([{"role": "assistant", "content": "Other note"}])
        case = adapt_record(record)
        validate_case(case)
        self.assertEqual(["s-old", "s-new", "s-old#duplicate-2"], [m["memory_id"] for m in case["memories"]])
        self.assertEqual("s-old", case["memories"][2]["source_session_id"])

    def test_duplicate_answer_id_is_rejected_as_ambiguous(self):
        record = sample_record()
        record["haystack_session_ids"].append("s-new")
        record["haystack_dates"].append(record["haystack_dates"][1])
        record["haystack_sessions"].append([{"role": "assistant", "content": "Other note"}])
        with self.assertRaisesRegex(ValueError, "ambiguous answer session"):
            adapt_record(record)

    def test_split_is_stable(self):
        self.assertEqual(_split("example-1"), _split("example-1"))

    def test_numeric_answer_preserves_raw_type_and_scores_as_text(self):
        record = sample_record()
        record["answer"] = 3
        case = adapt_record(record)
        validate_case(case)
        self.assertEqual(["3"], case["reference_answers"])
        self.assertEqual(3, case["source_answer_raw"])


if __name__ == "__main__":
    unittest.main()
