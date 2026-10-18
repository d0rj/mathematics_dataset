# Hugging Face publication

Target: `d0rj/mathematics_dataset`, expected parent
`d9f78d0665b3a13dad21c6830b9b358c8a25ae74`.
The reviewed card is [huggingface/README.md](huggingface/README.md). Existing
`data/` files, split paths, row counts and four-column data schema are retained.

## Prepare locally

Run from the source repository root:

```bash
uv run --project environments/mathematics_rl pytest environments/mathematics_rl/tests -q
uv build environments/mathematics_rl
uv run --project environments/mathematics_rl python scripts/prepare_hf_release.py
uv run --project environments/mathematics_rl python scripts/publish_hf_release.py dist/hf-release-0.1.0/manifest.json
```

The last command is a **dry run**: it validates hashes and prints the exact add/replace
allowlist. The release directory must be new; preparation refuses to overwrite it.
It includes only the dataset README and `rl/` package, lock, docs, tests and fixtures.
No original Parquet data, credentials, caches, virtual environments, outputs or
local training artifacts enter the release. `manifest.json` is a local control file.

## Publish the reviewed directory

After explicit publication authorization, authenticate locally with `hf auth login`
or a locally configured `HF_TOKEN`. Then run the same command with `--publish`:

```bash
uv run --project environments/mathematics_rl python scripts/publish_hf_release.py dist/hf-release-0.1.0/manifest.json --publish
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
- Add `rl-environment` and `verifiers` compatibility tags with an actual runnable package.
