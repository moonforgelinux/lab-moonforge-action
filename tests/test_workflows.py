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


def test_the_release_builds_both_architectures():
    build = step(load("release.yml"), "publish", "uses",
                 "build-push-action")
    assert build["with"]["platforms"] == "linux/amd64,linux/arm64"
