import json
import tomllib

import pytest

pytest.importorskip("harbor")

from harbor.models.task.task import Task
from test_adapters import module_examples

from mathematics_rl.adapters.harbor import export_tasks


def test_native_harbor_loads_both_languages_all_modules(tmp_path):
    tasks = module_examples()
    manifest = export_tasks(tasks, tmp_path / "tasks")
    assert len(manifest) == 140
    for item, example in zip(manifest, tasks, strict=True):
        path = tmp_path / "tasks" / item["directory"]
        assert Task.is_valid_dir(path)
        task = Task(path)
        assert example.prompt in task.instruction
        config = tomllib.loads((path / "task.toml").read_text())
        assert config["verifier"]["environment_mode"] == "separate"
        assert config["artifacts"] == ["/app/answer.txt"]
        assert json.loads((path / "tests/reference.json").read_text())["id"] == example.id
