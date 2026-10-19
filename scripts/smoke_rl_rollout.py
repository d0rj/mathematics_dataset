"""Compatibility entrypoint for the distributable Docker/Verifiers smoke check."""

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(
        str(
            Path(__file__).absolute().parents[1]
            / "environments/mathematics_rl/integrations/docker/verifiers_smoke.py"
        ),
        run_name="__main__",
    )
