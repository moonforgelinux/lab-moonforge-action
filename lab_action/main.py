"""The action itself: run what was planned, and report the result."""

import os
import subprocess

from . import dut, inputs, runner


def environment(plan, lab=None):
    """The environment the entry point runs with."""
    env = dict(os.environ)
    for line in inputs.lines("env"):
        name, separator, value = line.partition("=")
        if not separator:
            inputs.fail("env takes NAME=VALUE lines, got: " + line)
        env[name.strip()] = value

    env["MOONFORGE_TEST_WORKDIR"] = str(plan.workdir)
    env["MOONFORGE_TEST_OUTDIR"] = str(plan.outdir)
    if lab:
        env.update(lab.environment())
    dut.strip_secrets(env)
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
    if not outdir.is_dir():
        return

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
    lab = dut.borrow()
    status = inputs.FAILURE

    try:
        if lab:
            lab.reserve()
        status = execute(made, environment(made, lab))
    finally:
        # The device goes back however this ended, a crash of our
        # own included. A reservation nobody releases holds it for
        # two hours.
        if lab:
            lab.release()
        hand_back(made.outdir, runner.workspace())
        report(made, status)

    return status
