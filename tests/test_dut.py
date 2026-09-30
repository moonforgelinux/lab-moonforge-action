from pathlib import Path

import pytest

from lab_action import dut


def a_lab(given, workdir=None, **extra):
    given(dut_pool="rpi5", dut_control_client_key="a-client-key", **extra)
    return dut.Lab(workdir or Path("."))


def test_the_client_is_told_where_the_lab_is(given):
    lab = a_lab(given, dut_control_url="http://lab.invalid:8000")

    settings = lab.settings()

    assert settings["DUT_CONTROL_URL"] == "http://lab.invalid:8000"
    assert settings["DUT_CONTROL_CLIENT_KEY"] == "a-client-key"


def test_an_input_nobody_gave_is_left_out(given, monkeypatch):
    """An empty one would blank what the image set, or kill the default."""
    monkeypatch.delenv("DUT_CONTROL_URL", raising=False)

    assert "DUT_CONTROL_URL" not in a_lab(given).settings()

    monkeypatch.setenv("DUT_CONTROL_URL", "http://from-the-image:8000")

    assert a_lab(given).settings()["DUT_CONTROL_URL"] == \
        "http://from-the-image:8000"


def test_the_suite_is_told_how_to_reach_the_device(given):
    """Not the tunnelled port: it is on the runner, not in here."""
    lab = a_lab(given)
    lab.reservation = {
        "token": "a-token", "dut-name": "rpi5-01", "ip": "192.0.2.40",
        "ssh-port": 22, "tunnel-ssh-port": 5001,
    }

    assert lab.environment() == {
        "DUT_NAME": "rpi5-01",
        "DUT_POOL": "rpi5",
        "DUT_IP": "192.0.2.40",
        "DUT_SSH_PORT": "22",
        "DUT_TOKEN": "a-token",
    }


def test_an_image_without_the_client_says_so(given, capsys, monkeypatch):
    lab = a_lab(given)

    def missing(*_, **__):
        raise FileNotFoundError(dut.CLIENT)

    monkeypatch.setattr(dut.subprocess, "run", missing)

    with pytest.raises(SystemExit):
        lab.client("lease")

    assert "dut-control-client is not installed" in capsys.readouterr().out


def test_the_image_is_found_relative_to_workdir(given, workspace):
    tests = workspace / "tests"
    tests.mkdir()
    (tests / "image.wic.bz2").write_bytes(b"")
    given(dut_pool="rpi5", dut_control_client_key="a-key",
          dut_image="image.wic.bz2")

    assert dut.borrow(tests).image == tests / "image.wic.bz2"
