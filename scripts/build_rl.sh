#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
export PATH="$HOME/.local/bin:$PATH"
export UV_CACHE_DIR="$task_root/.cache/uv-linux"
uv build environments/mathematics_rl --out-dir dist
