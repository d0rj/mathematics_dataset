#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
export PATH="$HOME/.local/bin:$PATH"
export UV_CACHE_DIR="$task_root/.cache/uv-linux"
export UV_PROJECT_ENVIRONMENT="$task_root/environments/mathematics_rl/.venv-wsl"
uv sync --project environments/mathematics_rl --locked --python python3 --extra verifiers
"$UV_PROJECT_ENVIRONMENT/bin/python" -m pytest environments/mathematics_rl/tests tests/test_hf_release.py -q \
  --junitxml "$task_root/.cache/rl-junit-wsl.xml"
