"""Run real vf-eval against a local scripted endpoint; this is not a model benchmark."""

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CASES = [
    ("arithmetic__add_or_sub", "Compute 1+1.", "2", "2", 1),
    ("comparison__sort", "Sort 3, 1, 2.", "1, 2, 3", "3, 2, 1", 0),
    ("algebra__polynomial_roots", "Factor x**2-1.", "(x-1)*(x+1)", "x**2-1", 0),
    (
        "polynomials__simplify_power",
        "Simplify x**(2/4), assuming x is positive.",
        "x**(1/2)",
        r"\sqrt{x}",
        1,
    ),
    ("numbers__is_prime", "Is 7 prime?", "True", "False", 0),
    ("arithmetic__simplify_surd", "Simplify sqrt(12).", "2*sqrt(3)", "sqrt(12)", 0),
]


def verify_trace_files(output):
    episodes = [
        json.loads(line)
        for path in (output / "runs").rglob("traces.jsonl")
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    assert len(episodes) == len(CASES), f"Expected {len(CASES)} episodes, got {len(episodes)}"
    expected = {case[1]: case[4] for case in CASES}
    rewards = {}
    for episode in episodes:
        assert episode["ok"] and not episode["errors"], episode
        assert len(episode["traces"]) == 1, episode
        trace = episode["traces"][0]
        question = episode["task"]["data"]["question"]
        assert trace["task"]["data"]["question"] == question
        reward = trace["rewards"]["correct"]
        actual = reward["score"] * reward["weight"]
        assert not trace["errors"] and trace["ok"] and len(trace["calls"]) == 1, trace
        assert actual == expected[question], trace
        rewards[question] = actual
    assert set(rewards) == set(expected)
    report = {
        "type": "scripted_endpoint_real_verifiers_transport_smoke",
        "not_a_model_benchmark": True,
        "traces": len(episodes),
        "rewards": rewards,
        "no_remote_result_upload": True,
        "gpu_used": False,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="A new, empty output directory (never cleans existing runs)",
    )
    parser.add_argument(
        "--verify-existing",
        action="store_true",
        help="Only verify traces already produced by this smoke test",
    )
    args = parser.parse_args()
    if args.verify_existing:
        print(json.dumps(verify_trace_files(args.output), indent=2))
        return
    args.output.mkdir(parents=True, exist_ok=False)
    rows = [
        {
            "module": module,
            "question": question,
            "answer": answer,
            "language": "en",
            "category": "interpolate",
        }
        for module, question, answer, _, _ in CASES
    ]
    source = args.output / "source.ndjson"
    source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            content = str(request["messages"][-1]["content"])
            case = next(case for case in CASES if content.endswith(case[1]))
            received.append(case[1])
            response = {
                "id": "chatcmpl-local-smoke",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "scripted-smoke",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": case[3]},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 32,
                    "completion_tokens": 8,
                    "total_tokens": 40,
                },
            }
            if request.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                chunk = {
                    "id": response["id"],
                    "object": "chat.completion.chunk",
                    "created": response["created"],
                    "model": "scripted-smoke",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": case[3]},
                            "finish_reason": None,
                        }
                    ],
                }
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
                chunk["choices"] = [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                chunk["usage"] = response["usage"]
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n").encode())
            else:
                payload = json.dumps(response).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    command = [
        str(Path(sys.executable).parent / "vf-eval"),
        "mathematics-rl",
        "--env.taskset.language",
        "en",
        "--env.taskset.source",
        str(source.absolute()),
        "--client.base-url",
        f"http://127.0.0.1:{server.server_port}/v1",
        "--client.api-key-var",
        "MATHEMATICS_UNUSED_SMOKE_KEY",
        "--model",
        "scripted-smoke",
        "--env.agent.runtime.type",
        "subprocess",
        "--env.agent.harness.id",
        "null",
        "--env.agent.timeout.rollout",
        "60",
        "--client.timeout.read",
        "30",
        "--max-concurrent",
        "2",
        "-n",
        str(len(CASES)),
        "--no-push",
        "--no-rich",
        "--output-dir",
        str((args.output / "runs").absolute()),
    ]
    try:
        with (args.output / "vf-eval.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
            )
            try:
                code = process.wait(timeout=300)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                raise
            if code:
                raise subprocess.CalledProcessError(code, command)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    expected = {case[1]: case[4] for case in CASES}
    assert set(received) == set(expected)
    report = verify_trace_files(args.output)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
