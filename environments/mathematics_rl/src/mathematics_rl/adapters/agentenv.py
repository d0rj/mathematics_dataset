"""Scale AI AgentEnv native task-step plugin and single-turn task factory."""

import asyncio
from functools import lru_cache
from typing import ClassVar

from agent_env.task import Task
from agent_env.task_step.task_step import TaskStep
from agent_env.task_step.task_steps.deploy_agent import DeployAgentTaskStep
from agent_env.task_step.task_steps.prompt_agent import PromptAgentTaskStep

from ..data import Example
from ..worker import Grader
from .common import checked_grade, private_record, write_json


@lru_cache(maxsize=8)
def _grader(timeout):
    # Task steps are short-lived; reuse bounded, serialized workers across episodes.
    return Grader(timeout)


class MathematicsGradeStep(TaskStep):
    type: ClassVar[str] = "mathematics_grade"
    entity_refs = ()

    def __init__(self, id, version, example, prompt_id="answer", grading_timeout=3, **kwargs):
        super().__init__(id, version, **kwargs)
        self.example = Example(**example)
        self.prompt_id = prompt_id
        self.grading_timeout = grading_timeout

    @classmethod
    def from_dict(cls, data):
        return cls(
            **cls._base_from_dict(data),
            example=data["example"],
            prompt_id=data.get("prompt_id", "answer"),
            grading_timeout=data.get("grading_timeout", 3),
        )

    def to_dict(self):
        return super().to_dict() | {
            "example": private_record(self.example),
            "prompt_id": self.prompt_id,
            "grading_timeout": self.grading_timeout,
        }

    async def execute(self, context):
        matches = [item for item in context.prompt_responses if item.prompt_id == self.prompt_id]
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one response to {self.prompt_id!r}")
        response = matches[0]
        if response.error_type:
            raise RuntimeError(f"Agent execution failed: {response.error_type}")
        result = await asyncio.to_thread(
            checked_grade, _grader(self.grading_timeout), self.example, response.response or ""
        )
        context.metadata.setdefault("verifications", {})[self.id] = {
            "score": result.reward,
            "results": [
                {
                    "id": "mathematics",
                    "score": result.reward,
                    "result": result.reward == 1.0,
                    "status": result.status,
                    "answer_kind": result.kind,
                }
            ],
        }
        return context


def make_task(example, *, agent_id=None, model=None):
    """For EpisodeSpec the trainer supplies the response; no deployed agent is needed."""
    return Task(
        id=f"mathematics-{example.id}",
        version=None,
        steps=[
            DeployAgentTaskStep(
                id="agent", version=None, agent_name="solver", a2a_agent_id=agent_id
            ),
            PromptAgentTaskStep(
                id="prompt",
                version=None,
                agent_name="solver",
                prompt_id="answer",
                prompt=example.prompt,
                model=model,
                max_turns=1,
            ),
            MathematicsGradeStep(
                id="grade", version=None, prompt_id="answer", example=private_record(example)
            ),
        ],
    )


def export_tasks(tasks, output, *, agent_id=None, model=None):
    from pathlib import Path

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for example in tasks:
        task = make_task(example, agent_id=agent_id, model=model)
        write_json(output / "tasks" / f"{task.id}.json", [step.to_dict() for step in task.steps])
        manifest.append({"task_id": example.id, "bundle_task": task.id, "module": example.module})
    write_json(output / "selection.json", {"framework": "agentenv", "tasks": manifest})
    (output / "README.md").write_text(
        "Single-turn mathematics tasks. Install mathematics-rl[agentenv] in the same environment.\n"
        "Each task is a separate episode. Use EpisodeSpec.from_task(Task.get(task_id)) with an\n"
        "imported bundle, or make_task(example) directly. Model agents need --agent-id and\n"
        "--model at export and a configured agent store. References stay in grader steps.\n",
        encoding="utf-8",
    )
    return manifest
