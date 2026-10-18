"""Exercise the actual installed v1 plugin loader, Trace and Task.score on POSIX."""
# ruff: noqa: E402

import json
import sys
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip(
        "Verifiers 0.4 imports POSIX fcntl; run integration tests in WSL", allow_module_level=True
    )

vf = pytest.importorskip("verifiers.v1", reason="Install the verifiers extra in a separate venv")
from verifiers.v1.utils.loaders import environment_class, taskset_class

from mathematics_rl import MathematicsEnv, MathematicsTaskset
from mathematics_rl.catalog import MODULES
from mathematics_rl.taskset import MathematicsConfig, MathematicsData, MathematicsTask

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures"
_ROWS = [
    json.loads(line)
    for path in FIXTURE_DIRECTORY.glob("generated_*.ndjson")
    for line in path.read_text(encoding="utf-8").splitlines()
]
_REPRESENTATIVES = {}
for _row in _ROWS:
    _REPRESENTATIVES.setdefault((_row["language"], _row["module"]), _row)


def test_real_plugin_discovery_and_loading():
    assert taskset_class("mathematics-rl") is MathematicsTaskset
    assert environment_class("mathematics-rl") is MathematicsEnv
    taskset = MathematicsTaskset(
        MathematicsConfig(source=str(FIXTURE_DIRECTORY / "generated_ru.ndjson"), language="ru")
    )
    tasks = list(taskset.take(5))
    assert len(tasks) == 5
    assert len({task.key for task in tasks}) == 5
    assert [task.data.idx for task in tasks] == list(range(5))
    assert all(task.data.category == "interpolate" for task in tasks)
    assert all(task.data.prompt.endswith(task.data.question) for task in tasks)


@pytest.mark.parametrize(
    "row", list(_REPRESENTATIVES.values()), ids=lambda row: f"{row['language']}/{row['module']}"
)
@pytest.mark.asyncio
async def test_real_trace_scoring_each_module_and_language(row):
    task = MathematicsTask(
        MathematicsData(
            id="fixture",
            prompt=row["question"],
            question=row["question"],
            answer=row["answer"],
            module=row["module"],
            category=row["category"],
            language=row["language"],
            answer_kind="fixture",
            dataset_revision="fixture",
            content_hash="fixture",
        )
    )
    trace = vf.Trace(
        task={"type": "MathematicsTask", "data": task.data, "key": task.key},
        agent={"config": {}},
        root_reply=row["answer"],
    )
    await task.score(trace)
    assert trace.reward == 1, trace.model_dump()
    assert trace.metrics["accuracy"] == 1
    assert trace.info["mathematics_grading"]["status"] == "correct"
    assert len(trace.rewards) == 1
    wire = trace.model_dump(mode="json")
    assert wire["task"]["data"]["answer"] == row["answer"]
    assert wire["task"]["data"]["module"] == row["module"]


def test_full_integration_matrix():
    assert set(_REPRESENTATIVES) == {
        (language, module) for language in ("ru", "en") for module in MODULES
    }
