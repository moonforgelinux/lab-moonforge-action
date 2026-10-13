"""The action, run the way GitHub runs it: inside the built image."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = os.environ.get("CONTAINER_ENGINE", "podman")
IMAGE = os.environ.get("LAB_ACTION_IMAGE", "lab-moonforge-action:ci")
ROBOT_IMAGE = os.environ.get("LAB_ACTION_ROBOT_IMAGE",
                             "lab-moonforge-action:robot")

pytestmark = pytest.mark.docker


def built(image):
    """Skip rather than fail: not every checkout has built the image."""
    if not shutil.which(ENGINE):
        pytest.skip(ENGINE + " is not installed")
    present = subprocess.run([ENGINE, "image", "inspect", image],
                             capture_output=True)
    if present.returncode:
        pytest.skip(image + " has not been built")


def runner_for(tmp_path, image):
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

        done = subprocess.run(command + [image], capture_output=True,
                              text=True)
        done.workspace = workspace
        done.outputs = dict(
            line.split("=", 1) for line in outputs.read_text().splitlines()
            if "=" in line)
        return done
    return run_action


@pytest.fixture
def run(tmp_path):
    built(IMAGE)
    return runner_for(tmp_path, IMAGE)


@pytest.fixture
def robot_run(tmp_path):
    built(ROBOT_IMAGE)
    return runner_for(tmp_path, ROBOT_IMAGE)


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


def test_the_default_image_has_no_robot(run, capsys):
    """The robot stack is a gigabyte. It stays in its own tag."""
    done = run(workdir="robot", runner="robot", run="smoke.robot")

    assert done.returncode == 2
    assert "needs the robot image" in done.stdout


def test_the_robot_image_runs_a_robot_suite(robot_run):
    done = robot_run(workdir="robot", runner="robot", run="smoke.robot")

    assert done.returncode == 0, done.stdout + done.stderr
    assert "2 tests, 2 passed" in done.stdout


def test_the_robot_suite_reports_into_the_output_directory(robot_run):
    done = robot_run(workdir="robot", runner="robot", run="smoke.robot")

    outdir = done.workspace / "robot" / "test-results"
    assert (outdir / "xunit.xml").is_file()
    assert (outdir / "log.html").is_file()
    assert (outdir / "smoke.txt").read_text() == "the suite wrote this\n"


def test_the_robot_image_still_runs_pytest(robot_run):
    """It is the default image plus robot, not a different one."""
    done = robot_run(workdir="pytest", run="test_smoke.py")

    assert done.returncode == 0, done.stdout + done.stderr
    assert "2 passed" in done.stdout


def test_the_robot_device_suite_skips_without_a_device(robot_run):
    """The same suite has to pass on the runner and in the lab."""
    done = robot_run(workdir="robot", runner="robot", run="device.robot")

    assert done.returncode == 0, done.stdout + done.stderr
    assert "3 skipped" in done.stdout


def test_the_robot_device_suite_is_valid(robot_run):
    """
    A dry run resolves every keyword without connecting to anything.

    Without it nothing here would check the SSH half of that suite:
    the skip path never reaches it, and the lab run that does is
    manual.
    """
    done = robot_run(workdir="robot", runner="robot", run="device.robot",
                     run_args="--dryrun")

    assert done.returncode == 0, done.stdout + done.stderr
    assert "3 tests, 3 passed" in done.stdout
