"""Build and verify each framework in Docker. Only this run's resources are removed."""

import argparse
import hashlib
import json
import shutil
import subprocess
import time
import tomllib
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

PACKAGE = Path(__file__).absolute().parents[2]
FRAMEWORKS = ("verifiers", "harbor", "openenv", "nemo", "agentenv")


class DockerChecks:
    def __init__(self, output, frameworks, skip_build=False, harbor_limit=0):
        self.output = Path(output).absolute()
        self.output.mkdir(parents=True, exist_ok=False)
        self.frameworks = frameworks
        self.version = tomllib.loads((PACKAGE / "pyproject.toml").read_text())["project"]["version"]
        self.prefix = "math-rl-" + uuid.uuid4().hex[:10]
        self.docker = (
            shutil.which("docker") or r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
        )
        self.network = self.prefix + "-net"
        self.volume = None
        self.skip_build = skip_build
        self.harbor_limit = harbor_limit
        self.containers = []
        self.production_openenv = None
        self.report = {
            "version": self.version,
            "run_id": self.prefix,
            "frameworks": {},
            "model_responses": "scripted",
            "training_run": False,
            "gpu_used": False,
            "source_python_sha256": {
                p.relative_to(PACKAGE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((PACKAGE / "src").rglob("*.py"))
            },
        }

    def call(self, *args, timeout=60, check=True):
        return subprocess.run(
            [self.docker, *map(str, args)],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=check,
            timeout=timeout,
        )

    def image(self, framework):
        return f"mathematics-rl-check-{framework}:{self.version}"

    def build(self, framework):
        if not self.skip_build:
            with (self.output / f"build-{framework}.log").open("w", encoding="utf-8") as log:
                result = subprocess.run(
                    [
                        self.docker,
                        "build",
                        "--progress",
                        "plain",
                        "--build-arg",
                        f"FRAMEWORK={framework}",
                        "-f",
                        str(PACKAGE / "integrations/docker/Dockerfile"),
                        "-t",
                        self.image(framework),
                        str(PACKAGE),
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=1200,
                )
                if result.returncode:
                    raise RuntimeError(f"Build failed: {framework}; see {log.name}")
        info = json.loads(self.call("image", "inspect", self.image(framework)).stdout)[0]
        self.report["frameworks"][framework] = {
            "image_id": info["Id"],
            "image": self.image(framework),
        }
        if framework == "openenv":
            self.production_openenv = f"mathematics-openenv:{self.version}"
            if not self.skip_build:
                with (self.output / "build-openenv-production.log").open(
                    "w", encoding="utf-8"
                ) as log:
                    subprocess.run(
                        [
                            self.docker,
                            "build",
                            "--progress",
                            "plain",
                            "-f",
                            str(PACKAGE / "integrations/openenv/Dockerfile"),
                            "-t",
                            self.production_openenv,
                            str(PACKAGE),
                        ],
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=1200,
                        check=True,
                    )
            info = json.loads(self.call("image", "inspect", self.production_openenv).stdout)[0]
            self.report["frameworks"][framework]["production_server_image_id"] = info["Id"]

    def create(self, framework, suffix, command, *, daemon=False, mounts=(), image=None):
        name = self.prefix + "-" + suffix
        self.containers.append(name)
        args = [
            "create",
            "--name",
            name,
            "--label",
            f"mathematics.rl.run={self.prefix}",
            "--init",
            "--cpus",
            "2",
            "--memory",
            "4g",
            "--network",
            self.network,
        ]
        for mount in mounts:
            args.extend(["--mount", mount])
        args.extend([image or self.image(framework), *command])
        self.call(*args)
        if daemon:
            self.call("start", name)
        return name

    def run(self, framework, suffix, command, *, timeout=600, mounts=()):
        name = self.create(framework, suffix, command, mounts=mounts)
        with (self.output / f"{suffix}.log").open("w", encoding="utf-8") as log:
            proc = subprocess.run(
                [self.docker, "start", "--attach", name],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
        exit_code = json.loads(self.call("inspect", name).stdout)[0]["State"]["ExitCode"]
        target = self.output / suffix
        target.mkdir(exist_ok=True)
        self.call("cp", name + ":/results/.", target, check=False)
        if proc.returncode or exit_code:
            raise RuntimeError(f"{suffix} failed (exit {exit_code}); see {suffix}.log")
        return target

    def ready(self, name, port, endpoint):
        deadline = time.monotonic() + 90
        code = (
            "from urllib.request import urlopen; "
            f"urlopen('http://127.0.0.1:{port}{endpoint}', timeout=2).read()"
        )
        while time.monotonic() < deadline:
            if (
                self.call("exec", name, "python", "-c", code, timeout=5, check=False).returncode
                == 0
            ):
                return
            state = json.loads(self.call("inspect", name).stdout)[0]["State"]
            if not state["Running"]:
                break
            time.sleep(0.5)
        raise RuntimeError(f"Server {name} did not become ready")

    def unit(self, framework):
        target = self.run(
            framework, framework + "-unit", ["python", "integrations/docker/scenarios.py", "unit"]
        )
        suite = ET.parse(target / "pytest.xml").getroot().find("testsuite")
        assert int(suite.attrib["failures"]) == int(suite.attrib["errors"]) == 0
        passed = int(suite.attrib["tests"]) - int(suite.attrib["skipped"])
        assert passed > 1400
        self.report["frameworks"][framework]["unit"] = dict(suite.attrib)

    def protocols(self, framework):
        if framework == "openenv":
            results = []
            for language in ("en", "ru"):
                suffix = "openenv-" + language
                name = self.create(
                    framework,
                    suffix,
                    [
                        "python",
                        "integrations/docker/scenarios.py",
                        "serve-openenv",
                        "--language",
                        language,
                    ],
                    daemon=True,
                    image=self.production_openenv,
                )
                self.ready(name, 8000, "/health")
                target = self.run(
                    framework,
                    suffix + "-client",
                    [
                        "python",
                        "integrations/docker/scenarios.py",
                        "openenv",
                        "--url",
                        f"http://{name}:8000",
                        "--language",
                        language,
                    ],
                )
                results.append(json.loads((target / "report.json").read_text()))
                self.call("stop", "-t", "10", name)
            self.report["frameworks"][framework]["protocol"] = results
        elif framework == "nemo":
            name = self.create(
                framework,
                "nemo-server",
                ["mathematics-nemo", "--host", "0.0.0.0", "--port", "8001"],
                daemon=True,
            )
            self.ready(name, 8001, "/reverify_mode")
            target = self.run(
                framework,
                "nemo-client",
                [
                    "python",
                    "integrations/docker/scenarios.py",
                    "nemo",
                    "--url",
                    f"http://{name}:8001",
                ],
            )
            self.report["frameworks"][framework]["protocol"] = json.loads(
                (target / "report.json").read_text()
            )
            self.call("stop", "-t", "10", name)
            name = self.create(
                framework,
                "nemo-native-server",
                ["python", "integrations/docker/scenarios.py", "serve-nemo-native"],
                daemon=True,
            )
            self.ready(name, 8001, "/reverify_mode")
            target = self.run(
                framework,
                "nemo-native-client",
                [
                    "python",
                    "integrations/docker/scenarios.py",
                    "nemo",
                    "--url",
                    f"http://{name}:8001",
                ],
            )
            self.report["frameworks"][framework]["supervisor_entrypoint_protocol"] = json.loads(
                (target / "report.json").read_text()
            )
        elif framework == "agentenv":
            target = self.run(
                framework,
                "agentenv-episodes",
                ["python", "integrations/docker/scenarios.py", "agentenv"],
                timeout=900,
            )
            self.report["frameworks"][framework]["protocol"] = json.loads(
                (target / "report.json").read_text()
            )
        elif framework == "verifiers":
            target = self.run(
                framework,
                "verifiers-rollout",
                [
                    "python",
                    "integrations/docker/verifiers_smoke.py",
                    "--output",
                    "/results/rollout",
                ],
            )
            self.report["frameworks"][framework]["protocol"] = json.loads(
                (target / "rollout/report.json").read_text()
            )
        else:
            self.harbor()

    def harbor(self):
        self.volume = self.prefix + "-harbor-data"
        self.call("volume", "create", "--label", f"mathematics.rl.run={self.prefix}", self.volume)
        # Sibling containers must see the same absolute paths as the runner.
        mountpoint = json.loads(self.call("volume", "inspect", self.volume).stdout)[0]["Mountpoint"]
        target = self.run(
            "harbor",
            "harbor-trials",
            [
                "python",
                "integrations/docker/harbor_trials.py",
                "--work",
                mountpoint,
                "--prefix",
                self.prefix,
                "--limit",
                str(self.harbor_limit),
            ],
            timeout=3600,
            mounts=[
                "type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock",
                f"type=volume,source={self.volume},target={mountpoint}",
            ],
        )
        self.report["frameworks"]["harbor"]["protocol"] = json.loads(
            (target / "report.json").read_text()
        )

    def cleanup(self):
        for name in self.containers:
            captured = self.call("logs", name, check=False)
            log = captured.stdout + captured.stderr
            if log:
                (self.output / (name + "-container.log")).write_text(log, encoding="utf-8")
            self.call("rm", "-f", name, check=False)
        # Harbor tasks are prefixed with this run's random identifier before launch.
        ids = self.call(
            "ps", "-aq", "--filter", f"name=^/?{self.prefix}-", check=False
        ).stdout.split()
        if ids:
            self.call("rm", "-f", *ids, check=False)
        networks = self.call(
            "network", "ls", "-q", "--filter", f"name=^{self.prefix}", check=False
        ).stdout.split()
        if networks:
            self.call("network", "rm", *networks, check=False)
        if self.volume:
            self.call("volume", "rm", self.volume, check=False)

    def execute(self):
        self.report["docker"] = json.loads(self.call("version", "--format", "{{json .}}").stdout)
        self.call("network", "create", "--label", f"mathematics.rl.run={self.prefix}", self.network)
        try:
            for framework in self.frameworks:
                print(f"[{framework}] build, unit tests, native protocol", flush=True)
                self.build(framework)
                self.unit(framework)
                self.protocols(framework)
                self.report["frameworks"][framework]["passed"] = True
                print(f"[{framework}] passed", flush=True)
            self.report["passed"] = True
        except Exception as error:
            self.report["passed"] = False
            self.report["error"] = str(error)
            raise
        finally:
            self.cleanup()
            (self.output / "report.json").write_text(
                json.dumps(self.report, indent=2) + "\n", encoding="utf-8"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--framework", choices=FRAMEWORKS, action="append")
    parser.add_argument(
        "--skip-build", action="store_true", help="Development only: reuse already built images"
    )
    parser.add_argument(
        "--harbor-limit", type=int, default=0, help="0 verifies all 140 module/language tasks"
    )
    args = parser.parse_args()
    DockerChecks(
        args.output, args.framework or FRAMEWORKS, args.skip_build, args.harbor_limit
    ).execute()


if __name__ == "__main__":
    main()
