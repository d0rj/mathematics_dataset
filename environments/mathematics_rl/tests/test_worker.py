import sys

import mathematics_rl.worker as worker_module
from mathematics_rl.worker import Grader


def slow_worker_command():
    return [
        sys.executable,
        "-u",
        "-c",
        "import sys,time; print('{\"ready\":true}',flush=True); "
        "sys.stdin.readline(); time.sleep(60)",
    ]


def test_worker_reuse_timeout_termination_and_recovery(monkeypatch):
    with Grader(timeout=3) as grader:
        assert grader.grade("arithmetic__add_or_sub", "Compute.", "2", "2").reward == 1
        original_pid = grader._process.pid
        assert grader.grade("arithmetic__add_or_sub", "Compute.", "2", "3").reward == 0
        assert grader._process.pid == original_pid
        grader.close()
        original_worker = worker_module.worker_command
        monkeypatch.setattr(worker_module, "worker_command", slow_worker_command)
        grader.timeout = 0.05
        result = grader.grade("arithmetic__add_or_sub", "Compute.", "2", "3")
        assert result.status == "timeout"
        assert grader._process is None
        monkeypatch.setattr(worker_module, "worker_command", original_worker)
        grader.timeout = 3
        assert grader.grade("arithmetic__add_or_sub", "Compute.", "0", "0").reward == 1
        assert grader._process.pid != original_pid
    assert grader._process is None


def test_reference_timeout_is_a_source_error(monkeypatch):
    monkeypatch.setattr(worker_module, "worker_command", slow_worker_command)
    with Grader(timeout=0.05) as grader:
        result = grader.grade("arithmetic__add_or_sub", "Compute.", "2", "2")
        assert result.status == "invalid_reference"
        assert grader._process is None
