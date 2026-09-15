import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.release_manifest import (
    combined_sha256,
    critical_file_hashes,
    validate_image_identity,
)


class ReleaseManifestTests(unittest.TestCase):
    def test_combined_hash_is_stable_across_mapping_order(self):
        first = {"b": "2", "a": "1"}
        second = {"a": "1", "b": "2"}

        self.assertEqual(combined_sha256(first), combined_sha256(second))

    def test_critical_hashes_fail_closed_when_files_are_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "missing release-critical files"):
                critical_file_hashes(Path(directory))

    def test_critical_hashes_cover_current_release_inputs(self):
        root = Path(__file__).resolve().parents[1]
        hashes = critical_file_hashes(root)

        self.assertEqual(hashlib.sha256((root / "Dockerfile").read_bytes()).hexdigest(), hashes["Dockerfile"])
        self.assertIn("app/store.py", hashes)
        self.assertIn(".github/workflows/tests.yml", hashes)
        self.assertIn("scripts/release_manifest.py", hashes)

    def test_image_identity_must_match_exact_git_sha(self):
        git_sha = "a" * 40
        image_id = "sha256:" + "b" * 64

        validate_image_identity(git_sha, image_id, git_sha)
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_image_identity(git_sha, image_id, "c" * 40)
        with self.assertRaisesRegex(ValueError, "sha256"):
            validate_image_identity(git_sha, "latest", git_sha)


if __name__ == "__main__":
    unittest.main()
