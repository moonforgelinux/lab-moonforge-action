import re
from importlib.metadata import metadata
from pathlib import Path

import yaml

from test_image import IMAGE

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text())


def triggers(workflow):
    """YAML 1.1 reads a bare `on` key as the boolean True."""
    return workflow.get("on", workflow.get(True))


def step(workflow, job, key, fragment):
    for found in workflow["jobs"][job]["steps"]:
        if fragment in found.get(key, ""):
            return found
    raise AssertionError(f"no step with {key} matching {fragment}")


def test_every_workflow_parses_and_defines_jobs():
    files = sorted(WORKFLOWS.glob("*.yml"))
    assert files
    for path in files:
        assert yaml.safe_load(path.read_text())["jobs"], path.name


def test_the_matrix_covers_the_lowest_supported_python():
    floor = metadata("lab-moonforge-action")["Requires-Python"]
    floor = floor.lstrip(">=")
    matrix = load("test.yml")["jobs"]["pytest"]["strategy"]["matrix"]
    assert floor in matrix["python-version"]


def test_the_image_job_builds_the_tag_the_container_tests_look_for():
    build = step(load("test.yml"), "image", "run", "docker build")
    assert IMAGE in build["run"]


def test_nothing_but_a_tag_publishes_an_image():
    fired_by = triggers(load("release.yml"))
    assert set(fired_by) == {"push", "workflow_dispatch"}
    assert fired_by["push"] == {"tags": ["v*"]}


def test_the_release_pins_every_action_by_sha():
    """A moved tag would run as the only token that writes packages."""
    for job in load("release.yml")["jobs"].values():
        for found in job["steps"]:
            used = found.get("uses")
            if used:
                assert re.fullmatch(r"[0-9a-f]{40}", used.split("@")[1]), used


def release_matrix():
    return load("release.yml")["jobs"]["build"]["strategy"]["matrix"]


def test_the_release_builds_both_architectures():
    platforms = {entry["platform"] for entry in release_matrix()["include"]}
    assert platforms == {"linux/amd64", "linux/arm64"}


def test_each_architecture_builds_on_a_runner_of_its_own_kind():
    runners = {entry["platform"]: entry["runs-on"]
               for entry in release_matrix()["include"]}
    assert "arm" in runners["linux/arm64"]
    assert "arm" not in runners["linux/amd64"]


def test_nothing_in_the_release_emulates():
    """Emulation means a privileged container registering binfmt."""
    for job in load("release.yml")["jobs"].values():
        for found in job["steps"]:
            assert "setup-qemu" not in found.get("uses", "")
