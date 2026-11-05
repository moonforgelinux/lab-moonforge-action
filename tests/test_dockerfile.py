import re
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"


def instructions(keyword):
    for line in DOCKERFILE.read_text().splitlines():
        if line.startswith(keyword + " "):
            yield line.split(None, 1)[1]


def test_the_base_image_is_pinned_by_digest():
    """A tag moves, and then a rebuilt release is not the same image."""
    bases = list(instructions("FROM"))
    assert bases
    for base in bases:
        assert re.search(r"@sha256:[0-9a-f]{64}$", base), base


def test_dut_control_is_pinned_by_commit():
    refs = list(instructions("ARG"))
    pin = [ref for ref in refs if ref.startswith("DUT_CONTROL_REF=")]
    assert pin, refs
    assert re.fullmatch(r"DUT_CONTROL_REF=[0-9a-f]{40}", pin[0]), pin[0]


def test_the_robot_stack_prefers_wheels():
    """
    Without it, pip takes a newer sdist over an older wheel. There is
    no compiler in the image, so the build breaks the day a package
    ships a release without a musl wheel, as PyMuPDF 2.1 did.
    """
    robot = DOCKERFILE.with_name("Dockerfile.robot").read_text()
    installs = [line for line in robot.splitlines() if "pip install" in line]

    assert installs
    for line in installs:
        assert "--prefer-binary" in line, line
