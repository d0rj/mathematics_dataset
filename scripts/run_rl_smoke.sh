#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
export PATH="$HOME/.local/bin:$PATH"
export UV_CACHE_DIR="$task_root/.cache/uv-linux"
export UV_PROJECT_ENVIRONMENT="$task_root/environments/mathematics_rl/.venv-wsl"
export TMPDIR="$task_root/.cache/tmp-linux"
mkdir -p "$TMPDIR"
uv sync --project environments/mathematics_rl --locked --python python3
"$UV_PROJECT_ENVIRONMENT/bin/python" scripts/smoke_rl_rollout.py --output "$1"
