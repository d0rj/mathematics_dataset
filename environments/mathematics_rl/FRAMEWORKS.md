# Framework adapters

All adapters use the same 70-module catalog, pinned dataset loader and isolated
typed checker. Both languages and all five categories are supported. This is a
single-response mathematics task: a reset selects a problem, one final response
earns 0 or 1, then the episode ends. An RL trainer supplies its own model and updates.

Commands run from this package directory (`environments/mathematics_rl` in the
source checkout, `mathematics-env/rl` in the Hub download).

| Framework | Pinned release | Runtime | Adapter |
|---|---|---|---|
| Verifiers | 0.4.0, v1 API | Linux/macOS/WSL, Python 3.11.4+ | `MathematicsTaskset`, `MathematicsEnv` |
| Harbor | 0.24.0 | Python 3.12+, Docker for trials | exported native task directories, separate verifier |
| OpenEnv | 0.9.0 (`openenv`, not legacy `openenv-core`) | Python 3.11.4+ | typed `Environment`, `EnvClient`, HTTP/WebSocket server |
| NeMo Gym | 0.7.0 | Linux/WSL, Python 3.13.14+ | `SimpleResourcesServer`, native `/verify` and JSONL rows |
| AgentEnv (Scale AI) | 0.9.1334 | Linux/macOS/WSL, Python 3.11.4+ | `Task`, `EpisodeSpec`, registered `mathematics_grade` step |

Use separate virtual environments for each framework. Verifiers pins MCP 2.0.0;
the other SDKs use MCP 1.x. These extras deliberately conflict in `uv.lock`.
Installing the checker alone no longer installs a framework. Select its extra
explicitly; `uv sync --locked --extra verifiers` restores the original v1 setup.
Do not use `--all-extras`.

## Selection and reproducibility

Exports and servers consume a **bounded selection**, default 100, allowed 1–100000.
They never materialize the 125M-row corpus. `--language`, `--module` (repeatable),
`--mode`, `--category`, `--revision`, `--seed`, `--shuffle-buffer` use the common loader.
`--mode all` is for audits; training should explicitly select `train`. Existing
output directories are refused, preserving reviewed exports. Export private
records belong to the evaluator, never in a solver prompt or accessible agent mount.

Local NDJSON/Parquet and Hub loading are interchangeable. For offline examples,
append `--source tests/fixtures/generated_en.ndjson --language en`; these fixtures
are regression data, not the complete published dataset. Pin the source, filters,
seed, language and revision to reproduce task IDs and selection order.

## Harbor

```bash
UV_PROJECT_ENVIRONMENT=.venv-harbor uv sync --locked --extra harbor --python 3.13
UV_PROJECT_ENVIRONMENT=.venv-harbor uv run --extra harbor mathematics-rl export harbor \
  --language en --mode interpolate --module arithmetic__div --limit 10 \
  --output outputs/harbor
UV_PROJECT_ENVIRONMENT=.venv-harbor uv run --extra harbor harbor run \
  --path outputs/harbor --agent oracle --n-concurrent 1
```

Replace `--agent oracle` with your model agent for evaluation/training rollouts.
The oracle is a **reference acceptance test**, not model evidence. Each directory
contains `task.toml` schema 1.4, `instruction.md`, the agent environment,
`solution/solve.sh`, and `tests/test.sh` with its own Dockerfile. The agent writes
`/app/answer.txt`. Harbor copies that configured artifact into a **separate verifier
container**; references and checker code are present only there. Missing, oversized,
non-UTF-8 or non-regular answer files earn zero. Checker source is bundled with
the task; the verifier image installs pinned SymPy. Image build needs internet.
The base `python:3.13-slim` image is a mutable tag; archive the built image/digest
when reproducing an experiment. Do not switch to shared verification for an
untrusted shell agent: it could read references or alter the checker.

## OpenEnv

```bash
UV_PROJECT_ENVIRONMENT=.venv-openenv uv sync --locked --extra openenv
UV_PROJECT_ENVIRONMENT=.venv-openenv uv run --extra openenv mathematics-openenv \
  --config integrations/openenv/config.example.json --port 8000
```

The example configuration selects two offline English arithmetic problems. Supply
a JSON object of selection arguments for Hub use, for example
`{"language":"ru","mode":"train","modules":["arithmetic__div"],"limit":1000}`.
`grading_timeout` optionally overrides the common 3-second scoring deadline.

```python
from mathematics_rl.adapters.openenv import MathematicsAction, MathematicsClient

with MathematicsClient(base_url="http://127.0.0.1:8000") as client:
    initial = client.reset(seed=42)
    print(initial.observation.prompt)
    final = client.step(MathematicsAction(answer="your model's final response"))
    print(final.reward, final.done)
```

The same client supports `async with` and awaited calls. Reset accepts an optional
`task_index` into the bounded selection; a seed selects `seed % len(tasks)`, and
unseeded resets cycle deterministically. Each concurrent WebSocket connection
owns its episode state and checker, with at most eight active sessions. State and
observations contain no reference or private content hash. A second submission
after termination is rejected. Native `/schema`, `/health`, `/reset`, `/step`,
`/state` and `/ws` are supplied by OpenEnv. Use WebSocket sessions for isolation.

`integrations/openenv/openenv.yaml`, `app.py` and `Dockerfile` are also provided.
Build from this package root with
`docker build -f integrations/openenv/Dockerfile -t mathematics-openenv:0.2.0 .`.
This creates a runnable image, not a published Hugging Face Space.

