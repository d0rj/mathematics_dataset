"""Prepare a new allowlisted HF dataset release directory; never uploads or deletes data."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

REPOSITORY = "d0rj/mathematics_dataset"
BASE_REVISION = "d9f78d0665b3a13dad21c6830b9b358c8a25ae74"
ROOT = Path(__file__).absolute().parent.parent
PACKAGE = ROOT / "environments" / "mathematics_rl"
TOP_LEVEL = (
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "LICENSE",
    "NOTICE",
    "GRADING.md",
    "MODULES.md",
    "VALIDATION.md",
    "FRAMEWORKS.md",
    ".dockerignore",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    yield ROOT / "publication" / "huggingface" / "README.md", "README.md"
    for name in TOP_LEVEL:
        yield PACKAGE / name, f"rl/{name}"
    for pattern in (
        "src/**/*.py",
        "tests/test_*.py",
        "tests/fixtures/*.ndjson",
        "tests/fixtures/*.toml",
        "integrations/**/*.py",
        "integrations/**/*.yaml",
        "integrations/**/*.json",
        "integrations/**/Dockerfile",
    ):
        for path in sorted(PACKAGE.glob(pattern)):
            yield path, f"rl/{path.relative_to(PACKAGE).as_posix()}"


def prepare(output):
    output = Path(output)
    selected = list(sources())
    # Check the entire selection before creating anything.
    for path, _ in selected:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing or linked release input: {path}")
        if path.stat().st_size > 5_000_000:
            raise ValueError(f"Unexpectedly large release input: {path}")
    output.mkdir(parents=True, exist_ok=False)
    files = []
    for source, destination in selected:
        target = output / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files.append(
            {
                "path": destination,
                "sha256": sha256(target),
                "size": target.stat().st_size,
            }
        )
    manifest = {
        "repo_id": REPOSITORY,
        "repo_type": "dataset",
        "base_revision": BASE_REVISION,
        "package_version": "0.2.0",
        "files": files,
        "retained_parquet_files": 33,
        "data_operations": "none; README and rl/ additions only",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "dist" / "hf-release-0.2.0"
    )
    args = parser.parse_args()
    manifest = prepare(args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "files": len(manifest["files"]),
                "bytes": sum(item["size"] for item in manifest["files"]),
                "base_revision": BASE_REVISION,
                "uploaded": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
