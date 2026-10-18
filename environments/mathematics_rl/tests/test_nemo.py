import json

import pytest

pytest.importorskip("nemo_gym")

from fastapi.testclient import TestClient
from nemo_gym.openai_utils import NeMoGymResponse
from test_adapters import module_examples

from mathematics_rl.adapters.common import private_record
from mathematics_rl.adapters.nemo import (
    MathematicsVerifyRequest,
    export_tasks,
    make_server,
)


def response(text):
    return NeMoGymResponse(
        id="test-response",
        created_at=0,
        model="test",
        object="response",
        parallel_tool_calls=False,
        tool_choice="auto",
        tools=[],
        output=[
            {
                "type": "message",
                "id": "msg",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
    )


def server():
    return make_server()


@pytest.mark.asyncio
async def test_native_nemo_matrix_and_export(tmp_path):
    tasks = module_examples()
    export_tasks(tasks, tmp_path / "nemo")
    rows = [json.loads(line) for line in (tmp_path / "nemo/tasks.jsonl").read_text().splitlines()]
    app = server()
    try:
        for row, task in zip(rows, tasks, strict=True):
            assert row["responses_create_params"]["input"][0]["content"] == task.prompt
            request = MathematicsVerifyRequest(**row, response=response(task.answer))
            verified = await app.verify(request)
            assert verified.reward == 1
            assert "math_example" not in verified.model_dump()
    finally:
        app.close()


def test_native_nemo_http_verify():
    app = server()
    task = module_examples()[0]
    try:
        body = MathematicsVerifyRequest(
            math_example=private_record(task),
            responses_create_params={"input": [{"role": "user", "content": task.prompt}]},
            response=response("wrong answer"),
        )
        with TestClient(app.setup_webserver()) as client:
            reply = client.post("/verify", json=body.model_dump(mode="json"))
            assert reply.status_code == 200, reply.text
            assert reply.json()["reward"] == 0
    finally:
        app.close()
