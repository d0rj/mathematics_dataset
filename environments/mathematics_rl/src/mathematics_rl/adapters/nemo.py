"""NeMo Gym 0.7 native stateless resource server and Responses API dataset export."""

import argparse
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import ClassVar

from nemo_gym.base_resources_server import (
    BaseResourcesServerConfig,
    BaseVerifyRequest,
    BaseVerifyResponse,
    ReverifyMode,
    SimpleResourcesServer,
)
from pydantic import PrivateAttr

from ..data import Example
from ..worker import Grader
from .common import checked_grade, private_record


class MathematicsResourcesConfig(BaseResourcesServerConfig):
    REVERIFY_MODE: ClassVar[ReverifyMode] = ReverifyMode.STATELESS
    grading_timeout: float = 3.0


class MathematicsVerifyRequest(BaseVerifyRequest):
    math_example: Example


class MathematicsVerifyResponse(BaseVerifyResponse):
    task_id: str
    grading_status: str
    answer_kind: str


def final_assistant_text(response):
    for item in reversed(response.output):
        if item.type == "message" and item.role == "assistant":
            # Reasoning, tool results, and earlier assistant turns are never the final answer.
            return "\n".join(part.text for part in item.content if part.type == "output_text")
    return ""


class MathematicsResourcesServer(SimpleResourcesServer):
    config: MathematicsResourcesConfig
    _grader: Grader | None = PrivateAttr(default=None)
    checkpoint_verify: ClassVar[str] = "replay"

    async def verify(self, body: MathematicsVerifyRequest) -> MathematicsVerifyResponse:
        if self._grader is None:
            self._grader = Grader(self.config.grading_timeout)
        result = await asyncio.to_thread(
            checked_grade, self._grader, body.math_example, final_assistant_text(body.response)
        )
        return MathematicsVerifyResponse(
            responses_create_params=body.responses_create_params,
            response=body.response,
            task_id=body.math_example.id,
            reward=result.reward,
            grading_status=result.status,
            answer_kind=result.kind,
        )

    def close(self):
        if self._grader:
            self._grader.close()


def make_server(host="127.0.0.1", port=8001):
    from nemo_gym.config_types import BaseServerConfig
    from nemo_gym.server_utils import ServerClient
    from omegaconf import OmegaConf

    return MathematicsResourcesServer(
        config=MathematicsResourcesConfig(
            host=host, port=port, name="mathematics", entrypoint=__file__, domain="math"
        ),
        server_client=ServerClient(
            head_server_config=BaseServerConfig(host=host, port=11000),
            global_config_dict=OmegaConf.create({}),
        ),
    )


def make_app(host="127.0.0.1", port=8001):
    server = make_server(host, port)
    app = server.setup_webserver()
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        try:
            async with original_lifespan(app):
                yield
        finally:
            server.close()

    app.router.lifespan_context = lifespan
    return app


def export_tasks(tasks, output):
    import json

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    count = 0
    with (output / "tasks.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for task in tasks:
            row = {
                "responses_create_params": {"input": [{"role": "user", "content": task.prompt}]},
                "math_example": private_record(task),
            }
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return {"framework": "nemo-gym", "tasks": count}


def main():
    if os.getenv("NEMO_GYM_CONFIG_DICT"):
        MathematicsResourcesServer.run_webserver()
        return
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    uvicorn.run(make_app(args.host, args.port), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
