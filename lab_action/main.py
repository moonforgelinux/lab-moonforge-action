"""The action itself: run what was planned, and report the result."""

import os
import subprocess

from . import inputs, runner


def environment(plan):
    """The environment the entry point runs with."""
    env = dict(os.environ)
    for line in inputs.lines("env"):
        name, separator, value = line.partition("=")
        if not separator:
            inputs.fail("env takes NAME=VALUE lines, got: " + line)
        env[name.strip()] = value

    env["MOONFORGE_TEST_WORKDIR"] = str(plan.workdir)
    env["MOONFORGE_TEST_OUTDIR"] = str(plan.outdir)
    return env


def execute(plan, env):
    plan.outdir.mkdir(parents=True, exist_ok=True)
    try:
        done = subprocess.run(plan.command, cwd=plan.workdir, env=env)
    except FileNotFoundError:
        inputs.fail("entry point not found: " + plan.command[0])
    except PermissionError:
        inputs.fail("entry point is not executable: " + plan.command[0])
    return done.returncode


def hand_back(outdir, reference):
    """
    Give what we wrote back to the owner of the checkout.

    The container runs as root. Files owned by root break the next
    job's checkout.
    """
    owner = reference.stat()
    try:
        for entry in [outdir, *outdir.rglob("*")]:
            os.chown(entry, owner.st_uid, owner.st_gid)
    except OSError as error:
        inputs.warn(f"could not hand {outdir} back: {error}")


def report(plan, status):
    inputs.set_output("outdir", plan.outdir.relative_to(runner.workspace()))
    inputs.set_output("exit_code", status)


def main():
    made = runner.plan()
    status = execute(made, environment(made))
    hand_back(made.outdir, runner.workspace())
    report(made, status)
    return status
