"""Checks against the device the action reserved and flashed.

Skipped when there is none, so the same suite runs on the runner and
in the lab. Logging in uses the empty root password a Moonforge image
built with kas/common/debug.yml leaves; without that fragment there is
no SSH server at all.
"""

import os
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DUT_IP"),
    reason="no device; set dut_pool to run these")

SSH = (
    "sshpass", "-p", "",
    "ssh",
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "LogLevel=ERROR",
    "-o", "ConnectTimeout=10",
    # The password is empty, not absent: offering a key first would
    # only slow the handshake down.
    "-o", "PubkeyAuthentication=no",
    "-o", "PreferredAuthentications=password",
)


def on_device(command):
    """Run a command on the device and return what it printed."""
    done = subprocess.run(
        [*SSH,
         "-p", os.environ.get("DUT_SSH_PORT", "22"),
         "root@" + os.environ["DUT_IP"],
         command],
        capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr.strip()
    return done.stdout.strip()


def test_the_device_runs_the_image_that_was_flashed():
    assert on_device(". /etc/os-release && echo $ID") == "moonforge"


def test_the_root_filesystem_is_read_only():
    """Moonforge is immutable; a writable root means the wrong image."""
    assert "ro" in on_device("findmnt -no OPTIONS /").split(",")


def test_data_is_a_writable_overlay():
    """Everything that has to survive a reboot lives there."""
    on_device("echo written > /data/lab-moonforge-action.check")

    assert on_device("cat /data/lab-moonforge-action.check") == "written"
