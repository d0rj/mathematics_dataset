"""Run real Harbor oracle and negative trials using sibling Docker containers."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from scenarios import harbor_verify, representatives, rows, save

from mathematics_rl.adapters.harbor import build_verifier_payload, export_tasks


def prepare(tasks, path, prefix, negative=False):
    manifest = export_tasks(tasks, path)
    for item in manifest:
        task_dir = path / item["directory"]
        task_dir = task_dir.rename(task_dir.with_name(prefix + "-" + task_dir.name))
        item["directory"] = task_dir.name
        config_path = task_dir / "task.toml"
        config = config_path.read_text().replace(
            'name = "mathematics/', f'name = "mathematics/{prefix}-'
        )
        config_path.write_text(config, encoding="utf-8", newline="\n")
        solve = task_dir / "solution/solve.sh"
        text = solve.read_text()
        # These paths are mounted by the verifier only, not by the agent image.
        text = text.replace(
            "set -eu\n",
            "set -eu\ntest ! -e /tests/reference.json\ntest ! -d /tests/mathematics_rl\n",
            1,
        )
        solve.write_text(text, encoding="utf-8", newline="\n")
        check = task_dir / "tests/test.sh"
        # Check the actual private build payload, not just the host export.
        identity_check = (
            "import json; from pathlib import Path; "
            "r=json.loads(Path('/tests/reference.json').read_text()); "
            f"assert r['id'] == {item['task_id']!r}, r; "
            "print('Verifier task:', r['id'], 'reference:', repr(r['answer']))"
        )
        check.write_text(
            check.read_text().replace(
                "set -eu\n",
                'set -eu\npython -c "from pathlib import Path; '
                "assert len(Path('/proc/net/route').read_text().splitlines()) == 1\"\n"
                f'python -c "{identity_check}"\n',
                1,
            ),
            encoding="utf-8",
            newline="\n",
        )
        build_verifier_payload(task_dir / "tests")
        if negative:
            save(task_dir / "solution/answer.json", "intentionally invalid mathematics answer")
    return manifest


def run(tasks, root, prefix, label, expected, invalid_source=False, agent="oracle"):
    task_dir = root / label / "tasks"
    manifest = prepare(tasks, task_dir, prefix + "-" + label, negative=not expected)
    if invalid_source:
        for item in manifest:
            reference = task_dir / item["directory"] / "tests/reference.json"
            value = json.loads(reference.read_text())
            value["answer"] = "invalid source reference"
            save(reference, value)
            build_verifier_payload(reference.parent)
    job_name = prefix + "-" + label
    jobs_dir = root / "jobs"
    command = [
        "harbor",
        "run",
        "--path",
        str(task_dir),
        "--agent",
        agent,
        "--jobs-dir",
        str(jobs_dir),
        "--job-name",
        job_name,
        "--n-concurrent",
        "4",
        "--max-retries",
        "0",
        "--no-export-push",
        "--yes",
    ]
    with (root / f"{label}.log").open("w", encoding="utf-8") as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=3000)
    if invalid_source:
        results = [json.loads(p.read_text()) for p in (jobs_dir / job_name).glob("*/result.json")]
        assert len(results) == len(manifest)
        for result in results:
            assert result["exception_info"]["exception_type"] == "RewardFileNotFoundError", result
            assert result["verifier_result"] is None, result
        return {"episodes": len(results), "source_errors_have_no_reward": True}
    result = harbor_verify(jobs_dir / job_name, expected)
    assert result["episodes"] == len(manifest)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    root = args.work / "run"
    root.mkdir(exist_ok=False)
    results = Path("/results")
    results.mkdir(exist_ok=True)
    tasks = [task for lang in ("en", "ru") for _, task in representatives(lang)]
    if args.limit:
        tasks = tasks[: args.limit]
    try:
        positive = run(tasks, root, args.prefix, "positive", 1)
        print(f"Harbor accepted {positive['episodes']} oracle answers", flush=True)
        negatives = []
        seen = set()
        for lang in ("en", "ru"):
            for task in rows(lang):
                if (lang, task.kind) not in seen:
                    negatives.append(task)
                    seen.add((lang, task.kind))
        if args.limit:
            negatives = negatives[: args.limit]
        negative = run(negatives, root, args.prefix, "negative", 0)
        print(f"Harbor rejected {negative['episodes']} wrong answers", flush=True)
        source_error = run(tasks[:1], root, args.prefix, "invalid-source", 0, invalid_source=True)
        missing_output = run(tasks[:1], root, args.prefix, "missing-output", 0, agent="nop")
        save(
            results / "report.json",
            {
                "framework": "harbor",
                "passed": True,
                "oracle_episodes": positive["episodes"],
                "incorrect_episodes": negative["episodes"],
                "module_language_cases": [
                    {"module": t.module, "language": t.language} for t in tasks
                ],
                "negative_kinds": sorted({t.kind for t in negatives}),
                "separate_verifier": True,
                "agent_cannot_read_verifier_paths": True,
                "source_error": source_error,
                "missing_output": {"episodes": missing_output["episodes"], "reward": 0},
                "positive": positive,
                "negative": negative,
            },
        )
    finally:
        # Preserve native results even on error, before the runner removes its volume.
        shutil.copytree(root, results / "native", dirs_exist_ok=True)


if __name__ == "__main__":
    main()
