from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

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


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


@pytest.fixture
def served(tmp_path):
    """
    A directory, and the URL it is served from.

    A real server, so the test exercises the download itself. A stubbed
    urlopen would pass just as well with the wrong call in it.
    """
    handler = partial(_Quiet, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield tmp_path, "http://127.0.0.1:%d" % server.server_port
    finally:
        server.shutdown()


def an_image_at(given, served):
    directory, url = served
    name = "moonforge.wic.bz2"
    (directory / name).write_bytes(b"an image")
    given(dut_pool="rpi5", dut_control_client_key="a-key",
          dut_image=url + "/" + name)
    return directory


def test_an_image_url_is_downloaded(given, served, workspace):
    """No bmap is served here, so this covers going without one too."""
    an_image_at(given, served)

    image = dut.borrow(workspace).image

    assert image.read_bytes() == b"an image"
    assert image.name == "moonforge.wic.bz2"
    assert not list(image.parent.glob("*.bmap"))


def test_the_bmap_beside_the_url_comes_too(given, served, workspace):
    directory = an_image_at(given, served)
    (directory / "moonforge.wic.bmap").write_bytes(b"a bmap")

    image = dut.borrow(workspace).image

    beside = image.with_suffix(".bmap")
    assert beside.read_bytes() == b"a bmap"


def test_a_url_that_does_not_answer_fails(given, served, workspace):
    _, url = served
    given(dut_pool="rpi5", dut_control_client_key="a-key",
          dut_image=url + "/not-there.wic.bz2")

    with pytest.raises(SystemExit):
        dut.borrow(workspace)


def test_a_url_naming_no_file_fails(given, served, workspace):
    _, url = served
    given(dut_pool="rpi5", dut_control_client_key="a-key", dut_image=url)

    with pytest.raises(SystemExit):
        dut.borrow(workspace)
