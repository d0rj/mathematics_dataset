# Validation evidence

Implementation and checks: 2026-10-18/19. Source data revision:
`d9f78d0665b3a13dad21c6830b9b358c8a25ae74`.

## Version 0.2.1: local Docker execution

The Docker runner builds separate SDK images on Docker Desktop 4.89.0,
Engine/CLI 29.7.2, Linux amd64, Python 3.13.14. The measured image IDs,
checksums and protocol results are recorded in [DOCKER_VALIDATION.toml](DOCKER_VALIDATION.toml).
Run it using [DOCKER.md](DOCKER.md).

| Pinned SDK in its own container | Package tests passed | Other SDK modules skipped |
| --- | ---: | ---: |
| Verifiers 0.4.0 | 1,641 | 4 |
| Harbor 0.24.0 | 1,500 | 4 |
| OpenEnv 0.9.0 | 1,502 | 4 |
| NeMo Gym 0.7.0 | 1,501 | 4 |
| AgentEnv 0.9.1334 | 1,504 | 4 |

Windows Python 3.13.13 separately passes 1,506 tests, with five optional SDK
modules skipped; this includes the seven source-repository publication checks.
The package suites include all 1,434 mathematical fixtures.

OpenEnv's actual production image and native cross-container client cover
280 submissions across all 70 modules in both languages. NeMo Gym covers the
same 280 submissions both through the standalone launcher and through the
entrypoint receiving native supervisor configuration. AgentEnv completes 280
native episode/turn/result cycles with local stores. Verifiers covers native
`Task.score` for all 140 module/language pairs and six actual `vf-eval` episodes
against the local scripted endpoint.

Native Harbor trials exercise artifact collection and separate agent/verifier
containers, oracle reference acceptance for all 140 module/language pairs,
incorrect answers covering all 12 answer kinds in each language, a source error
with no model reward, and missing output earning zero. The trials assert
private reference/checker paths are absent from the agent and that the verifier
has no IPv4 routes.

Container execution found and corrected Windows CRLF shell exports, the
Docker Desktop kernel incompatibility of Harbor's egress sidecar policy,
invalid-source errors leaving a misleading reward, and mixed verifier build
payloads during parallel Compose/BuildKit execution. Content-addressed tar
snapshots and reference checksums now bind each verifier to its task's files.
The OpenEnv production image also uses the checked lockfile and pinned base.

All supplied model answers are scripted or oracle answers. No model training,
GPU use, hosted CI run or real-model quality benchmark is claimed. The older
Docker limitation below describes version 0.2.0 and is resolved in this release.

## Scope

- 1,434 generated fixtures: 717 EN and 717 RU. Each language covers all 70 modules,
  all five categories and all 12 grading kinds. Three examples per module/category;
  56 train/interpolation modules and 15 extrapolation modules have a 70-module union.
- Each fixture checks reference acceptance and rejection of a changed answer.
- Additional tests cover equivalent fractions/LaTeX/decimal forms, root permutation,
  ordered-list changes, form shortcuts, code injection, bounded parsing, source errors,
  worker reuse/deadline termination/recovery, train/eval isolation and key stability.
- POSIX tests use the actual installed Verifiers 0.4 plugin loader, `Trace` and
  `Task.score` for all 140 module/language combinations. Native Windows skips that
  integration module because upstream imports `fcntl`; the standalone checker is tested.
- Bounded live Hub checks exercise the real streaming/filtering loader on Russian
  training arithmetic and English extrapolation root/factorization rows.
- `scripts/smoke_rl_rollout.py` drives actual `vf-eval` through a local scripted
  OpenAI-compatible endpoint. It is a transport/lifecycle/reward smoke, not inference
  by a trained model and not a model-quality or RL-training result.

Recorded complete v0.1.0 source-checkout runs (including seven card/release checks):

| Platform | Result |
| --- | --- |
| Windows, Python 3.13.13 | 1,497 passed; one POSIX integration module skipped |
| Ubuntu WSL, Python 3.12.3 | 1,639 passed, including actual v1 scoring for all 140 module/language combinations |
| Actual vf-eval + local scripted endpoint | Six completed episodes, one model request each; all expected rewards matched |
| Pinned public Hub loader | RU train: 3/3 accepted; EN extrapolation: 5/5 accepted |

