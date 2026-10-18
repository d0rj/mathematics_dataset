---
dataset_info:
  features:
  - name: question
    dtype: string
  - name: answer
    dtype: string
  - name: category
    dtype: string
  - name: module
    dtype: string
  splits:
  - name: ru
    num_bytes: 2068198005
    num_examples: 12699944
  - name: en
    num_bytes: 13818553700
    num_examples: 112709888
  download_size: 4606972272
  dataset_size: 15886751705
configs:
- config_name: default
  data_files:
  - split: ru
    path: data/ru-*
  - split: en
    path: data/en-*
license: apache-2.0
language:
- en
- ru
task_categories:
- text-generation
- question-answering
tags:
- mathematics
- synthetic
- reasoning
- rl-environment
- verifiers
---

# Mathematical Reasoning Dataset and Verifiers v1 Environment

A bilingual synthetic school-level mathematics dataset, with an executable
single-turn RL/evaluation environment for all **70 modules**. The four-column
Parquet data remains usable with `datasets`; the environment package lives in
[`rl/`](rl) and uses the Verifiers v1 API from pinned `verifiers==0.4.0`.

## Data

| Language split | Rows |
| --- | ---: |
| `en` | 112,709,888 |
| `ru` | 12,699,944 |

English data originates from the official DeepMind Mathematics Dataset release.
Russian questions were generated independently with a translated generator;
the language splits are not paired translations. Exact historical Russian
generation flags have not been established for these published files, so this
card does not assert a command inferred solely from row counts.

Each row has exactly four string columns:

```python
from datasets import load_dataset

ds = load_dataset(
    "d0rj/mathematics_dataset", "default", split="ru", streaming=True,
    revision="d9f78d0665b3a13dad21c6830b9b358c8a25ae74",
)
print(next(iter(ds)))
# question, answer, category, module
```

There is **no `language` column** in Parquet: select the `en` or `ru` split.
`category` separates training difficulty and evaluation:

| Category | Intended use |
| --- | --- |
| `train-easy`, `train-medium`, `train-hard` | Training / curriculum |
| `interpolate` | In-distribution evaluation |
| `extrapolate` | Extrapolation evaluation |

The eight module families are algebra, arithmetic, calculus, comparison,
measurement, numbers, polynomials and probability. See the complete
[70-module catalog](rl/MODULES.md). Language splits do not replace train/eval
selection. Do not mix the two evaluation categories into RL training.

## Install the RL environment

Use Linux, macOS or WSL for full execution: the pinned upstream Verifiers runtime
requires POSIX `fcntl`. The standalone checker can also run on Windows.

```bash
uvx --from huggingface-hub hf download d0rj/mathematics_dataset \
  --repo-type dataset --include 'rl/**' --local-dir mathematics-env
cd mathematics-env/rl
uv sync --locked
uv run mathematics-rl catalog
```

This downloads environment files, not the entire corpus. Package installation is
required for this custom v1 taskset; use these commands rather than interpreting
the generic library menu as a preinstalled hosted runtime.

## Run an evaluation or select training tasks

Point the environment at an OpenAI-compatible model endpoint, with its credential
configured locally in `LOCAL_LLM_API_KEY` when required:

```bash
uv run vf-eval mathematics-rl \
  --env.taskset.language ru --env.taskset.mode interpolate \
  --env.taskset.modules '["arithmetic__add_or_sub"]' \
  --model YOUR_MODEL --client.base-url http://127.0.0.1:8000/v1 \
  --client.api-key-var LOCAL_LLM_API_KEY -n 20 --no-push
```

Defaults: one agent, one tool-less `null` turn, local `subprocess` runtime, and
dataset revision `d9f78d0665b3a13dad21c6830b9b358c8a25ae74`.
The loader streams with Parquet filters. Use `mode=train` for training categories
or `mode=extrapolate` for the separate extrapolation holdout. A Verifiers v1-compatible
trainer supplies weight updates; this repository does not start training itself.
`--no-push` keeps evaluation results local instead of uploading them to Prime.

## Reward

The evaluator keeps the reference answer private from the solver prompt and scores
the final response with reward **1 for correct, 0 otherwise**, without an LLM judge.
The answer is the last box outside completed thinking, or the last nonempty line.
Checks cover exact numbers/fractions, symbolic polynomials, root sets, ordered lists,
booleans, time, base numerals, and task-specific factorized/expanded/simplified forms.

For factorization and expansion, equivalence alone is insufficient: copying the
original expression does not satisfy the required form. Composed comparisons require
preserving the original named-value labels, as specified in the solver prompt.
See the full [grading contract](rl/GRADING.md) for accepted syntax and restrictions.

The mathematical parser uses a bounded grammar, not Python execution. A disposable
worker enforces a default 3-second deadline per reference check and candidate.
Malformed or timed-out source references fail as source errors; model parse errors
and timeouts are recorded separately in traces.

## Verification and limitations

Run the committed regression suite or bounded reference audit after installation:

```bash
uv run pytest tests -q
uv run mathematics-rl self-check --source tests/fixtures/generated_ru.ndjson \
  --language ru --mode all --limit 0 --require-all-modules --output reference-check.json
```

See [validation evidence](rl/VALIDATION.md). Reference acceptance and framework smoke
tests do not independently prove every published answer, absence of duplicates or
contamination, model quality, or an improvement from RL. No full-corpus mathematical
audit or model-training result is claimed. Keep source/filter/seed configuration
fixed for resume; see [package documentation](rl/README.md) for bounded shuffling.

## Provenance, citation and license

Original generator: [google-deepmind/mathematics_dataset](https://github.com/google-deepmind/mathematics_dataset).
Original paper: [Analysing Mathematical Reasoning Abilities of Neural Models](https://arxiv.org/abs/1904.01557),
Saxton, Grefenstette, Hill and Kohli, ICLR 2019.
Data, translated generator and this environment are Apache-2.0; preserve attribution.
Verifiers is a separately installed MIT-licensed dependency. See [LICENSE](rl/LICENSE)
and [NOTICE](rl/NOTICE).
