"""Borrowing a device from a dut-control lab, and handing it back."""

import json
import os
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from . import inputs

CLIENT = "dut-control-client"
# Wait 15 minutes for a free device, asking once a minute. Long
# enough for a board to come free. Short enough not to hold a runner
# for the whole morning.
RETRIES = 15
POLL = 60

# The token drives the device this run was given. The client key
# would reserve and release other people's.
SECRETS = ("DUT_CONTROL_CLIENT_KEY",)


def strip_secrets(env):
    for name in SECRETS:
        env.pop(name, None)


class Lab:
    """One device, reserved for as long as the run needs it."""

    def __init__(self, workdir):
        self.pool = inputs.get("dut_pool")
        self.image = _image(workdir)
        self.reservation = {}

    @property
    def token(self):
        return self.reservation.get("token", "")

    @property
    def name(self):
        return self.reservation.get("dut-name", "")

    def settings(self):
        """What the client reads from the environment."""
        env = dict(os.environ)
        given = {
            "DUT_CONTROL_URL": inputs.get("dut_control_url"),
            "DUT_CONTROL_CLIENT_KEY": inputs.get("dut_control_client_key"),
            "DUT_CONTROL_TOKEN": self.token,
        }
        env.update({name: value for name, value in given.items() if value})
        return env

    def client(self, *arguments, capture=False):
        """Run the client, with the token in the environment not the argv."""
        try:
            return subprocess.run(
                [CLIENT, *arguments], env=self.settings(),
                capture_output=capture, text=True)
        except FileNotFoundError:
            inputs.fail(CLIENT + " is not installed in this image")

    def reserve(self):
        """Take a device, waiting out a pool that is merely busy."""
        inputs.log(f"::group::reserving a device from {self.pool}")
        done = self.client(
            "reserve", self.pool, "--json",
            "--retries", str(RETRIES),
            "--retries-wait", f"{POLL}s",
            capture=True)
        inputs.log("::endgroup::")

        if done.returncode:
            inputs.fail("could not reserve from " + self.pool +
                        ": " + done.stderr.strip())

        # Mask it now. Masking only covers what is logged after it.
        self.reservation = json.loads(done.stdout)
        inputs.mask(self.token)
        inputs.log(f"reserved {self.name} at {self.reservation.get('ip')}")

    def flash(self):
        """Power down, write the image, and wait for it to come back up."""
        if not self.image:
            return

        inputs.log(f"flashing {self.image.name} onto {self.name}")
        # The image is uploaded, not named. The lab cannot reach a
        # container back. The wait is the client's default, which is
        # five minutes.
        steps = (
            ("could not power off", ("power", "off", "-q")),
            ("could not flash", ("flash", "--upload", str(self.image),
                                 "-q")),
            ("could not power on", ("power", "on", "-q")),
            ("gave up waiting for", ("wait",)),
        )
        for complaint, arguments in steps:
            if self.client(*arguments).returncode:
                inputs.fail(f"{complaint} {self.name}")

    def release(self):
        """Clear the device storage and hand the device back."""
        if not self.token:
            return

        # Zero the head of the storage: the partition table, /boot
        # and the start of the root filesystem. The next tenant finds
        # nothing of this run. It goes through the node, like the
        # flash, so it works on a device that crashed. Power down
        # first, or the storage moves while the device uses it.
        for step in (("power", "off", "-q"), ("wipe", "-q")):
            if self.client(*step).returncode:
                # The service already took this device out of
                # rotation. Failing here would throw away a good
                # test result.
                inputs.warn("could not clear " + self.name)
                break

        if self.client("lease", "-q").returncode:
            inputs.warn("could not release " + self.name)
        else:
            inputs.log("released " + self.name)

    def environment(self):
        """What a suite needs to reach the device."""
        # The tunnelled port is left out. It is on the runner's
        # localhost, which this container does not share.
        return {
            "DUT_NAME": self.name,
            "DUT_POOL": self.pool,
            "DUT_IP": str(self.reservation.get("ip", "")),
            "DUT_SSH_PORT": str(self.reservation.get("ssh-port", "")),
            "DUT_TOKEN": self.token,
        }


def _fetch(url, into):
    """Save a URL into a directory. Returns the local path."""
    name = Path(urllib.parse.urlparse(url).path).name
    if not name:
        inputs.fail("dut_image names no file: " + url)

    target = into / name
    try:
        with urllib.request.urlopen(url) as response:
            with target.open("wb") as handle:
                shutil.copyfileobj(response, handle)
    except OSError as error:
        inputs.fail(f"could not fetch {url}: {error}")
    return target


def _fetch_bmap(url, image):
    """
    Best effort, like the client's own search for one beside the image.

    Two names are conventional, so both are tried. Without a bmap the
    flash writes the whole image instead of the mapped blocks.
    """
    base = url.rsplit("/", 1)[0]
    for name in (image.with_suffix(".bmap").name, image.name + ".bmap"):
        target = image.parent / name
        try:
            with urllib.request.urlopen(base + "/" + name) as response:
                with target.open("wb") as handle:
                    shutil.copyfileobj(response, handle)
            return
        except OSError:
            target.unlink(missing_ok=True)


def _image(workdir):
    """
    The image to flash: a path in the checkout, or a URL to fetch.

    Fetched and checked before a device is taken, so a bad URL costs a
    second rather than a reservation.
    """
    given = inputs.get("dut_image")
    if not given:
        return None

    if urllib.parse.urlparse(given).scheme in ("http", "https"):
        inputs.log("fetching " + given.split("?")[0])
        # Not cleaned up: the container is thrown away with it.
        into = Path(tempfile.mkdtemp(prefix="lab-image-"))
        image = _fetch(given, into)
        _fetch_bmap(given, image)
        return image

    image = (workdir / given).resolve()
    if not image.is_file():
        inputs.fail("dut_image does not exist: " + str(image))
    return image


def borrow(workdir):
    """A device to run on, or nothing when no pool was named."""
    if not inputs.get("dut_pool"):
        return None

    lab = Lab(workdir)
    if not inputs.get("dut_control_client_key"):
        inputs.fail("dut_control_client_key is required with dut_pool")
    inputs.mask(inputs.get("dut_control_client_key"))

    # Not an error: the service may well be on the runner itself. But
    # the client then talks to localhost, and a refused connection
    # there is hard to trace back to an empty input.
    if not inputs.get("dut_control_url"):
        inputs.warn("dut_control_url is empty; the client will use its "
                    "own default")
    return lab
