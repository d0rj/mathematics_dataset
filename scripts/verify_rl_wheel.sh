#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
export PATH="$HOME/.local/bin:$PATH"
export UV_CACHE_DIR="$task_root/.cache/uv-linux"
uv run --isolated --no-project --python python3 \
  --with "$task_root/dist/mathematics_rl-0.2.1-py3-none-any.whl" \
  mathematics-rl grade --module arithmetic__div --question 'Divide 1 by 2.' \
  --reference 1/2 --answer '0.5'
