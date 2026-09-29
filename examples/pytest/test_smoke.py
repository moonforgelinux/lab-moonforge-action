"""What every suite can count on the action having set up."""

import os
from pathlib import Path


def test_the_output_directory_exists_and_is_ours():
    outdir = Path(os.environ["MOONFORGE_TEST_OUTDIR"])
    assert outdir.is_dir()

    (outdir / "smoke.txt").write_text("the suite wrote this\n")


def test_the_suite_runs_from_workdir():
    assert Path.cwd() == Path(os.environ["MOONFORGE_TEST_WORKDIR"])
