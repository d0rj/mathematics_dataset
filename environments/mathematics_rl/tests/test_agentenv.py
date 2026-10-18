import asyncio
import importlib.metadata
import json

import pytest

pytest.importorskip("agent_env")

from agent_env.bundle.parse import parse_bundle
from agent_env.config import configure, reset_config
from agent_env.task import EpisodeSpec
from agent_env.task_step.context import PromptResponse, TaskStepContext
from agent_env.task_step.registry import get_task_step_registry
from test_adapters import module_examples

from mathematics_rl.adapters.agentenv import MathematicsGradeStep, export_tasks, make_task


@pytest.fixture(autouse=True)
def isolated_agentenv_stores(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text("")
    monkeypatch.setenv("AGENT_ENV_CONFIG", str(config))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("AGENT_ENV_OBJECT_STORE", "local")
    monkeypatch.setenv("AGENT_ENV_DOCUMENT_STORE", "local")
    reset_config()
    configure()
    yield
    reset_config()


def test_native_agentenv_plugin_discovery():
    entries = importlib.metadata.entry_points(group="agent_env.task_steps")
    assert any(entry.name == "mathematics_grade" for entry in entries)
    assert get_task_step_registry()["mathematics_grade"] is MathematicsGradeStep


def test_native_agentenv_export_bundle(tmp_path):
    tasks = module_examples()
    selected = [tasks[0], tasks[-1]]
    output = tmp_path / "mathematics-bundle"
    manifest = export_tasks(selected, output)
    parsed = parse_bundle(output)
    assert len(parsed.entries) == 2
    for item in manifest:
        steps = json.loads((output / "tasks" / f"{item['bundle_task']}.json").read_text())
        assert steps[-1]["type"] == "mathematics_grade"
        assert steps[1]["prompt"] == next(t.prompt for t in selected if t.id == item["task_id"])
    with pytest.raises(FileExistsError):
        export_tasks(selected, output)


@pytest.mark.asyncio
async def test_native_agentenv_matrix_and_roundtrip():
    for task in module_examples():
        native = make_task(task)
        spec = EpisodeSpec.from_task(native)
        assert spec.trainer_agents == ("solver",)
        step = MathematicsGradeStep.from_dict(native.steps[-1].to_dict())
        context = TaskStepContext(
            prompt_responses=[PromptResponse(prompt_id="answer", response=task.answer)]
        )
        result = await step.execute(context)
        assert result.metadata["verifications"]["grade"]["score"] == 1
        assert native.steps[1].prompt == task.prompt


@pytest.mark.asyncio
async def test_agentenv_wrong_answer_and_missing_response():
    step = make_task(module_examples()[0]).steps[-1]
    with pytest.raises(RuntimeError, match="exactly one"):
        await step.execute(TaskStepContext())
    context = TaskStepContext(
        prompt_responses=[PromptResponse(prompt_id="answer", response="wrong")]
    )
    assert (await step.execute(context)).metadata["verifications"]["grade"]["score"] == 0


@pytest.mark.asyncio
async def test_real_agentenv_episode_lifecycle():
    task = module_examples()[0]
    run = await EpisodeSpec.from_task(make_task(task), turn_timeout=30).start()
    try:
        turn = await asyncio.wait_for(run.next_turn(), timeout=30)
        assert turn.prompt == task.prompt
        await turn.end(response=task.answer)
        assert await asyncio.wait_for(run.next_turn(), timeout=30) is None
        scores = await asyncio.wait_for(run.result(), timeout=30)
        assert scores == {"grade": 1.0}
    finally:
        await run.abandon("test finished")
