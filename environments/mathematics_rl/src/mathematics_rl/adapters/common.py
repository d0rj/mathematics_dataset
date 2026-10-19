"""Bounded selection, private task records and one-attempt episode semantics."""

import json
from dataclasses import asdict
from itertools import islice
from pathlib import Path

from ..data import GRADING_VERSION, examples
from ..worker import Grader

MAX_TASKS = 100_000


def select_tasks(*, limit=100, **kwargs):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_TASKS:
        raise ValueError(f"limit must be an integer between 1 and {MAX_TASKS}")
    mode = kwargs.pop("mode", "interpolate")
    modes = ("train", "interpolate", "extrapolate") if mode == "all" else (mode,)
    rows = (row for selected in modes for row in examples(mode=selected, **kwargs))
    tasks = tuple(islice(rows, limit))
    if not tasks:
        raise ValueError("No tasks match the selection")
    return tasks


def public_task(task):
    return {
        "task_id": task.id,
        "prompt": task.prompt,
        "module": task.module,
        "category": task.category,
        "language": task.language,
        "dataset_revision": task.revision,
        "grading_version": GRADING_VERSION,
    }


def read_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8")) if path else {}
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object of selection arguments")
    return config


def checked_grade(grader, task, completion):
    result = grader.grade(task.module, task.question, task.answer, completion)
    if result.status == "invalid_reference":
        raise ValueError(f"Invalid source reference for task {task.id}")
    return result


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def private_record(task):
    return asdict(task)


class OneTurnSession:
    """A private, isolated episode. Exactly one scored submission after each reset."""

    def __init__(self, tasks, timeout=3):
        self.tasks = tuple(tasks)
        if not self.tasks:
            raise ValueError("An environment needs at least one task")
        self.grader = Grader(timeout)
        self.task = None
        self.done = False
        self._next = 0

    def reset(self, *, seed=None, task_index=None):
        if task_index is None:
            task_index = self._next if seed is None else seed % len(self.tasks)
        if isinstance(task_index, bool) or not isinstance(task_index, int):
            raise ValueError("task_index must be an integer")
        if not 0 <= task_index < len(self.tasks):
            raise ValueError("task_index is out of range")
        self.task = self.tasks[task_index]
        self._next = (task_index + 1) % len(self.tasks)
        self.done = False
        return public_task(self.task)

    def submit(self, completion):
        if self.task is None:
            raise RuntimeError("Reset the environment before submitting an answer")
        if self.done:
            raise RuntimeError("Episode is terminal; reset before another submission")
        if not isinstance(completion, str):
            raise TypeError("Answer must be a string")
        result = checked_grade(self.grader, self.task, completion)
        self.done = True
        return result

    def close(self):
        self.grader.close()
