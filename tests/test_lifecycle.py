"""The lab lifecycle, against the stub in tests/stubs."""

import pytest

pytestmark = pytest.mark.lifecycle


def lab(**extra):
    """The inputs a lab run needs. Keywords override them."""
    return {
        "dut_pool": "rpi5",
        "dut_control_client_key": "a-client-key",
        "dut_control_url": "http://lab.invalid:8000",
        "runner": "command",
        "run": "true",
        **extra,
    }


def test_no_pool_means_the_lab_is_never_contacted(run_action):
    done = run_action(runner="command", run="true")

    assert done.returncode == 0
    assert done.calls == []


def test_a_device_is_reserved_and_handed_back(run_action):
    done = run_action(**lab())

    assert done.returncode == 0
    assert done.calls == [
        "reserve rpi5 --json --retries 15 --retries-wait 60s",
        "power off -q",
        "wipe -q",
        "lease -q",
    ]


def test_the_device_goes_back_after_a_failing_suite(run_action):
    """The reservation lasts two hours if nobody leases it."""
    done = run_action(**lab(run="sh", run_args="-c 'exit 7'"))

    assert done.returncode == 7
    assert done.calls[-1] == "lease -q"


def test_the_device_goes_back_after_a_broken_entry_point(run_action):
    done = run_action(**lab(run="no-such-program"))

    assert done.returncode == 2
    assert done.calls[-1] == "lease -q"
    assert "entry point not found" in done.stdout


def test_a_reservation_that_is_refused_releases_nothing(run_action):
    """A bare lease would hand back every reservation this key holds."""
    done = run_action(**lab(), stub={"DUT_STUB_RESERVE_FAIL": "1"})

    assert done.returncode == 2
    assert done.calls == [
        "reserve rpi5 --json --retries 15 --retries-wait 60s"]
    assert "could not reserve from rpi5" in done.stdout


def test_a_release_that_fails_only_warns(run_action):
    done = run_action(**lab(), stub={"DUT_STUB_LEASE_FAIL": "1"})

    assert done.returncode == 0
    assert "::warning::could not release stub-rpi5-01" in done.stdout


def test_the_token_is_masked_before_anything_could_carry_it(run_action):
    done = run_action(**lab())

    assert "::add-mask::a-secret-token" in done.stdout
    masked = done.stdout.index("::add-mask::a-secret-token")
    assert "a-secret-token" not in done.stdout[masked + 40:]


def test_the_suite_is_told_where_the_device_is(run_action):
    done = run_action(**lab(
        run="sh",
        run_args="-c 'echo $DUT_NAME $DUT_IP $DUT_SSH_PORT'"))

    assert "stub-rpi5-01 192.0.2.40 22" in done.stdout


def test_the_suite_is_not_given_the_client_key(run_action):
    """The token drives one device; the key reserves everyone else's."""
    done = run_action(**lab(
        run="sh",
        run_args="-c 'echo [${DUT_CONTROL_CLIENT_KEY-unset}]'"))

    assert "[unset]" in done.stdout


def test_the_log_says_which_device_ran(run_action):
    """Not an output: by the time one is read, this is someone else's."""
    done = run_action(**lab())

    assert "reserved stub-rpi5-01" in done.stdout
    assert "released stub-rpi5-01" in done.stdout


def test_a_pool_without_a_key_is_refused_before_anything_is_taken(run_action):
    done = run_action(dut_pool="rpi5", runner="command", run="true")

    assert done.returncode == 2
    assert done.calls == []
    assert "dut_control_client_key is required" in done.stdout


def an_image(workspace, name="core-image.wic.bz2"):
    image = workspace / name
    image.write_bytes(b"an image")
    return image


def test_an_image_is_written_before_the_suite_runs(run_action, workspace):
    """Down, write, up: the storage moves while nothing is using it."""
    image = an_image(workspace)

    done = run_action(**lab(dut_image=image.name))

    assert done.returncode == 0
    assert done.calls == [
        "reserve rpi5 --json --retries 15 --retries-wait 60s",
        "power off -q",
        f"flash --upload {image} -q",
        "power on -q",
        "wait",
        "power off -q",
        "wipe -q",
        "lease -q",
    ]


def test_an_image_that_is_not_there_costs_no_reservation(run_action):
    done = run_action(**lab(dut_image="build/never-built.wic.bz2"))

    assert done.returncode == 2
    assert done.calls == []
    assert "dut_image does not exist" in done.stdout


def test_a_failed_flash_still_hands_the_device_back(run_action, workspace):
    image = an_image(workspace)

    done = run_action(**lab(dut_image=image.name),
                      stub={"DUT_STUB_FLASH_FAIL": "1"})

    assert done.returncode == 2
    assert "could not flash stub-rpi5-01" in done.stdout
    assert done.calls[-1] == "lease -q"


def test_storage_that_cannot_be_cleared_does_not_fail_the_run(run_action):
    """The result is valid; the device has already left the pool."""
    done = run_action(**lab(), stub={"DUT_STUB_WIPE_FAIL": "1"})

    assert done.returncode == 0
    assert "::warning::could not clear stub-rpi5-01" in done.stdout
    assert done.calls[-1] == "lease -q"


def test_a_missing_service_url_is_called_out(run_action):
    """Otherwise it surfaces as a refused connection to localhost."""
    done = run_action(**lab(dut_control_url=""))

    assert done.returncode == 0
    assert "::warning::dut_control_url is empty" in done.stdout
