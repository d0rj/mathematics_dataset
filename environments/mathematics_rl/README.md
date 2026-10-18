# Mathematics RL

A mathematics RL environment for **Verifiers v1, Harbor, OpenEnv, NeMo Gym and
AgentEnv**, covering all **70 modules** of
[`d0rj/mathematics_dataset`](https://huggingface.co/datasets/d0rj/mathematics_dataset).
The Verifiers API is provided by pinned `verifiers==0.4.0`. Each episode is one
tool-less model response followed by a deterministic exact typed reward in `{0, 1}`.
English and Russian use the same scoring rules and separate language splits.
See [FRAMEWORKS.md](FRAMEWORKS.md) for the four additional adapters, pinned SDK
versions, bounded exports, native servers/clients and AgentEnv episode loops.
Install each framework in a separate environment: Verifiers' MCP major version
conflicts with the other SDKs. The base package contains only the checker/loader.

## Installation

Commands below run from the package directory: `cd environments/mathematics_rl`
in the source checkout, or `cd mathematics-env/rl` after the Hub download.

Full Verifiers execution requires Linux, macOS or WSL: the pinned upstream runtime
imports `fcntl`. The standalone checker and its unit tests also work on Windows.
Scoring needs no GPU, Docker, hosted sandbox or paid service.

```bash
uv sync --locked --extra verifiers
uv run mathematics-rl catalog
uv run mathematics-rl grade \
  --module arithmetic__div --question 'Divide 1 by 2.' --reference 1/2 --answer '0.5'
```

For full integration tests from PowerShell (adjust the checkout path):

```powershell
wsl -d Ubuntu-24.04 -- bash /mnt/d/Projects/mathematics_dataset/scripts/run_rl_tests.sh
```

The script keeps Linux dependencies in `.venv-wsl`, separately from Windows `.venv`.

## Evaluation

Use an OpenAI-compatible model endpoint. Configure credentials locally through
the environment variable named by `--client.api-key-var`. Do not place credentials
in commands, TOML files, dataset cards or traces. Local endpoints may accept `EMPTY`.

```bash
uv run --extra verifiers vf-eval mathematics-rl \
  --env.taskset.language ru --env.taskset.mode interpolate \
  --env.taskset.modules '["arithmetic__add_or_sub"]' \
  --model YOUR_MODEL --client.base-url http://127.0.0.1:8000/v1 \
  --client.api-key-var LOCAL_LLM_API_KEY -n 20 --no-push
```

The default `MathematicsEnv` is one agent with the `null` harness, one model turn
and local `subprocess` runtime. It provides no tools. Override the runtime with
normal Verifiers configuration when needed. Use `--no-push` for local results;
upstream otherwise defaults to uploading completed evaluations to Prime Intellect.

`--env.taskset.mode train` selects only `train-easy`, `train-medium`, `train-hard`.
`interpolate` and `extrapolate` are separate evaluation modes. For example,
`--env.taskset.categories '["train-hard"]'` selects one difficulty within train;
cross-mode categories are rejected. See [MODULES.md](MODULES.md) for all module names.

The pinned dataset revision is `d9f78d0665b3a13dad21c6830b9b358c8a25ae74`.
Overriding it requires another full commit hash, never a moving branch. The loader
uses lazy streaming with Parquet category/module predicate pushdown. Choose modules
for small pilots; the existing 125M rows do not need to be rewritten.

### Bounded sampling and resume

`-n` bounds consumed tasks. Do not use unbounded `-s` over the whole corpus: the
framework's exact shuffle materializes its input. Bound it first:

```bash
uv run --extra verifiers vf-eval mathematics-rl \
  --env.taskset.language en --select.include.idx 0:1000 -s -n 20 \
  --model YOUR_MODEL --client.base-url http://127.0.0.1:8000/v1 --no-push
```

Alternatively use `--env.taskset.shuffle-buffer 1000 --env.taskset.seed 42` for
a bounded approximate streaming shuffle. Preserve revision, filters, seed and
buffer size when resuming. IDs combine source/config, source position and content
hash: repeated identical rows have distinct keys, and subsequent CLI selection
preserves IDs. Changing source filters can change IDs; `content_hash` supports
cross-selection duplicate analysis.

### Offline sources and reference checks

`--env.taskset.source rows.ndjson` (or `.parquet`) reads the same four string
columns locally. A local file may include `language`; otherwise it is inferred
from the selected language. On the Hub, language comes from the split name.
Local examples are marked `local`, not incorrectly attributed to the Hub revision.

```bash
uv run mathematics-rl self-check \
  --source tests/fixtures/generated_ru.ndjson \
  --language ru --mode all --limit 0 --require-all-modules --output reference-check.json
```

This checks reference/verifier compatibility, not independent correctness of
every reference. Invalid source references fail loudly instead of becoming model
errors. Split separation does not prove that duplicate questions or cross-language
mathematical overlap are absent.

## Reward and RL

[GRADING.md](GRADING.md) specifies extraction, accepted notation, form requirements,
resource limits and the named-value comparison convention. References stay in
immutable `TaskData` on the evaluator and are not inserted into the solver prompt.
Traces include `correct` reward, `accuracy`, `parse_error`, `grading_timeout`,
answer kind and grading version.

Use the exported environment with a Verifiers v1-compatible trainer and `mode=train`.
The trainer supplies trajectories, tokenization, log-probabilities, grouping and
weight updates. This package implements no optimizer and claims no training gain.
Keep both evaluation categories out of the training mixture.

## Tests and publication

```bash
uv run pytest tests -q
uv run ruff check src tests
uv build .
```

See [VALIDATION.md](VALIDATION.md) for evidence and fixture provenance. The repository's
`scripts/prepare_hf_release.py` builds an allowlisted, hashed release tree with the
corrected card and this package under `rl/`. Preparation and the publisher's default
dry run do not modify the Hub. See `publication/README.md` in the source checkout.

Apache-2.0; original generator and source data attributed to DeepMind.
See [LICENSE](LICENSE) and [NOTICE](NOTICE).
