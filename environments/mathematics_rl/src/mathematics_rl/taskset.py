"""Real Verifiers v1 Taskset/Task integration (verifiers==0.4.0)."""

import asyncio
from functools import lru_cache
from typing import Literal

import verifiers.v1 as vf
from pydantic import Field

from .data import GRADING_VERSION, REVISION, examples
from .worker import Grader


class MathematicsData(vf.TaskData):
    question: str
    answer: str
    module: str
    category: str
    language: str
    answer_kind: str
    dataset_revision: str
    content_hash: str
    grading_version: str = GRADING_VERSION


class MathematicsTaskConfig(vf.TaskConfig):
    grading_timeout: float = Field(default=3.0, gt=0, le=30)


@lru_cache(maxsize=8)
def _grader(timeout: float) -> Grader:
    return Grader(timeout)


class MathematicsTask(vf.Task[MathematicsData, vf.State, MathematicsTaskConfig]):
    @property
    def key(self) -> str:
        return self.data.id

    @vf.reward
    async def correct(self, trace: vf.Trace) -> float:
        result = await asyncio.to_thread(
            _grader(self.config.grading_timeout).grade,
            self.data.module,
            self.data.question,
            self.data.answer,
            trace.last_reply,
        )
        if result.status == "invalid_reference":
            raise ValueError(f"Invalid reference for {self.data.id} ({self.data.module})")
        trace.info["mathematics_grading"] = {
            "status": result.status,
            "kind": result.kind,
            "version": GRADING_VERSION,
            "extracted": result.extracted,
        }
        trace.metrics["parse_error"] = float(result.status == "parse_error")
        trace.metrics["grading_timeout"] = float(result.status == "timeout")
        trace.metrics["accuracy"] = result.reward
        return result.reward

    async def validate(self, runtime=None) -> bool:
        result = await asyncio.to_thread(
            _grader(self.config.grading_timeout).grade,
            self.data.module,
            self.data.question,
            self.data.answer,
            self.data.answer,
        )
        # This is verifier/reference compatibility, not an independent mathematical proof.
        return result.status == "correct"


class MathematicsConfig(vf.TasksetConfig):
    language: Literal["ru", "en"] = "ru"
    mode: Literal["train", "interpolate", "extrapolate"] = "interpolate"
    categories: list[str] = Field(default_factory=list)
    modules: list[str] = Field(default_factory=list)
    revision: str = REVISION
    source: str | None = None
    seed: int = 42
    shuffle_buffer: int = Field(default=0, ge=0, le=100000)
    task: MathematicsTaskConfig = Field(default_factory=MathematicsTaskConfig)


class MathematicsTaskset(vf.Taskset[MathematicsTask, MathematicsConfig]):
    def load(self):
        for example in examples(
            language=self.config.language,
            mode=self.config.mode,
            categories=self.config.categories,
            modules=self.config.modules,
            revision=self.config.revision,
            source=self.config.source,
            seed=self.config.seed,
            shuffle_buffer=self.config.shuffle_buffer,
        ):
            yield MathematicsTask(
                MathematicsData(
                    id=example.id,
                    name=f"{example.language}/{example.category}/{example.module}",
                    prompt=example.prompt,
                    question=example.question,
                    answer=example.answer,
                    module=example.module,
                    category=example.category,
                    language=example.language,
                    answer_kind=example.kind,
                    dataset_revision=example.revision,
                    content_hash=example.content_hash,
                ),
                self.config.task,
            )


def _default_agent():
    return vf.AgentConfig(
        harness=vf.HarnessConfig(id="null"),
        runtime=vf.SubprocessConfig(),
        max_turns=1,
        network_notice=False,
    )


class MathematicsEnvConfig(vf.EnvConfig):
    taskset: MathematicsConfig = Field(default_factory=MathematicsConfig)
    agent: vf.AgentConfig = _default_agent()


class MathematicsEnv(vf.Env[MathematicsEnvConfig]):
    """Single agent, tool-less harness and local subprocess runtime by default."""

    async def run(self, task, agents):
        await agents.agent.run(task)
