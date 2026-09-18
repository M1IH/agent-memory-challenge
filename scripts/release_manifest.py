from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


CRITICAL_FILES = (
    ".github/workflows/tests.yml",
    "Dockerfile",
    "README.md",
    "docs/cycle-2-deployment.md",
    "requirements.lock",
    "requirements.txt",
    "app/__init__.py",
    "app/embedding.py",
    "app/main.py",
    "app/store.py",
    "scripts/release_manifest.py",
    "scripts/smoke_local.py",
    "scripts/smoke_remote.py",
)
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
IMAGE_ID_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def critical_file_hashes(root: Path) -> dict[str, str]:
    missing = [relative for relative in CRITICAL_FILES if not (root / relative).is_file()]
    if missing:
        raise ValueError(f"missing release-critical files: {', '.join(missing)}")
    return {relative: file_sha256(root / relative) for relative in CRITICAL_FILES}


def combined_sha256(hashes: dict[str, str]) -> str:
    payload = "".join(f"{path}\0{digest}\n" for path, digest in sorted(hashes.items()))
    return hashlib.sha256(payload.encode()).hexdigest()


def git_output(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def validate_image_identity(git_sha: str, image_id: str, image_revision: str) -> None:
    if not SHA_PATTERN.fullmatch(git_sha):
        raise ValueError("git SHA must be a lowercase 40-character hexadecimal value")
    if not IMAGE_ID_PATTERN.fullmatch(image_id):
        raise ValueError("image ID must be a sha256 digest")
    if image_revision != git_sha:
        raise ValueError("image revision does not match the checked-out git SHA")


def build_manifest(
    root: Path,
    *,
    allow_dirty: bool,
    image_id: str | None,
    image_revision: str | None,
) -> dict[str, object]:
    git_sha = git_output(root, "rev-parse", "HEAD")
    dirty_paths = git_output(root, "status", "--porcelain").splitlines()
    if dirty_paths and not allow_dirty:
        raise ValueError("working tree is not clean")
    if (image_id is None) != (image_revision is None):
        raise ValueError("image ID and image revision must be supplied together")
    if image_id is not None and image_revision is not None:
        validate_image_identity(git_sha, image_id, image_revision)

    hashes = critical_file_hashes(root)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": {
            "sha": git_sha,
            "remote": git_output(root, "remote", "get-url", "origin"),
            "clean": not dirty_paths,
            "dirty_paths": dirty_paths,
        },
        "source": {
            "critical_files": hashes,
            "combined_sha256": combined_sha256(hashes),
        },
        "image": None
        if image_id is None
        else {
            "id": image_id,
            "revision": image_revision,
            "revision_matches_git": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a fail-closed source and container release manifest."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--image-id")
    parser.add_argument("--image-revision")
    args = parser.parse_args()

    manifest = build_manifest(
        args.root.resolve(),
        allow_dirty=args.allow_dirty,
        image_id=args.image_id,
        image_revision=args.image_revision,
    )
    rendered = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
