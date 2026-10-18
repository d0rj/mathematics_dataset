"""OpenEnv 0.9 native typed Environment, WebSocket client and HTTP server."""

import argparse
import os
from functools import partial
from uuid import uuid4

from openenv.core.client_types import StepResult
from openenv.core.env_client import EnvClient
from openenv.core.env_server import Action, Environment, Observation, State, create_app
from pydantic import Field

from ..grading import MAX_COMPLETION
from .common import OneTurnSession, read_config, select_tasks


class MathematicsAction(Action):
    answer: str = Field(max_length=MAX_COMPLETION)


class MathematicsObservation(Observation):
    prompt: str = ""
    task_id: str = ""


class MathematicsState(State):
    task_id: str = ""
    done: bool = False


class MathematicsEnvironment(
    Environment[MathematicsAction, MathematicsObservation, MathematicsState]
):
    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self, tasks=None, timeout=3):
        super().__init__()
        self.session = OneTurnSession(tasks if tasks is not None else select_tasks(), timeout)
        self._state = MathematicsState(episode_id=str(uuid4()), step_count=0)

    def reset(self, seed=None, episode_id=None, **kwargs):
        public = self.session.reset(seed=seed, task_index=kwargs.get("task_index"))
        self._state = MathematicsState(
            episode_id=episode_id or str(uuid4()), step_count=0, task_id=public["task_id"]
        )
        return MathematicsObservation(
            prompt=public.pop("prompt"), task_id=public["task_id"], reward=0.0, metadata=public
        )

    def step(self, action, timeout_s=None, **kwargs):
        result = self.session.submit(action.answer)
        self._state.step_count = 1
        self._state.done = True
        return MathematicsObservation(
            task_id=self._state.task_id,
            reward=result.reward,
            done=True,
            metadata={"grading_status": result.status, "answer_kind": result.kind},
        )

    @property
    def state(self):
        return self._state.model_copy(deep=True)

    def close(self):
        self.session.close()


class MathematicsClient(EnvClient[MathematicsAction, MathematicsObservation, MathematicsState]):
    def _step_payload(self, action):
        return action.model_dump()

    def _parse_result(self, payload):
        observation = MathematicsObservation.model_validate(payload["observation"])
        return StepResult(
            observation=observation,
            reward=payload.get("reward", observation.reward),
            done=payload.get("done", observation.done),
            metadata=payload.get("metadata", observation.metadata),
        )

    def _parse_state(self, payload):
        return MathematicsState.model_validate(payload)


def make_app(config=None):
    config = dict(config or {})
    timeout = config.pop("grading_timeout", 3)
    tasks = select_tasks(**config)
    return create_app(
        partial(MathematicsEnvironment, tasks=tasks, timeout=timeout),
        MathematicsAction,
        MathematicsObservation,
        state_cls=MathematicsState,
        env_name="mathematics",
        max_concurrent_envs=8,
    )


def app_factory():
    return make_app(read_config(os.getenv("MATHEMATICS_RL_CONFIG")))


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.getenv("MATHEMATICS_RL_CONFIG"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(make_app(read_config(args.config)), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
