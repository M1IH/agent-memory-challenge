import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.store import RetrievalConfig
from benchmarks.run_ablation import run_variant


class AblationTests(unittest.TestCase):
    def test_default_fusion_weights_match_evidence_backed_configuration(self):
        config = RetrievalConfig()
        self.assertEqual(1.5, config.lexical_weight)
        self.assertEqual(0.5, config.dense_weight)

    def test_inherited_disabled_embeddings_do_not_contaminate_variants(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"

            def fake_run(command, **kwargs):
                self.assertEqual("true", kwargs["env"]["AML_EMBED_ENABLED"])
                self.assertNotIn("--no-embeddings", command)
                output.write_text(json.dumps({"mrr": 0.5}), encoding="utf-8")

            with patch.dict(os.environ, {"AML_EMBED_ENABLED": "false"}):
                with patch("benchmarks.run_ablation.subprocess.run", side_effect=fake_run):
                    self.assertEqual("hybrid", run_variant("hybrid", [], 10, output)["variant"])
                self.assertEqual("false", os.environ["AML_EMBED_ENABLED"])

    def test_invalid_weights_are_rejected_before_search(self):
        for value in (float("nan"), float("inf"), -1.0, 0.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                RetrievalConfig(dense_weight=value)
