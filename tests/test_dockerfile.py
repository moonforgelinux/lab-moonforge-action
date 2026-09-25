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