The downloadable package's `pytest tests` excludes the seven source-repository
release/card checks. Release hashes are recorded in the source repository's
publication report and generated release manifest. CI is configured for
Ubuntu Python 3.11/3.13 and Windows Python 3.13; configuring CI is not evidence that
hosted CI has executed.

## Version 0.2.0: historical SDK checks

Checked on 2026-10-19 with actual installed SDKs, using the shared checker and
the unchanged EN/RU regression fixtures:

| Runtime | Complete suite result |
| --- | --- |
| Windows, Python 3.13.13 | 1,505 passed; five optional/POSIX SDK modules skipped |
| Ubuntu WSL, Python 3.12.3, Verifiers extra | 1,647 passed; four other SDK modules skipped |
| Ubuntu WSL, Python 3.13.14, Harbor/OpenEnv/AgentEnv/NeMo extras | 1,515 passed; Verifiers module skipped |

- Harbor 0.24.0's real `Task` loader validates exported task directories for all
  140 module/language pairs. Artifact checking covers correct, incorrect, missing
  and non-UTF-8 files. `environment_mode=separate` isolates references/checker code
  from the shell agent. **Version 0.2.0 had no completed Docker trial or image build**: the
  installed Docker Desktop daemon was unavailable (`dockerDesktopLinuxEngine`
  pipe missing), including after its normal start command. Run the documented
  `harbor run --agent oracle` once a Docker daemon is available.
- OpenEnv 0.9.0's real `Environment` grades all 140 module/language pairs, rejects
  repeated submissions, and exposes only public state. Native WebSocket tests
  verify two independent sessions. The real `EnvClient` also completes reset,
  answer submission and state inspection through a local Uvicorn TCP server.
- NeMo Gym 0.7.0's native request/response models, JSONL export and resource server
  grade all 140 pairs. Its real FastAPI `/verify` endpoint returns the expected
  reward; a policy model and training supervisor are not required for this check.
- AgentEnv 0.9.1334 discovers the installed `mathematics_grade` plugin. Native
  task/step serialization and scoring cover all 140 pairs. A real `EpisodeSpec`
  run through local stores hands out the solver turn, records its supplied
  response, grades it, and returns the expected final score. No deployed model,
  A2A agent container, cloud sandbox or model training was exercised.
  An additional focused check passes the exported EN/RU bundle through the actual
  AgentEnv bundle parser (one test, separate from the complete-suite count above).
- Cross-framework process tests found and fixed Windows child-process locale
  corruption of Russian questions by explicitly enabling UTF-8 in the grader.
- Separate extras/venvs preserve Verifiers' MCP 2 pin and the other SDKs' MCP 1
  dependencies. Current NeMo Gym needs Linux and Python >=3.13.14.

Reproduce with `scripts/run_rl_tests.sh` and `scripts/run_framework_tests.sh` in
the source checkout. The latter pins all four SDKs and runs on CPU in a separate
environment. Tests do not require credentials, a model endpoint or hosted jobs.
These counts are pytest cases; the module matrices each loop through 140 tasks.
All fixture math remains regression/reference-acceptance evidence, not an
independent full-corpus proof. Framework manifests and Docker definitions are
included in the source/Hub package; configuring CI is not a hosted CI result.

## Fixture generation

See [fixture provenance](tests/fixtures/provenance.toml) for hashes and versions.
Russian source is the translated generator at base commit
`e97cd83e190163e025dd831886f05460a11c1bc8`; English source is the original upstream
commit `427f45075f84b8b9774950196ad63867ca20ffb3`. `scripts/build_rl_fixtures.py`
uses per-module/category seeds derived from seed 20261018 and applies the same
160-character question / 30-character answer limits as the generator.

The old English generator needs Python 3.10 and NumPy 1.26 because newer Python
rejects its integer-valued float randint bounds and NumPy 2 removed `itemset`.
The generator sources are not patched to create the English fixtures. Russian
generation uses the existing translated checkout; neither generator was changed
for RL. The environment itself uses modern dependencies pinned in `uv.lock`.

## Boundaries

These fixtures are engineering regression data, not held-out model benchmarks.
Accepting an official generator's answer does not independently validate its math.
The full 125,409,832-row corpus has not been audited, deduplicated or used for an
RL experiment here. Release preparation changes only the card and `rl/`;
it neither rewrites Parquet nor uploads files itself. The source repository's
publication report records the actual Hub commit and post-upload verification.
