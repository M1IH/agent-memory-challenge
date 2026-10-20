import unittest

from benchmarks.adapt_personamem import _sessions, _split


class PersonaMemAdapterTests(unittest.TestCase):
    def test_excludes_system_persona_and_respects_question_cutoff(self):
        turns = [
            {"role": "system", "content": "Secret synthetic persona"},
            {"role": "user", "content": "I like jazz"},
            {"role": "assistant", "content": "Noted"},
            {"role": "system", "content": "Secret synthetic persona"},
            {"role": "user", "content": "I now prefer folk"},
            {"role": "assistant", "content": "Understood"},
            {"role": "user", "content": "Future conversation must be excluded"},
        ]
        memories = _sessions("context-1", turns, 5)
        self.assertEqual(2, len(memories))
        self.assertEqual([2, 2], [len(memory["turns"]) for memory in memories])
        self.assertFalse(any("Secret" in memory["content"] for memory in memories))
        self.assertFalse(any("Future" in memory["content"] for memory in memories))

    def test_shared_context_has_one_fixed_split(self):
        self.assertEqual(_split("shared-1"), _split("shared-1"))

    def test_invalid_cutoff_rejected(self):
        with self.assertRaisesRegex(ValueError, "cutoff"):
            _sessions("context-1", [{"role": "system", "content": "persona"}], 1)


if __name__ == "__main__":
    unittest.main()
