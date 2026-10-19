"""Harbor 0.24 task-directory export with a separate trusted verifier environment."""

import hashlib
import json
import stat
import tarfile
from pathlib import Path

from .. import __version__
from ..data import Example
from ..grading import MAX_COMPLETION
from ..worker import Grader
from .common import checked_grade, private_record, write_json

BASE_IMAGE = (
    "python:3.13.14-slim@sha256:9662417aace5ae7b8e2609cce472b72a8958e134ba372808abe9cc1a0c0125e6"
)

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
# Docker network isolation is configured in tests/docker-compose.yaml.
"""


def build_verifier_payload(tests):
    """Snapshot private inputs into one content-addressed build-context file."""
    tests = Path(tests)
    archive = tests / "payload.tar"
    with tarfile.open(archive, "w", format=tarfile.PAX_FORMAT) as output:
        paths = [tests / "reference.json", tests / "test.sh"]
        paths.extend(sorted((tests / "mathematics_rl").rglob("*.py")))
        for path in paths:
            info = output.gettarinfo(str(path), arcname=path.relative_to(tests).as_posix())
            info.mtime = info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.pax_headers = {}
            with path.open("rb") as source:
                output.addfile(info, source)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.replace(tests / f"payload-{digest}.tar")
    reference_sha = hashlib.sha256((tests / "reference.json").read_bytes()).hexdigest()
    (tests / "Dockerfile").write_text(
        f"FROM {BASE_IMAGE}\nRUN pip install --no-cache-dir sympy==1.14.0\n"
        f'LABEL mathematics.rl.reference.sha256="{reference_sha}"\n'
        # Unique source names avoid cross-task directory transfer/cache reuse.
        f"ADD payload-{digest}.tar /tests/\n"
        f"RUN echo '{reference_sha}  /tests/reference.json' | sha256sum -c -\n"
        "ENV PYTHONPATH=/tests\nWORKDIR /tests\n",
        encoding="utf-8",
        newline="\n",
    )


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
            newline="\n",
        )
        (root / "instruction.md").write_text(
            task.prompt + "\n\nWrite your final answer to /app/answer.txt (UTF-8).\n",
            encoding="utf-8",
            newline="\n",
        )
        (root / "environment").mkdir()
        (root / "environment" / "Dockerfile").write_text(
            f"FROM {BASE_IMAGE}\nWORKDIR /app\n", encoding="utf-8", newline="\n"
        )
        write_json(tests / "reference.json", private_record(task))
        # Package source is bundled only into the trusted verifier build context.
        for relative, content in checker.items():
            target = tests / "mathematics_rl" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        # Docker Desktop kernels may lack nftables FIB_INET. Native Compose
        # network_mode:none enforces isolation without Harbor's egress sidecar.
        (tests / "docker-compose.yaml").write_text(
            "services:\n  main:\n    network_mode: none\n", encoding="utf-8", newline="\n"
        )
        (tests / "test.sh").write_text(
            "#!/bin/sh\nset -eu\nexport PYTHONPATH=/tests\n"
            "python -m mathematics_rl.adapters.harbor\n",
            encoding="utf-8",
            newline="\n",
        )
        build_verifier_payload(tests)
        solution = root / "solution"
        solution.mkdir()
        write_json(solution / "answer.json", task.answer)
        (solution / "solve.sh").write_text(
            "#!/bin/sh\nset -eu\nmkdir -p /app\npython - <<'PY'\n"
            "import json\nfrom pathlib import Path\n"
            "Path('/app/answer.txt').write_text(json.loads("
            "Path('/solution/answer.json').read_text(encoding='utf-8')), encoding='utf-8')\nPY\n",
            encoding="utf-8",
            newline="\n",
        )
        manifest.append({"directory": root.name, "task_id": task.id, "module": task.module})
    write_json(output / "selection.json", {"framework": "harbor", "tasks": manifest})
    return manifest


def verify_task(reference, answer, log_dir):
    """Run in the separate verifier. Missing/malformed agent artifacts earn zero."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    reward_file = log_dir / "reward.txt"
    # Harbor consumes a reward file even when test.sh exits nonzero. Source and
    # infrastructure failures must leave no score, including stale ones.
    reward_file.unlink(missing_ok=True)
    task = Example(**json.loads(Path(reference).read_text(encoding="utf-8")))
    answer = Path(answer)
    with Grader() as grader:
        # Validate the source even if the model produced no artifact.
        checked_grade(grader, task, task.answer)
        try:
            info = answer.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_COMPLETION * 4:
                raise ValueError("Invalid answer artifact")
            completion = answer.read_bytes()[: MAX_COMPLETION * 4 + 1].decode("utf-8")
        except (OSError, ValueError):
            write_json(log_dir / "grading.json", {"reward": 0.0, "status": "invalid_artifact"})
            reward_file.write_text("0\n", encoding="utf-8", newline="\n")
            return 0.0
        result = checked_grade(grader, task, completion)
    write_json(log_dir / "grading.json", result.to_dict())
    reward_file.write_text(f"{result.reward}\n", encoding="utf-8", newline="\n")
    return result.reward


if __name__ == "__main__":
    verify_task("/tests/reference.json", "/app/answer.txt", "/logs/verifier")
