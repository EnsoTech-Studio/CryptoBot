from subprocess import CompletedProcess

import pytest

from app.errors import ApplicationError
from app.infrastructure.sandbox import DockerSandboxRunner


def test_docker_sandbox_runs_artifact_with_network_and_host_access_disabled():
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return CompletedProcess(command, 0, "", "")

    report = DockerSandboxRunner(run=run).run_contract("STRATEGY_SPEC = {'schema_version': 'strategy-spec/v1'}\n")

    command, kwargs = calls[0]
    assert ["--network", "none"] == command[command.index("--network"):command.index("--network") + 2]
    assert "--read-only" in command
    assert ["--user", "65532:65532"] == command[command.index("--user"):command.index("--user") + 2]
    assert "--cap-drop" in command and "ALL" in command
    assert kwargs["input"].startswith("STRATEGY_SPEC")
    assert report["status"] == "passed"
    assert "isolated_container" in report["checks"]


def test_docker_sandbox_never_exposes_container_output_as_an_authoring_error():
    def run(command, **kwargs):
        return CompletedProcess(command, 1, "secret", "untrusted traceback")

    with pytest.raises(ApplicationError) as error:
        DockerSandboxRunner(run=run).run_contract("STRATEGY_SPEC = {}\n")

    assert error.value.code == "strategy_sandbox_failed"
    assert "secret" not in error.value.message


def test_docker_sandbox_compiles_custom_python_without_executing_it():
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return CompletedProcess(command, 0, "", "")

    report = DockerSandboxRunner(run=run).run_python_contract("class Strategy:\n    def analyze(self, candles): return []\n")

    command, kwargs = calls[0]
    assert ["--network", "none"] == command[command.index("--network"):command.index("--network") + 2]
    assert "compile(sys.stdin.read()" in command[-1]
    assert kwargs["input"].startswith("class Strategy")
    assert report["checks"] == ["isolated_container", "python_syntax_compiles"]
