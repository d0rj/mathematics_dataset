"""Harbor 0.24 task-directory export with a separate trusted verifier environment."""

import json
import stat
from pathlib import Path

from .. import __version__
from ..data import Example
from ..grading import MAX_COMPLETION
from ..worker import Grader
from .common import checked_grade, private_record, write_json

TASK_TOML = """schema_version = "1.4"
artifacts = ["/app/answer.txt"]
[task]
name = "mathematics/{name}"
version = "{version}"
authors = []
keywords = ["mathematics", "{language}", "{module}"]
[metadata]
category = "mathematics"
difficulty = "medium"
[agent]
timeout_sec = 180.0
[environment]
cpus = 1
memory_mb = 512
storage_mb = 1024
gpus = 0
[verifier]
timeout_sec = 60.0
environment_mode = "separate"
[verifier.environment]
cpus = 1
memory_mb = 512
storage_mb = 1024
gpus = 0
network_mode = "no-network"
"""


def export_tasks(tasks, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    package = Path(__file__).absolute().parents[1]
    paths = [
        package / f"{name}.py"
        for name in (
            "__init__",
            "catalog",
            "data",
            "grading",
            "parsing",
            "worker",
            "worker_entry",
        )
    ] + [package / "adapters" / f"{name}.py" for name in ("__init__", "common", "harbor")]
    checker = {path.relative_to(package): path.read_bytes() for path in paths}
    manifest = []
    for task in tasks:
        name = task.module.replace("__", "-").replace("_", "-") + "-" + task.id[:20]
        root = output / name
        tests = root / "tests"
        tests.mkdir(parents=True)
        (root / "task.toml").write_text(
            TASK_TOML.format(name=name, version=__version__, **private_record(task)),
            encoding="utf-8",
        )
        (root / "instruction.md").write_text(
            task.prompt + "\n\nWrite your final answer to /app/answer.txt (UTF-8).\n",
            encoding="utf-8",
        )
        (root / "environment").mkdir()
        (root / "environment" / "Dockerfile").write_text(
            "FROM python:3.13-slim\nWORKDIR /app\n", encoding="utf-8"
        )
        write_json(tests / "reference.json", private_record(task))
        # Package source is bundled only into the trusted verifier build context.
        for relative, content in checker.items():
            target = tests / "mathematics_rl" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        (tests / "Dockerfile").write_text(
            "FROM python:3.13-slim\nRUN pip install --no-cache-dir sympy==1.14.0\n"
            "COPY . /tests\nENV PYTHONPATH=/tests\nWORKDIR /tests\n",
            encoding="utf-8",
        )
        (tests / "test.sh").write_text(
            "#!/bin/sh\nset -eu\nexport PYTHONPATH=/tests\n"
            "python -m mathematics_rl.adapters.harbor\n",
            encoding="utf-8",
        )
        solution = root / "solution"
        solution.mkdir()
        write_json(solution / "answer.json", task.answer)
        (solution / "solve.sh").write_text(
            "#!/bin/sh\nset -eu\nmkdir -p /app\npython - <<'PY'\n"
            "import json\nfrom pathlib import Path\n"
            "Path('/app/answer.txt').write_text(json.loads("
            "Path('/solution/answer.json').read_text(encoding='utf-8')), encoding='utf-8')\nPY\n",
            encoding="utf-8",
        )
        manifest.append({"directory": root.name, "task_id": task.id, "module": task.module})
    write_json(output / "selection.json", {"framework": "harbor", "tasks": manifest})
    return manifest


def verify_task(reference, answer, log_dir):
    """Run in the separate verifier. Missing/malformed agent artifacts earn zero."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    reward_file = log_dir / "reward.txt"
    reward_file.write_text("0\n", encoding="utf-8")
    task = Example(**json.loads(Path(reference).read_text(encoding="utf-8")))
    answer = Path(answer)
    try:
        info = answer.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_COMPLETION * 4:
            raise ValueError("Invalid answer artifact")
        completion = answer.read_bytes()[: MAX_COMPLETION * 4 + 1].decode("utf-8")
    except (OSError, ValueError):
        write_json(log_dir / "grading.json", {"reward": 0.0, "status": "invalid_artifact"})
        return 0.0
    with Grader() as grader:
        result = checked_grade(grader, task, completion)
    write_json(log_dir / "grading.json", result.to_dict())
    reward_file.write_text(f"{result.reward}\n", encoding="utf-8")
    return result.reward


if __name__ == "__main__":
    verify_task("/tests/reference.json", "/app/answer.txt", "/logs/verifier")
