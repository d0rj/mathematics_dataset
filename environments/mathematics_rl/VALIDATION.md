# Validation evidence

Implementation and checks: 2026-10-18/19. Source data revision:
`d9f78d0665b3a13dad21c6830b9b358c8a25ae74`.

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

Recorded complete source-checkout runs (including seven card/release checks):

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
RL experiment here. The release preparation changes only the card and adds `rl/`;
it neither rewrites Parquet nor performs a hosted publication.
