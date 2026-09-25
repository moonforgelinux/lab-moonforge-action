from importlib.metadata import metadata
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text())


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
