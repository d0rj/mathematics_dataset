import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).absolute().parent.parent


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_corrected_card_preserves_data_contract():
    text = (ROOT / "publication/huggingface/README.md").read_text(encoding="utf-8")
    metadata = yaml.safe_load(text.split("---", 2)[1])
    assert [field["name"] for field in metadata["dataset_info"]["features"]] == [
        "question",
        "answer",
        "category",
        "module",
    ]
    assert {
        item["name"]: item["num_examples"]
        for item in metadata["dataset_info"]["splits"]
    } == {"ru": 12699944, "en": 112709888}
    assert metadata["configs"][0]["data_files"] == [
        {"split": "ru", "path": "data/ru-*"},
        {"split": "en", "path": "data/en-*"},
    ]
    assert {
        "rl-environment",
        "verifiers",
        "mathematics",
        "harbor",
        "openenv",
        "nemo-gym",
        "agentenv",
    } <= set(metadata["tags"])
    assert "your-username" not in text and "--per_train_module=1000000" not in text
    assert metadata["license"] == "apache-2.0"


def test_release_allowlist_hashes_and_non_overwrite(tmp_path):
    prepare = load_script("prepare_hf_release")
    publish = load_script("publish_hf_release")
    output = tmp_path / "release"
    prepared = prepare.prepare(output)
    manifest, selected = publish.verify(output / "manifest.json")
    assert manifest == prepared
    paths = [path for path, _ in selected]
    assert "README.md" in paths and "rl/uv.lock" in paths
    assert "rl/FRAMEWORKS.md" in paths
    assert "rl/integrations/openenv/Dockerfile" in paths
    assert "rl/src/mathematics_rl/adapters/agentenv.py" in paths
    assert all(path == "README.md" or path.startswith("rl/") for path in paths)
    assert not any(
        "data/" in path or ".venv" in path or "__pycache__" in path for path in paths
    )
    assert len(paths) == len(set(paths))
    with pytest.raises(FileExistsError):
        prepare.prepare(output)
    first = selected[0][1]
    assert (
        hashlib.sha256(first.read_bytes()).hexdigest() == manifest["files"][0]["sha256"]
    )
    first.write_text("modified after review", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        publish.verify(output / "manifest.json")


@pytest.mark.parametrize(
    "target", ["data/ru.parquet", "../escape", "/absolute", "rl/../../escape", ""]
)
def test_upload_target_escape_is_rejected(tmp_path, target):
    manifest = {
        "repo_id": "d0rj/mathematics_dataset",
        "repo_type": "dataset",
        "base_revision": "a" * 40,
        "files": [{"path": target, "size": 0, "sha256": ""}],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_script("publish_hf_release").verify(path)
