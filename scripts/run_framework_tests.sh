#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
export PATH="$HOME/.local/bin:$PATH"
export UV_CACHE_DIR="$task_root/.cache/uv-linux"
export UV_PYTHON_INSTALL_DIR="$task_root/.cache/python"
export UV_PROJECT_ENVIRONMENT="$task_root/environments/mathematics_rl/.venv-frameworks"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
uv sync --project environments/mathematics_rl --locked --python 3.13.14 \
  --extra harbor --extra openenv --extra agentenv --extra nemo
"$UV_PROJECT_ENVIRONMENT/bin/python" -m pytest -p pytest_asyncio.plugin \
  environments/mathematics_rl/tests tests/test_hf_release.py -q \
  --junitxml "$task_root/.cache/framework-junit-wsl.xml"
