"""action.yml and the code have to agree on the inputs and outputs."""

import ast
from pathlib import Path

import yaml

import lab_action

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "lab_action"
READERS = {"get", "get_int", "lines"}
WRITERS = {"set_output"}


def action(name="action.yml"):
    return yaml.safe_load((ROOT / name).read_text())


def input_call(node):
    """An inputs.<something>("literal", [default]) call, or nothing."""
    func = node.func
    if not isinstance(func, ast.Attribute):
        return None
    if not isinstance(func.value, ast.Name) or func.value.id != "inputs":
        return None
    if not node.args or not isinstance(node.args[0], ast.Constant):
        return None

    default = None
    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
        default = node.args[1].value
    return func.attr, node.args[0].value, default


def calls():
    for path in sorted(PACKAGE.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call):
                found = input_call(node)
                if found:
                    yield found


def names(kinds):
    return {name for attr, name, _ in calls() if attr in kinds}


def test_the_code_reads_no_undeclared_input():
    assert names(READERS) - set(action()["inputs"]) == set()


def test_every_declared_input_is_read_by_the_code():
    assert set(action()["inputs"]) - names(READERS) == set()


def test_the_code_writes_no_undeclared_output():
    assert names(WRITERS) - set(action()["outputs"]) == set()


def test_every_declared_output_is_written_by_the_code():
    assert set(action()["outputs"]) - names(WRITERS) == set()


def test_the_declared_defaults_are_the_ones_the_code_falls_back_to():
    declared = action()["inputs"]
    checked = 0
    for attr, name, default in calls():
        if attr == "get" and default is not None:
            assert declared[name].get("default") == default, name
            checked += 1
    assert checked, "no default was actually compared"


def test_the_action_points_at_the_tag_for_this_version():
    """So bumping the version without republishing fails here."""
    runs = action()["runs"]

    assert runs["using"] == "docker"
    assert runs["image"].startswith("docker://ghcr.io/")
    assert runs["image"].endswith(f":{lab_action.__version__}")


def test_no_input_is_named_after_a_reserved_key():
    """
    GitHub keeps `entrypoint` and `args` for itself inside `with:` on a
    container action, and feeds them to the docker run. An input by
    either name is passed as INPUT_* and also silently overrides the
    image, which fails before the action starts.
    """
    assert not {"entrypoint", "args"} & set(action()["inputs"])


def test_the_robot_action_declares_the_same_inputs_and_outputs():
    """Two files because GitHub pins one image per action."""
    robot = action("robot/action.yml")

    assert robot["inputs"] == action()["inputs"]
    assert robot["outputs"] == action()["outputs"]


def test_the_robot_action_points_at_the_tag_for_this_version():
    """So bumping the version without republishing fails here."""
    image = action("robot/action.yml")["runs"]["image"]

    assert image.endswith(f":{lab_action.__version__}-robot")
    assert image.startswith("docker://ghcr.io/")
