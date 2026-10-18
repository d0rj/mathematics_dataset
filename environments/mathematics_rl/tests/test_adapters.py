"""Shared episode and artifact boundaries, independent of optional framework SDKs."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from mathematics_rl.adapters.common import OneTurnSession, public_task, select_tasks
from mathematics_rl.adapters.harbor import export_tasks, verify_task
from mathematics_rl.catalog import MODULES

FIXTURES = Path(__file__).absolute().parent / "fixtures"


def module_examples():
    result = []
    for language in ("en", "ru"):
        seen = set()
        for row in select_tasks(
            source=str(FIXTURES / f"generated_{language}.ndjson"),
            language=language,
            mode="all",
            limit=10_000,
        ):
            if row.module not in seen:
                result.append(row)
                seen.add(row.module)
        assert seen == set(MODULES)
    return result


@pytest.fixture(scope="module")
def all_module_examples():
    return module_examples()


@pytest.mark.parametrize("limit", [0, -1, 100001, True, 1.5])
def test_bounded_selection(limit):
    with pytest.raises(ValueError, match="limit"):
        select_tasks(limit=limit)


def test_episode_matrix_and_privacy(all_module_examples):
    session = OneTurnSession(all_module_examples)
    try:
        with pytest.raises(RuntimeError, match="Reset"):
            session.submit("0")
        for index, task in enumerate(all_module_examples):
            public = session.reset(task_index=index)
            assert public == public_task(task)
            assert "answer" not in public and "content_hash" not in public
            assert task.answer not in public.values()
            assert session.submit(task.answer).reward == 1
            with pytest.raises(RuntimeError, match="terminal"):
                session.submit(task.answer)
            assert session.reset(seed=index)["task_id"] == task.id
            assert session.submit("not a mathematical answer").reward == 0
        with pytest.raises(ValueError, match="range"):
            session.reset(task_index=len(all_module_examples))
        with pytest.raises(ValueError, match="integer"):
            session.reset(task_index=True)
    finally:
        session.close()


def test_bad_reference_is_a_source_error(all_module_examples):
    session = OneTurnSession([replace(all_module_examples[0], answer="invalid reference")])
    try:
        session.reset()
        with pytest.raises(ValueError, match="source"):
            session.submit("0")
        assert not session.done
    finally:
        session.close()


def test_harbor_export_and_artifact_verification(tmp_path, all_module_examples):
    task = all_module_examples[0]
    output = tmp_path / "harbor"
    manifest = export_tasks([task], output)
    root = output / manifest[0]["directory"]
    with pytest.raises(FileExistsError):
        export_tasks([task], output)
    assert "separate" in (root / "task.toml").read_text()
    assert "reference" not in (root / "environment/Dockerfile").read_text()
    assert not list((root / "environment").glob("*.json"))
    answer = tmp_path / "answer.txt"
    logs = tmp_path / "logs"
    reference = root / "tests/reference.json"
    assert verify_task(reference, answer, logs) == 0
    answer.write_text(task.answer, encoding="utf-8")
    assert verify_task(reference, answer, logs) == 1
    answer.write_text("a deliberately incorrect answer", encoding="utf-8")
    assert verify_task(reference, answer, logs) == 0
    assert float((logs / "reward.txt").read_text()) == 0
    answer.write_bytes(b"\xff")
    assert verify_task(reference, answer, logs) == 0
    assert json.loads((logs / "grading.json").read_text())["status"] == "invalid_artifact"
