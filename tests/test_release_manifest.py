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
        self.assertIn("requirements.lock", hashes)
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

    def test_revision_label_does_not_invalidate_dependency_layers(self):
        dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()

        self.assertGreater(dockerfile.index("ARG VCS_REF"), dockerfile.index("COPY app ./app"))
        self.assertGreater(dockerfile.index("LABEL org.opencontainers"), dockerfile.index("ARG VCS_REF"))
        self.assertGreater(
            dockerfile.index("ENV PYTHONDONTWRITEBYTECODE"),
            dockerfile.index("model_optimized.onnx"),
        )
        self.assertGreater(
            dockerfile.index("ARG AML_EMBED_MODEL_SHA256"),
            dockerfile.index("TextEmbedding('BAAI/bge-small-en-v1.5'"),
        )

    def test_documented_and_ci_volumes_mount_the_database_directory(self):
        root = Path(__file__).resolve().parents[1]
        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        readme = (root / "README.md").read_text(encoding="utf-8")
        workflow = (root / ".github/workflows/tests.yml").read_text(encoding="utf-8")

        self.assertIn("AML_DB_PATH=/data/memory.db", dockerfile)
        self.assertIn("-v agent-memory-data:/data", readme)
        self.assertEqual(2, workflow.count("-v aml-ci-data:/data"))
        self.assertNotIn(":/app/data", readme + workflow)

    def test_docker_build_inputs_are_immutable(self):
        root = Path(__file__).resolve().parents[1]
        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        workflow = (root / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        direct = {
            line.strip().lower()
            for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        locked = {
            line.strip().lower()
            for line in (root / "requirements.lock").read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

        self.assertRegex(dockerfile.splitlines()[0], r"^FROM python:3\.12-slim@sha256:[0-9a-f]{64}$")
        self.assertIn("pip install --no-cache-dir -r requirements.lock", dockerfile)
        self.assertIn("cache-dependency-path: requirements.lock", workflow)
        for requirement in direct:
            package = requirement.split("[", 1)[0].split("==", 1)[0]
            self.assertTrue(
                any(item.split("==", 1)[0].split("[", 1)[0] == package for item in locked),
                f"direct dependency is absent from requirements.lock: {package}",
            )


if __name__ == "__main__":
    unittest.main()
