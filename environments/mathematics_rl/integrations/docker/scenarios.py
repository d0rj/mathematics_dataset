"""Native framework checks for the Docker runner; all model responses are scripted."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from urllib.request import Request, urlopen

PACKAGE = Path(__file__).absolute().parents[2]
FIXTURES = PACKAGE / "tests" / "fixtures"
WRONG = "intentionally invalid mathematics answer"


def rows(language):
    from mathematics_rl.adapters.common import select_tasks

    return select_tasks(
        source=str(FIXTURES / f"generated_{language}.ndjson"),
        language=language,
        mode="all",
        limit=10_000,
    )


def representatives(language):
    seen = set()
    result = []
    for index, task in enumerate(rows(language)):
        if task.module not in seen:
            seen.add(task.module)
            result.append((index, task))
    assert len(result) == 70
    return result


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def serve_openenv(language):
    config = {
        "source": str(FIXTURES / f"generated_{language}.ndjson"),
        "language": language,
        "mode": "all",
        "limit": 10_000,
    }
    path = Path(tempfile.mkdtemp()) / "config.json"
    save(path, config)
    os.execvp(
        "mathematics-openenv",
        ["mathematics-openenv", "--config", str(path), "--host", "0.0.0.0", "--port", "8000"],
    )


def serve_nemo_native():
    # Match the config injected by Gym's supervisor; exercise the shipped shim.
    os.environ["NEMO_GYM_CONFIG_PATH"] = "mathematics"
    os.environ["NEMO_GYM_CONFIG_DICT"] = json.dumps(
        {
            "dry_run": False,
            "head_server": {"host": "127.0.0.1", "port": 11000},
            "mathematics": {
                "resources_servers": {
                    "mathematics": {
                        "entrypoint": str(PACKAGE / "integrations/nemo/app.py"),
                        "host": "0.0.0.0",
                        "port": 8001,
                        "domain": "math",
                    }
                }
            },
        }
    )
    os.execvp("mathematics-nemo", ["mathematics-nemo"])


def openenv_check(url, language):
    from mathematics_rl.adapters.openenv import MathematicsAction, MathematicsClient

    checks = []
    with MathematicsClient(base_url=url, connect_timeout_s=10, message_timeout_s=30) as client:
        for index, task in representatives(language):
            for answer, expected in ((task.answer, 1), (WRONG, 0)):
                initial = client.reset(task_index=index)
                assert initial.observation.prompt == task.prompt, (task.module, index)
                state = client.state().model_dump()
                assert "answer" not in state and "content_hash" not in state
                result = client.step(MathematicsAction(answer=answer))
                assert result.done and result.reward == expected, (task.module, result)
                assert client.state().step_count == 1
            checks.append(
                {"module": task.module, "language": language, "correct": 1, "incorrect": 0}
            )
        try:
            client.step(MathematicsAction(answer=task.answer))
        except Exception as error:
            assert "terminal" in str(error).lower(), str(error)
        else:
            raise AssertionError("OpenEnv accepted a second submission")
    return {
        "framework": "openenv",
        "cases": checks,
        "episodes": 140,
        "transport": "native EnvClient over Docker network",
        "passed": True,
    }


def response(text):
    return {
        "id": "scripted",
        "object": "response",
        "created_at": 0,
        "model": "scripted",
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "output": [
            {
                "id": "msg",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
    }


def request(url, body=None):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    with urlopen(
        Request(url, data=data, headers={"Content-Type": "application/json"}), timeout=30
    ) as reply:
        return json.load(reply)


def nemo_check(url):
    checks = []
    for language in ("en", "ru"):
        for _, task in representatives(language):
            row = {
                "responses_create_params": {"input": [{"role": "user", "content": task.prompt}]},
                "math_example": asdict(task),
            }
            for answer, expected in ((task.answer, 1), (WRONG, 0)):
                result = request(url + "/verify", {**row, "response": response(answer)})
                assert result["reward"] == expected and not result["mask_sample"], result
                assert "math_example" not in result and result["task_id"] == task.id
            checks.append(
                {"module": task.module, "language": language, "correct": 1, "incorrect": 0}
            )
    assert request(url + "/reverify_mode") == "stateless"
    return {
        "framework": "nemo",
        "cases": checks,
        "episodes": 280,
        "transport": "native resource server HTTP over Docker network",
        "passed": True,
    }


async def agentenv_check():
    # The trainer supplies each answer through AgentEnv's real turn protocol.
    from agent_env.config import configure
    from agent_env.task import EpisodeSpec

    from mathematics_rl.adapters.agentenv import make_task

    state = tempfile.mkdtemp(prefix="mathematics-agentenv-")
    os.environ["XDG_STATE_HOME"] = state
    os.environ["AGENT_ENV_CONFIG"] = str(Path(state) / "config.toml")
    Path(os.environ["AGENT_ENV_CONFIG"]).write_text("")
    configure()
    checks = []
    for language in ("en", "ru"):
        for _, task in representatives(language):
            for answer, expected in ((task.answer, 1), (WRONG, 0)):
                episode = await EpisodeSpec.from_task(make_task(task), turn_timeout=30).start()
                try:
                    turn = await asyncio.wait_for(episode.next_turn(), 30)
                    assert turn.prompt == task.prompt
                    await turn.end(response=answer)
                    assert await asyncio.wait_for(episode.next_turn(), 30) is None
                    assert await asyncio.wait_for(episode.result(), 30) == {"grade": expected}
                finally:
                    await episode.abandon("Docker check finished")
            checks.append(
                {"module": task.module, "language": language, "correct": 1, "incorrect": 0}
            )
    return {
        "framework": "agentenv",
        "cases": checks,
        "episodes": 280,
        "transport": "native EpisodeSpec, turn, result and local stores",
        "passed": True,
    }


def harbor_prepare(output, limit):
    from mathematics_rl.adapters.harbor import export_tasks

    tasks = [task for lang in ("en", "ru") for _, task in representatives(lang)]
    return export_tasks(tasks[:limit] if limit else tasks, output)


def harbor_verify(job, expected=1):
    trials = []
    for path in Path(job).glob("*/result.json"):
        result = json.loads(path.read_text())
        assert not result["exception_info"], (path, result["exception_info"])
        assert result["verifier_environment_mode"] == "separate", path
        assert result["verifier_result"]["rewards"]["reward"] == expected, (path, result)
        trials.append(
            {"task_name": result["task_name"], "reward": expected, "separate_verifier": True}
        )
    assert trials, job
    return {"framework": "harbor", "trials": trials, "episodes": len(trials), "passed": True}


def unit_tests(output):
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "pytest_asyncio.plugin",
        "tests",
        "-q",
        "--junitxml",
        str(Path(output) / "pytest.xml"),
    ]
    Path(output).mkdir(parents=True, exist_ok=True)
    subprocess.run(command, check=True, timeout=300)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenario",
        choices=(
            "serve-openenv",
            "serve-nemo-native",
            "openenv",
            "nemo",
            "agentenv",
            "harbor-prepare",
            "harbor-verify",
            "unit",
        ),
    )
    parser.add_argument("--language", choices=("en", "ru"), default="en")
    parser.add_argument("--url")
    parser.add_argument("--output", type=Path, default=Path("/results"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--expected", type=int, default=1)
    args = parser.parse_args()
    started = time.monotonic()
    if args.scenario == "serve-openenv":
        serve_openenv(args.language)
    elif args.scenario == "serve-nemo-native":
        serve_nemo_native()
    elif args.scenario == "unit":
        unit_tests(args.output)
        return
    elif args.scenario == "openenv":
        result = openenv_check(args.url, args.language)
    elif args.scenario == "nemo":
        result = nemo_check(args.url)
    elif args.scenario == "agentenv":
        result = asyncio.run(agentenv_check())
    elif args.scenario == "harbor-prepare":
        result = harbor_prepare(args.output, args.limit)
    else:
        result = harbor_verify(args.output, args.expected)
    if isinstance(result, dict):
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        save(args.output / "report.json", result)
        print(json.dumps({k: v for k, v in result.items() if k not in ("cases", "trials")}))
    else:
        print(json.dumps({"exported": len(result), "output": str(args.output)}))


if __name__ == "__main__":
    main()
