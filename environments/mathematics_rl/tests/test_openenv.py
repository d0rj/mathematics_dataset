import json
import socket
import threading
import time

import pytest

pytest.importorskip("openenv")

from fastapi.testclient import TestClient
from test_adapters import FIXTURES, module_examples

from mathematics_rl.adapters.openenv import (
    MathematicsAction,
    MathematicsClient,
    MathematicsEnvironment,
    make_app,
)


def test_native_openenv_all_modules():
    tasks = module_examples()
    env = MathematicsEnvironment(tasks)
    try:
        for index, task in enumerate(tasks):
            obs = env.reset(task_index=index)
            assert obs.prompt == task.prompt
            assert "answer" not in env.state.model_dump()
            scored = env.step(MathematicsAction(answer=task.answer))
            assert scored.reward == 1 and scored.done
            assert env.state.step_count == 1 and env.state.done
            with pytest.raises(RuntimeError, match="terminal"):
                env.step(MathematicsAction(answer=task.answer))
    finally:
        env.close()


def test_native_openenv_websocket_sessions():
    config = {"source": str(FIXTURES / "generated_en.ndjson"), "language": "en", "limit": 2}
    with TestClient(make_app(config)) as client:
        assert client.get("/health").status_code == 200
        with client.websocket_connect("/ws") as first, client.websocket_connect("/ws") as second:
            first.send_json({"type": "reset", "data": {"seed": 0}})
            a = first.receive_json()
            second.send_json({"type": "reset", "data": {"seed": 0}})
            b = second.receive_json()
            assert a["type"] == b["type"] == "observation", (a, b)
            assert "reference" not in json.dumps(a)
            first.send_json({"type": "step", "data": {"answer": "deliberately wrong"}})
            scored = first.receive_json()
            assert scored["data"]["done"] and scored["data"]["reward"] == 0
            second.send_json({"type": "state"})
            state = second.receive_json()
            assert state["data"]["step_count"] == 0
            assert "answer" not in state["data"]


def test_real_openenv_client_transport():
    import uvicorn

    config = {"source": str(FIXTURES / "generated_en.ndjson"), "language": "en", "limit": 2}
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(make_app(config), log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 30
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert server.started
            with MathematicsClient(base_url=f"http://127.0.0.1:{port}") as client:
                initial = client.reset(seed=0)
                assert initial.observation.prompt
                final = client.step(MathematicsAction(answer="wrong"))
                assert final.reward == 0 and final.done
                assert client.state().step_count == 1
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive()
