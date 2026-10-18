"""Reusable isolated Python worker, with bounded I/O and enforceable wall-clock deadlines."""

import atexit
import json
import queue
import subprocess
import sys
import threading
from collections import OrderedDict

from .grading import MAX_COMPLETION, Grade


def worker_command():
    # A module entrypoint avoids multiprocessing.spawn re-importing a heavyweight
    # vf-eval / trainer __main__ inside every mathematical checker process.
    return [sys.executable, "-u", "-m", "mathematics_rl.worker_entry"]


def _read(process, replies):
    try:
        for line in process.stdout:
            if len(line) > 100_000:
                raise ValueError("Oversized worker response")
            replies.put(json.loads(line))
    except (OSError, ValueError) as error:
        replies.put({"error": type(error).__name__})
    finally:
        replies.put({"error": "WorkerEOF"})


def _write(process, requests, replies):
    try:
        while True:
            payload = requests.get()
            if payload is None:
                return
            process.stdin.write(payload + "\n")
            process.stdin.flush()
    except (OSError, ValueError) as error:
        replies.put({"error": type(error).__name__})


class Grader:
    """One serialized process per evaluator; timed-out workers are killed and replaced.

    I/O threads only transfer bounded JSON. Symbolic operations run exclusively in
    the child; its 3s deadline includes request writing and response reading.
    """

    def __init__(self, timeout: float = 3.0):
        if not 0 < timeout <= 30:
            raise ValueError("Scoring timeout must be between 0 and 30 seconds")
        self.timeout = timeout
        self._process = None
        self._reader = self._writer = None
        self._requests = self._replies = None
        self._lock = threading.Lock()
        self._validated = OrderedDict()
        atexit.register(self.close)

    def _stop(self):
        if self._process is None:
            return
        process = self._process
        if self._requests is not None:
            self._requests.put(None)
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        for thread in (self._reader, self._writer):
            if thread is not None:
                thread.join(timeout=2)
        for stream in (process.stdin, process.stdout):
            if stream:
                stream.close()
        self._process = self._reader = self._writer = None
        self._requests = self._replies = None

    def _start(self):
        if self._process is not None and self._process.poll() is None:
            return
        self._stop()
        self._process = subprocess.Popen(
            worker_command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        self._requests, self._replies = queue.Queue(), queue.Queue()
        self._reader = threading.Thread(
            target=_read, args=(self._process, self._replies), daemon=True
        )
        self._writer = threading.Thread(
            target=_write, args=(self._process, self._requests, self._replies), daemon=True
        )
        self._reader.start()
        self._writer.start()
        try:
            ready = self._replies.get(timeout=30)
        except queue.Empty:
            ready = None
        if ready != {"ready": True}:
            self._stop()
            raise RuntimeError(f"Mathematics grader worker failed to start: {ready}")

    def _request(self, payload, kind):
        self._requests.put(json.dumps(payload, ensure_ascii=False))
        try:
            message = self._replies.get(timeout=self.timeout)
        except queue.Empty:
            self._stop()
            return Grade(0.0, "timeout", kind)
        if "grade" not in message:
            self._stop()
            raise RuntimeError(f"Mathematics grader worker failed: {message}")
        return Grade(**message["grade"])

    def grade(self, module: str, question: str, reference: str, completion: str) -> Grade:
        from .catalog import contract_for

        kind = contract_for(module, question).kind
        with self._lock:
            self._start()
            key = (module, question, reference)
            if key not in self._validated:
                validation = self._request((module, question, reference, reference), kind)
                if validation.status != "correct":
                    return Grade(0.0, "invalid_reference", kind)
                self._validated[key] = True
                if len(self._validated) > 4096:
                    self._validated.popitem(last=False)
            if not isinstance(completion, str) or len(completion) > MAX_COMPLETION:
                return Grade(0.0, "parse_error", kind)
            if completion == reference:
                return Grade(1.0, "correct", kind, reference)
            return self._request((module, question, reference, completion), kind)

    def close(self):
        with self._lock:
            self._stop()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
