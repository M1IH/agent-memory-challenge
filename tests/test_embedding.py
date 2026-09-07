import unittest

from app.embedding import positive_concurrency


class EmbeddingConfigurationTests(unittest.TestCase):
    def test_embedding_concurrency_must_be_positive_integer(self):
        self.assertEqual(2, positive_concurrency("2"))
        for value in ("0", "-1", "many"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "positive integer"
            ):
                positive_concurrency(value)


if __name__ == "__main__":
    unittest.main()
