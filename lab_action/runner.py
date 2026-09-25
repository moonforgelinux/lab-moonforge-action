"""Working out what to run, and where, from the inputs."""

import os
import shlex
from pathlib import Path
from typing import NamedTuple

from . import inputs

RUNNERS = ("pytest", "command")
DEFAULT_OUTDIR = "test-results"


class Plan(NamedTuple):
    runner: str
    command: list
    workdir: Path
    outdir: Path


def workspace():
    """The checkout, as the container sees it."""
    return Path(os.environ.get("GITHUB_WORKSPACE") or os.getcwd()).resolve()


def check_under(path, root, what):
    """Refuse a path that points outside the tree it belongs to."""
    if not path.is_relative_to(root):
        inputs.fail(f"{what} is outside the workspace: {path}")


def arguments():
    """Any number of arguments, split the way a shell would split them."""
    return shlex.split(inputs.get("args"))


def directories():
    root = workspace()

    workdir = (root / inputs.get("workdir", ".")).resolve()
    check_under(workdir, root, "workdir")
    if not workdir.is_dir():
        inputs.fail("workdir does not exist: " + str(workdir))

    outdir = (workdir / inputs.get("outdir", DEFAULT_OUTDIR)).resolve()
    check_under(outdir, root, "outdir")
    return workdir, outdir


def pytest_command(entrypoint, args, outdir):
    """Our flags come first, so the caller's own flags win over them."""
    return [
        "pytest",
        f"--junitxml={outdir / 'junit.xml'}",
        "-o", f"cache_dir={outdir / 'pytest-cache'}",
        *args,
        entrypoint,
    ]


def direct_command(entrypoint, args, workdir):
    """A file from the checkout if there is one, otherwise from PATH."""
    candidate = workdir / entrypoint
    program = str(candidate) if candidate.is_file() else entrypoint
    return [program, *args]


def plan():
    """Check everything that can be wrong before anything is touched."""
    runner = inputs.get("runner", "pytest")
    if runner not in RUNNERS:
        inputs.fail("unknown runner: " + runner)

    entrypoint = inputs.get("entrypoint", required=True)
    workdir, outdir = directories()
    args = arguments()

    if runner == "pytest":
        command = pytest_command(entrypoint, args, outdir)
    else:
        command = direct_command(entrypoint, args, workdir)
    return Plan(runner, command, workdir, outdir)
