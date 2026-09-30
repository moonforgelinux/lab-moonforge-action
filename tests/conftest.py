import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUBS = Path(__file__).resolve().parent / "stubs"
ACTION = Path(sys.executable).parent / "lab-moonforge-action"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A checkout for the action to work on."""
    root = tmp_path.resolve()
    monkeypatch.setenv("GITHUB_WORKSPACE", str(root))
    return root


@pytest.fixture
def given(monkeypatch):
    """Set action inputs: given(entrypoint="tests", runner="pytest")."""
    def set_inputs(**values):
        for name, value in values.items():
            monkeypatch.setenv("INPUT_" + name.upper(), str(value))
    return set_inputs


@pytest.fixture
def run_action(workspace, tmp_path, pytestconfig):
    """
    Run the action the way the container does: a subprocess reading
    INPUT_*, with the lab stubs ahead of anything real on PATH.
    """
    log = tmp_path / "lab.log"
    outputs = tmp_path / "outputs"
    outputs.touch()

    def run(stub=None, **given):
        """Inputs as keywords; `stub` goes to the environment unchanged."""
        env = dict(os.environ)
        env["PATH"] = str(STUBS) + os.pathsep + env["PATH"]
        env["GITHUB_WORKSPACE"] = str(workspace)
        env["GITHUB_OUTPUT"] = str(outputs)
        env["DUT_STUB_LOG"] = str(log)
        if pytestconfig.pluginmanager.get_plugin("_cov"):
            env["COVERAGE_PROCESS_START"] = str(ROOT / "pyproject.toml")
        for name, value in given.items():
            env["INPUT_" + name.upper()] = str(value)
        env.update(stub or {})

        done = subprocess.run([str(ACTION)], env=env, capture_output=True,
                              text=True)
        done.calls = log.read_text().splitlines() if log.exists() else []
        done.outputs = dict(
            line.split("=", 1) for line in outputs.read_text().splitlines()
            if "=" in line)
        return done
    return run
