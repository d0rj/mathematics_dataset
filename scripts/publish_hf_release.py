"""Verify the prepared release; publishing requires the explicit --publish flag."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

REPOSITORY = "d0rj/mathematics_dataset"


def verify(manifest_path):
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["repo_id"] != REPOSITORY or manifest["repo_type"] != "dataset":
        raise ValueError("Unexpected publication target")
    revision = manifest["base_revision"]
    if len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
        raise ValueError("Expected a full parent commit hash")
    seen = set()
    selected = []
    for entry in manifest["files"]:
        target = PurePosixPath(entry["path"])
        if (
            not target.parts
            or target.is_absolute()
            or ".." in target.parts
            or "\\" in entry["path"]
            or not (target.as_posix() == "README.md" or target.parts[0] == "rl")
        ):
            raise ValueError(f"Disallowed upload path: {target}")
        if entry["path"] in seen:
            raise ValueError("Duplicate upload target")
        seen.add(entry["path"])
        source = path.parent.joinpath(*target.parts)
        for part in (source, *source.parents):
            if part.is_symlink():
                raise ValueError("Linked release inputs are not allowed")
            if part == path.parent:
                break
        if (
            not source.is_file()
            or source.stat().st_size != entry["size"]
            or (hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"])
        ):
            raise ValueError(f"Release file changed: {target}")
        if entry["size"] > 5_000_000:
            raise ValueError("Oversized release file")
        selected.append((entry["path"], source))
    if "README.md" not in seen or "rl/pyproject.toml" not in seen:
        raise ValueError("Incomplete release")
    if sum(item["size"] for item in manifest["files"]) > 50_000_000:
        raise ValueError("Unexpectedly large release")
    return manifest, selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--publish", action="store_true", help="Create the reviewed HF commit"
    )
    args = parser.parse_args()
    manifest, selected = verify(args.manifest)
    if not args.publish:
        print(
            json.dumps(
                {
                    "repo_id": REPOSITORY,
                    "parent_commit": manifest["base_revision"],
                    "add_or_replace": [target for target, _ in selected],
                    "delete": [],
                    "uploaded": False,
                },
                indent=2,
            )
        )
        return
    from huggingface_hub import CommitOperationAdd, HfApi

    result = HfApi().create_commit(
        repo_id=REPOSITORY,
        repo_type="dataset",
        parent_commit=manifest["base_revision"],
        operations=[
            CommitOperationAdd(path_in_repo=target, path_or_fileobj=str(source))
            for target, source in selected
        ],
        commit_message=(
            f"Publish mathematics RL {manifest['package_version']} with five framework adapters"
        ),
    )
    print(result.commit_url)


if __name__ == "__main__":
    main()
