# Hugging Face publication

Version **0.2.1** adds reproducible local Docker checks and fixes found by native
container execution. See `rl/DOCKER.md` and `rl/DOCKER_VALIDATION.toml` in the
release for protocol coverage, SDK/image pins and measured results.

Previous version **0.2.0 was published on 2026-10-19**:
[HF commit 0d8f2b5](https://huggingface.co/datasets/d0rj/mathematics_dataset/commit/0d8f2b5f5e5ad4f2d51c09f10e5da6d795f9413a).
All 44 release files were downloaded and matched to their manifest hashes;
all 33 original Parquet objects are unchanged. The API confirms `rl-environment`
and all five framework tags, and returns the repository through the
`rl-environment` dataset filter. See `validation.toml` for recorded evidence.

Target: `d0rj/mathematics_dataset`, expected parent
`0d8f2b5f5e5ad4f2d51c09f10e5da6d795f9413a` for version 0.2.1.
The reviewed card is [huggingface/README.md](huggingface/README.md). Existing
`data/` files, split paths, row counts and four-column data schema are retained.

## Prepare locally

Run from the source repository root:

```bash
uv run --project environments/mathematics_rl --extra verifiers pytest environments/mathematics_rl/tests -q
uv build environments/mathematics_rl
python environments/mathematics_rl/integrations/docker/run.py --output /absolute/path/to/new-results
uv run --project environments/mathematics_rl python scripts/prepare_hf_release.py
uv run --project environments/mathematics_rl python scripts/publish_hf_release.py dist/hf-release-0.2.1/manifest.json
```

The last command is a **dry run**: it validates hashes and prints the exact add/replace
allowlist. The release directory must be new; preparation refuses to overwrite it.
It includes only the dataset README and `rl/` package, lock, docs, tests, fixtures
and framework integration manifests. Version 0.2.1 includes a Docker runner and
native protocol checks for all five frameworks; install extras in separate environments as described in
`rl/FRAMEWORKS.md`. The Verifiers extra must now be explicitly selected.
No original Parquet data, credentials, caches, virtual environments, outputs or
local training artifacts enter the release. `manifest.json` is a local control file.

## Publish the reviewed directory

After explicit publication authorization, authenticate locally with `hf auth login`
or a locally configured `HF_TOKEN`. Then run the same command with `--publish`:

```bash
uv run --project environments/mathematics_rl python scripts/publish_hf_release.py dist/hf-release-0.2.1/manifest.json --publish
```

It creates one commit with `parent_commit` protection and **no delete operations**.
If the remote base changed, inspect it and prepare a new release; do not bypass
the parent check. Never print or save credentials in the manifest or documentation.

After publication, verify the RL filter/card and run the card's exact download,
install and evaluation commands from a fresh environment. The generic Hub library
menu is framework metadata; this custom v1 taskset requires the package installation
shown in the card. A published tag or successful upload alone does not prove execution.

## Card corrections

- Correct repository ID in loading examples; remove the nonexistent `language` column.
- Preserve language as `en`/`ru` split selection; distinguish train and evaluation categories.
- Remove the unverified Russian generation command instead of inventing historical provenance.
- Describe the eight actual module families; remove the unsupported geometry claim.
- Document grading, supported modules, execution platform, pinned revision and evidence limits.
- Add `rl-environment`, `verifiers`, `harbor`, `openenv`, `nemo-gym` and `agentenv`
  compatibility tags with the executable package and native adapters.
