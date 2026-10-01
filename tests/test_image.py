"""The action, run the way GitHub runs it: inside the built image."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = os.environ.get("CONTAINER_ENGINE", "podman")
IMAGE = os.environ.get("LAB_ACTION_IMAGE", "lab-moonforge-action:ci")

pytestmark = pytest.mark.docker


@pytest.fixture(scope="module", autouse=True)
def an_image():
    if not shutil.which(ENGINE):
        pytest.skip(ENGINE + " is not installed")
    present = subprocess.run([ENGINE, "image", "inspect", IMAGE],
                             capture_output=True)
    if present.returncode:
        pytest.skip(IMAGE + " has not been built")


@pytest.fixture
def run(tmp_path):
    """Run the action over a copy of examples/, as a container action."""
    workspace = tmp_path / "workspace"
    shutil.copytree(ROOT / "examples", workspace)
    outputs = tmp_path / "outputs"
    outputs.touch()

    def run_action(**given):
        command = [ENGINE, "run", "--rm",
                   "-v", f"{workspace}:/github/workspace",
                   "-v", f"{outputs}:/outputs",
                   "-e", "GITHUB_WORKSPACE=/github/workspace",
                   "-e", "GITHUB_OUTPUT=/outputs"]
        for name, value in given.items():
            command += ["-e", f"INPUT_{name.upper()}={value}"]

        done = subprocess.run(command + [IMAGE], capture_output=True,
                              text=True)
        done.workspace = workspace
        done.outputs = dict(
            line.split("=", 1) for line in outputs.read_text().splitlines()
            if "=" in line)
        return done
    return run_action


def test_the_image_runs_a_pytest_suite(run):
    done = run(workdir="pytest", run="test_smoke.py")

    assert done.returncode == 0, done.stdout + done.stderr
    assert "2 passed" in done.stdout


def test_the_suite_reports_into_the_output_directory(run):
    done = run(workdir="pytest", run="test_smoke.py")

    outdir = done.workspace / "pytest" / "test-results"
    assert (outdir / "junit.xml").is_file()
    assert (outdir / "smoke.txt").read_text() == "the suite wrote this\n"
    assert done.outputs["outdir"] == "pytest/test-results"


def test_a_failing_suite_gives_the_container_its_exit_status(run):
    done = run(runner="command", run="sh", run_args="-c 'exit 5'")

    assert done.returncode == 5
    assert done.outputs["exit_code"] == "5"


def test_the_cache_stays_out_of_the_checkout(run):
    """A root-owned .pytest_cache in the tree breaks the next job."""
    done = run(workdir="pytest", run="test_smoke.py")

    assert not (done.workspace / "pytest" / ".pytest_cache").exists()
    assert (done.workspace / "pytest" / "test-results" /
            "pytest-cache").is_dir()
