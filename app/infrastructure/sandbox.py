"""Disposable Docker sandbox for generated strategy artifacts."""

from __future__ import annotations

import os
import subprocess
from typing import Any, Callable

from ..errors import ApplicationError


class DockerSandboxRunner:
    """Runs only stdin-provided artifacts: no host mount, network, DB or secrets."""

    def __init__(
        self,
        *,
        image: str | None = None,
        timeout_seconds: float = 5.0,
        run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self._image = image or os.getenv("SANDBOX_IMAGE", "python:3.12-alpine")
        self._timeout_seconds = timeout_seconds
        self._run = run

    def run_contract(self, artifact: str) -> dict[str, Any]:
        command = [
            "docker", "run", "--rm", "--pull=never", "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "65532:65532",
            "--pids-limit", "32", "--memory", "128m", "--cpus", "0.5",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m", "--workdir", "/tmp", "--log-driver", "none",
            "-i", self._image, "python", "-I", "-S", "-",
        ]
        script = artifact + "\nassert isinstance(STRATEGY_SPEC, dict)\n"
        try:
            completed = self._run(
                command,
                input=script,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
            raise ApplicationError("sandbox_unavailable", "isolated sandbox is unavailable", 503) from exc
        if completed.returncode != 0:
            raise ApplicationError("strategy_sandbox_failed", "sandbox contract checks failed", 422)
        return {
            "status": "passed",
            "policy_version": "docker-sandbox-v1",
            "fixture_version": "strategy-contract-v1",
            "image": self._image,
            "checks": ["isolated_container", "strategy_spec_mapping"],
        }

    def run_python_contract(self, artifact: str) -> dict[str, Any]:
        command = [
            "docker", "run", "--rm", "--pull=never", "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "65532:65532",
            "--pids-limit", "32", "--memory", "128m", "--cpus", "0.5",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m", "--workdir", "/tmp", "--log-driver", "none",
            "-i", self._image, "python", "-I", "-S", "-c", "import sys; compile(sys.stdin.read(), '<artifact>', 'exec')",
        ]
        try:
            completed = self._run(
                command, input=artifact, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                text=True, timeout=self._timeout_seconds, check=False,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
            raise ApplicationError("sandbox_unavailable", "isolated sandbox is unavailable", 503) from exc
        if completed.returncode != 0:
            raise ApplicationError("strategy_sandbox_failed", "sandbox contract checks failed", 422)
        return {
            "status": "passed",
            "policy_version": "docker-sandbox-v1",
            "fixture_version": "custom-python-syntax-v1",
            "image": self._image,
            "checks": ["isolated_container", "python_syntax_compiles"],
        }
