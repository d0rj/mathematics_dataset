# Local Docker validation

Run all five integrations from this package directory on a machine with a Linux
Docker daemon and Python 3.11.4+ on the host:

```bash
python integrations/docker/run.py --output /absolute/path/to/new-validation-directory
```

The output directory must be new. The runner builds separate pinned SDK images,
runs the regression suite in each, then exercises native framework protocols.
It also builds the actual OpenEnv production Dockerfile and uses that image for
both English and Russian servers. The host needs only Python's standard library
and Docker CLI. Image builds need internet; scoring uses local committed fixtures.

For an individual integration, add `--framework harbor` (or `verifiers`, `openenv`,
`nemo`, `agentenv`). The flag is repeatable. Harbor's default covers 140 task
directories; `--harbor-limit 2` is a shorter development check. `--skip-build` is
for iterative development with existing images, not final release evidence.

## What is exercised

| Integration | Docker execution |
| --- | --- |
| Verifiers | Native plugin discovery and `Task.score` for 70 modules × 2 languages; real `vf-eval` with six scripted model responses |
| Harbor | Real `harbor run`, agent containers, artifact collection, separate verifier containers, 140 oracle tasks, incorrect answers spanning all answer kinds, invalid-source and missing-output cases |
| OpenEnv | Production server image plus native `EnvClient` in a different container; correct/incorrect answers for every module/language pair, reset/state and rejection of repeated submissions |
| NeMo Gym | Real resource-server CLI, cross-container HTTP `/verify`, and supervisor-style entrypoint configuration; correct/incorrect answers for every module/language pair |
| AgentEnv | Native `EpisodeSpec.start`, solver turn, response submission, grading, result and local stores inside the container; correct/incorrect answers for every module/language pair |

The HTTP/episode matrices each cover 280 scripted submissions (140 correct, 140
incorrect). These are deterministic engineering checks, not evaluation of a real
model, model training or an independent audit of the entire published corpus.

## Reproducibility and artifacts

The validation images pin Python 3.13.14, uv 0.11.23 and Docker CLI 29.7.2;
base-image manifest digests are in the Dockerfile. `uv sync --locked` preserves
the five SDK pins and their separate MCP dependency graphs. No API credentials
or host environment secrets are passed into the test containers.

`report.json` records image IDs, source hashes, Docker versions, pytest results,
case coverage and native protocol results. Per-phase logs and JUnit XML are
retained. Harbor's native trial JSON, verifier logs and artifacts are copied out
before its run volume is removed. Expected invalid-source errors are asserted
separately and do not count as model rewards.

The runner uses CPU limits, memory limits and a dedicated Docker network. It
removes its own named containers, networks and scratch volume, retaining the
built images and host reports. It never prunes Docker globally. Harbor alone
receives the Docker socket to launch sibling task containers. A named volume is
mounted at its daemon-side absolute path, so artifact mounts work on Docker
Desktop as well as a local Linux daemon.

## Fixes verified by container execution

- Windows exports use LF for executable scripts. Earlier CRLF exports failed
  inside Linux with `set: Illegal option -`; a native Windows export is also
  executed directly in a Linux container as a regression check.
- Harbor verifiers use an explicit Compose `network_mode: none`. This works on
  Docker Desktop kernels without `CONFIG_NFT_FIB_INET`, where Harbor's dynamic
  egress-control `network_mode="no-network"` policy rejects startup. The native
  trials verify that the verifier has no IPv4 routes and the agent cannot read
  the verifier's reference/checker paths.
- Invalid Harbor references are checked before model artifacts. Source failures
  leave no `reward.txt`; Harbor reports a verifier/source error. This prevents
  malformed references and missing outputs from silently becoming zero model
  rewards, and discards stale score files.
- The production OpenEnv image uses the same lockfile and pinned Python base as
  validation, rather than resolving a separate transitive dependency set.
- Verifier inputs are snapshotted in a deterministic, content-addressed tar file,
  with a unique source filename for Docker's `ADD`. A reference SHA-256 label
  and build-time digest check supplement it. This replaces directory copying,
  which mixed files between simultaneous task builds in the local Compose/BuildKit
  run. Native tests also assert the task ID inside each verifier container.

See [VALIDATION.md](VALIDATION.md) and [DOCKER_VALIDATION.toml](DOCKER_VALIDATION.toml)
for release evidence. [FRAMEWORKS.md](FRAMEWORKS.md) describes normal use.
