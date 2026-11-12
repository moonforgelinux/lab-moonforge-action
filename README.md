# lab-moonforge-action

Runs a test suite for images based on [Moonforge](https://github.com/moonforgelinux/meta-moonforge) checkout. It runs in a container with its own Python stack, so nothing has to be installed on the runner.

It uses a DUT from pool and the run gets the lab lifecycle around it: reserve a device, flash it, wait for it to boot, test, clear it, hand it back.

> [!NOTE]
> The whole lifecycle has run against a real board, and the example suite passed on it. What is still only stub-tested is the failure paths: a flash that fails, a board that never comes up. `.github/workflows/hardware.yml` is the manual run, and it needs a device and a `DUT_CONTROL_CLIENT_KEY` secret.

## Usage

On the runner, with no hardware involved:

```yml
jobs:
  test:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v4
      - uses: moonforgelinux/lab-moonforge-action@v0.1.0
        with:
          workdir: tests
          run: integration
          run_args: -k "not slow" --reruns 2
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-results
          path: tests/test-results
```

On a device from the lab, flashing it first:

```yml
      - uses: moonforgelinux/lab-moonforge-action@v0.1.0
        with:
          workdir: tests
          run: integration
          dut_pool: rpi5
          dut_image: build/tmp/deploy/images/raspberrypi5/moonforge-image-base.rootfs.wic.bz2
          dut_control_url: ${{ vars.DUT_CONTROL_URL }}
          dut_control_client_key: ${{ secrets.DUT_CONTROL_CLIENT_KEY }}
```

## Inputs

| Input | Description | Default |
| --- | --- | --- |
| `run` | What to run: a test path for `pytest`, a suite for `robot`, a program for `command`. Required | |
| `run_args` | Arguments for it, any number of them, split the way a shell would | `''` |
| `runner` | `pytest`, `robot` or `command` | `pytest` |
| `workdir` | Directory in the checkout the tests live in; the run happens from here | `.` |
| `outdir` | Directory for reports, relative to `workdir` | `test-results` |
| `env` | One `NAME=VALUE` per line, exported to what is run | `''` |

### Lab hardware

All optional. Leave `dut_pool` empty and none of the rest applies.

| Input | Description | Default |
| --- | --- | --- |
| `dut_pool` | Pool to reserve a device from. Setting it turns on everything below | `''` |
| `dut_control_url` | Base URL of the dut-control service | `''` |
| `dut_control_client_key` | Client key. Required whenever `dut_pool` is set | `''` |
| `dut_image` | Image to flash before testing. A path relative to `workdir`, or an `http`/`https` URL. Empty uses the device as it is | `''` |

A device is asked for by pool, not by name. To reach one board, give it a pool of its own in the lab configuration. A board can be in several pools at once.

## Outputs

| Output | Description |
| --- | --- |
| `outdir` | Output directory, relative to the workspace root, ready to hand to `upload-artifact` |
| `exit_code` | Exit status of what was run. `1` usually means the suite failed, `2` that the request was wrong |

The step already fails when the run fails. `exit_code` is for a workflow with `continue-on-error` that wants to tell a failed suite from a bad request.

## What the suite gets

| Variable | |
| --- | --- |
| `MOONFORGE_TEST_WORKDIR` | Where the run happens |
| `MOONFORGE_TEST_OUTDIR` | Where reports go |

With `dut_pool` set, and only while the device is held:

| Variable | |
| --- | --- |
| `DUT_NAME` | Device name, as the lab knows it |
| `DUT_POOL` | Pool it came from |
| `DUT_IP` | Address of the device |
| `DUT_SSH_PORT` | Its SSH port |
| `DUT_TOKEN` | Reservation token, enough to drive power and status |

`DUT_CONTROL_CLIENT_KEY` is deliberately **not** passed on: the token drives the device the run was given, while the client key would reserve and release everyone else's.

A suite logs in with an empty root password. A Moonforge image built with `kas/common/debug.yml` leaves it that way, and that is what CI builds. An image without that fragment has no SSH server at all.

## Examples

`examples/robot` is both of those written for Robot Framework, using `SSHLibrary` instead of `sshpass`. `device.robot` skips its whole suite in `Suite Setup` when `DUT_IP` is unset, which is the Robot equivalent of the pytest skip.

`examples/pytest` is a suite that runs either way. Two checks need nothing but the action. Three log in to the device. They check that it runs the image that was flashed, that the root filesystem is read only, and that `/data` is a writable overlay. Those three skip themselves when `DUT_IP` is unset, so the same suite passes on the runner and in the lab.

## Robot Framework

The `robot` runner needs a second image, and a second action to pick it:

```yml
      - uses: moonforgelinux/lab-moonforge-action/robot@v0.1.0
        with:
          runner: robot
          workdir: suites
          run: smoke.robot
```

It is the default image plus `robotframework`, `robotframework-sshlibrary`, `robotframework-doctestlibrary` and `robotframework-seleniumlibrary`, so everything above works there too, `pytest` included. Robot writes `log.html`, `report.html`, `output.xml` and `xunit.xml` into `outdir`.

It is a separate tag because of what the doctest library drags behind it. OpenCV, PyMuPDF, scipy, scikit-image, ImageMagick, zbar, libdmtx and tesseract take the image from 123 MB to about a gigabyte. PyMuPDF has no musl wheel for aarch64, so this tag is **amd64 only**, while the default one is both.

Asking for `runner: robot` on the default image fails before a device is reserved, with a message saying which image to use.

## The lab lifecycle

With `dut_pool` set, the run becomes:

```
reserve      wait for a device, up to fifteen minutes
power off    the storage is about to move to the lab node
flash        the image is uploaded with the request, and its bmap with it
power on
wait         until the device answers SSH, up to five minutes
             <the suite runs>
power off
wipe         zeros over the head of the storage
lease        hand the device back
```

Without `dut_image`, the three flashing steps are skipped and the device is used in whatever state it is in.

Given a URL, the action downloads the image itself, before taking a device. It looks for a `.bmap` next to it under the two conventional names and downloads that too when it is there; a bmap makes the flash write only the blocks it has to. There is no need for a step of your own to fetch the image first.

The last three steps always run. That covers a failing suite, nothing to run, and a crash of the action itself. A reservation nobody hands back holds the device for two hours.

Everything that can be wrong is checked before a device is taken: nothing to run, a `workdir` outside the checkout, an image that was never built. A typo should cost a second, not a device.

The wipe goes through the lab node, not through the device. It works on a board this run crashed. It zeroes the partition table, `/boot` and the start of the root filesystem, so the device does not boot until the next run flashes it.

A wipe that fails only warns. The service has already taken that device out of rotation, and a test result that is good should not be thrown away for it.

## Running against a board

`.github/workflows/hardware.yml` is a manual run. It takes a pool and the URL of a Moonforge image, flashes a device and runs `examples/pytest/test_device.py` on it.

It is the only thing that tests what the stubs cannot: that dut-control answers the way the stub pretends to, and that the image boots after the action writes it. It needs a self-hosted runner that can reach the dut-control service over HTTP. The runner does not have to be reachable back, because the image is uploaded with the request.

## Developing

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[test,lint]'

pytest                                # unit and lifecycle tests, no container
./.github/scripts/run-all-sanatizers  # radon, pycodestyle, pyflakes, shellcheck, commits
```

The lifecycle tests put a stub `dut-control-client` first on `PATH` and check the exact sequence of lab calls. That tests the order without a lab. What they cannot test is whether the stub matches the service.

Running the image itself:

```sh
podman build -t lab-moonforge-action .
CONTAINER_ENGINE=podman pytest -m docker

podman run --rm -v "$PWD:/github/workspace" \
  -e GITHUB_WORKSPACE=/github/workspace \
  -e INPUT_WORKDIR=examples -e INPUT_RUN=pytest \
  lab-moonforge-action
```

Inputs arrive as the `INPUT_*` environment variables GitHub sets for a container action, so a local run and a CI run take the same path.

`action.yml` names a published image, so a job pulls it instead of building one.

Releasing: bump `__version__`, point the `image:` line of `action.yml` and `robot/action.yml` at the new version, then tag `vX.Y.Z`. The tag is what builds and pushes `ghcr.io/moonforgelinux/lab-moonforge-action:X.Y.Z` for amd64 and arm64, and `:X.Y.Z-robot` for amd64. The order matters: tag last, so the tag holds an action.yml that names the image that tag publishes.

## Legal

MIT License

Copyright (c) 2026 Igalia, S.L.