## NeMo Gym

```bash
UV_PROJECT_ENVIRONMENT=.venv-nemo uv sync --locked --extra nemo --python 3.13.14
UV_PROJECT_ENVIRONMENT=.venv-nemo uv run --extra nemo mathematics-rl export nemo \
  --language ru --mode train --module arithmetic__div --limit 100 \
  --output outputs/nemo
UV_PROJECT_ENVIRONMENT=.venv-nemo uv run --extra nemo mathematics-nemo --port 8001
```

`tasks.jsonl` follows Gym's native run input: `responses_create_params.input`
contains only the public user prompt, and `math_example` contains the trusted
private task record. Pass the former to your policy model; send the full row plus
its Responses API `response` to `/verify`. The final assistant message is scored;
reasoning items, tool outputs and preceding assistant messages are excluded.
The reply uses `BaseVerifyResponse`, with scalar `reward`, `task_id`,
`grading_status` and `answer_kind`. It does not echo the private task record.

```python
import json
import httpx

row = json.loads(open("outputs/nemo/tasks.jsonl", encoding="utf-8").readline())
# response = your_policy.responses.create(**row["responses_create_params"])
# scored = httpx.post("http://127.0.0.1:8001/verify",
#                     json={**row, "response": response.model_dump(mode="json")}).json()
```

For the native Gym supervisor, `integrations/nemo/app.py` is an entrypoint shim.
Place it in a resource-server folder in your Gym checkout, install this package
in that server's environment, and use the supplied `config.yaml` as a starting
point for your model and `simple_agent` configuration. When Gym supplies
`NEMO_GYM_CONFIG_DICT`, `mathematics-nemo` uses `run_webserver()` and its native
config/client instead of the standalone launcher. Verification is stateless and
declares `REVERIFY_MODE=stateless`; Gym supplies session and aggregate-metric routes.
This adapter needs no Ray, judge model, GPU or external sandbox. Treat `/verify`
as a trusted evaluator interface: callers must not replace the reference record.

## AgentEnv

This is [`scaleapi/agentenv-framework`](https://github.com/scaleapi/agentenv-framework),
the project linked by the Hub's `agentenv` tag. It is unrelated to AgentGym.

```bash
UV_PROJECT_ENVIRONMENT=.venv-agentenv uv sync --locked --extra agentenv
UV_PROJECT_ENVIRONMENT=.venv-agentenv uv run --extra agentenv agent-env plugin check
UV_PROJECT_ENVIRONMENT=.venv-agentenv uv run --extra agentenv mathematics-rl export agentenv \
  --language en --mode train --module arithmetic__div --limit 10 \
  --output outputs/agentenv
```

The installed distribution registers `mathematics_grade` in `agent_env.task_steps`.
Each native task deploys a `solver` role, prompts it once, and grades that prompt's
final response. The reward is recorded in
`context.metadata["verifications"]["grade"]["score"]`, the same native format used
by AgentEnv verifiers. Missing/ambiguous prompt responses, agent execution failures
and invalid references raise infrastructure/source errors, instead of assigning
a misleading model score. Private reference records occur only in grader steps.

For an external RL loop, the native episode API needs no Docker or hosted agent:

```python
from agent_env.task import EpisodeSpec
from mathematics_rl.adapters.agentenv import make_task
from mathematics_rl.adapters.common import select_tasks

async def episode(policy):
    example = select_tasks(language="en", mode="train", limit=1)[0]
    run = await EpisodeSpec.from_task(make_task(example)).start()
    try:
        while (turn := await run.next_turn()) is not None:
            await turn.end(response=await policy(turn.prompt))
        return await run.result()
    except BaseException:
        await run.abandon("trainer interrupted")
        raise
```

AgentEnv uses configured local stores for episode records. For a deployed model
agent, export with `--agent-id YOUR_REGISTERED_AGENT --model YOUR_MODEL`, then use
the resulting native bundle with `agent-env run ./outputs/agentenv --task TASK_ID`.
That path uses your configured sandbox/agent backend and may require Docker.
The external-episode path above supplies model responses directly.

## Verification boundaries and sources

See [VALIDATION.md](VALIDATION.md) for measured checks and outstanding deployment
boundaries. SDK/protocol tests and oracle trials do not measure a real model or
an RL training gain. The HF card tags identify adapter compatibility; use the
specific preparation and launch commands here, because the dataset stores a
reusable package plus Parquet rather than millions of pre-exported tasks.

API sources checked 2026-10-19:
[Harbor](https://github.com/harbor-framework/harbor/tree/357c5e74020fc0890d69fb3a7db610896b9ce57d),
[OpenEnv](https://github.com/huggingface/OpenEnv/tree/55347f62e22f83a618b49ee984e2f684b69d8fbd),
[NeMo Gym](https://github.com/NVIDIA-NeMo/Gym/tree/b3103ea8ac462e4ca30aa06fb151198271b8e3dd),
[AgentEnv](https://github.com/scaleapi/agentenv-framework/tree/7ca617eb002055af0fd846f0c9c6f3758519631e),
and [HF RL environment metadata](https://huggingface.co/docs/hub/datasets-cards#declare-an-rl-environment-dataset).
Released versions in the table are pinned independently of those source snapshots.
