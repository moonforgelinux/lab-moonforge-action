import os
import shlex

import pytest

from lab_action import main, runner


@pytest.fixture
def outputs(tmp_path, monkeypatch):
    """Read back what the action told the workflow."""
    path = tmp_path / "outputs"
    path.touch()
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))

    def read():
        pairs = (line.split("=", 1) for line in path.read_text().split("\n")
                 if "=" in line)
        return {name: value for name, value in pairs}
    return read


def shell(given, script, **rest):
    """Run a shell snippet as the entry point."""
    given(runner="command", entrypoint="sh",
          args="-c " + shlex.quote(script), **rest)
    return main.main()


def test_a_passing_entry_point_reports_zero(workspace, given):
    assert shell(given, "true") == 0


def test_a_snippet_carrying_a_quote_reaches_the_shell_whole(workspace,
                                                            given):
    """shlex.quote keeps this in one argument; hand-written quotes do not."""
    shell(given, "echo \"it's fine\" > seen")
    assert (workspace / "seen").read_text().strip() == "it's fine"


def test_the_exit_status_of_the_entry_point_becomes_ours(workspace, given):
    assert shell(given, "exit 7") == 7


def test_the_output_directory_is_created(workspace, given):
    shell(given, "true")
    assert (workspace / "test-results").is_dir()


def test_the_entry_point_runs_from_workdir(workspace, given):
    (workspace / "tests").mkdir()
    shell(given, "pwd > where", workdir="tests")
    assert (workspace / "tests" / "where").read_text().strip() == str(
        workspace / "tests")


def test_the_outputs_describe_the_run(workspace, given, outputs):
    shell(given, "exit 3")
    assert outputs() == {"outdir": "test-results", "exit_code": "3"}


def test_the_reported_outdir_is_relative_to_the_workspace(workspace, given,
                                                          outputs):
    (workspace / "tests").mkdir()
    shell(given, "true", workdir="tests", outdir="results")
    assert outputs()["outdir"] == "tests/results"


def test_env_lines_reach_the_entry_point(workspace, given):
    shell(given, "echo $DEVICE_HOST > seen",
          env="DEVICE_HOST=192.168.1.40\nBOARD=raspberrypi5")
    assert (workspace / "seen").read_text().strip() == "192.168.1.40"


def test_the_working_and_output_directories_are_exported(workspace, given):
    shell(given, "echo $MOONFORGE_TEST_OUTDIR > seen")
    assert (workspace / "seen").read_text().strip() == str(
        workspace / "test-results")


def test_a_malformed_env_line_is_refused(workspace, given, capsys):
    given(entrypoint="true", runner="command", env="DEVICE_HOST 192.168.1.40")
    with pytest.raises(SystemExit):
        main.main()
    assert "env takes NAME=VALUE lines" in capsys.readouterr().out


def test_a_missing_entry_point_says_so(workspace, given, capsys):
    given(entrypoint="no-such-program", runner="command")
    with pytest.raises(SystemExit):
        main.main()
    assert "entry point not found" in capsys.readouterr().out


def test_an_entry_point_that_cannot_be_executed_says_so(workspace, given,
                                                        capsys):
    script = workspace / "run.sh"
    script.write_text("#!/bin/sh\n")
    script.chmod(0o644)
    given(entrypoint="run.sh", runner="command")

    with pytest.raises(SystemExit):
        main.main()
    assert "not executable" in capsys.readouterr().out


def test_what_we_wrote_is_handed_back_to_the_checkout_owner(workspace, given,
                                                            monkeypatch):
    """Root-owned leftovers break the next job, not this one."""
    chowned = []
    monkeypatch.setattr(os, "chown",
                        lambda path, uid, gid: chowned.append((path, uid,
                                                               gid)))
    shell(given, "touch $MOONFORGE_TEST_OUTDIR/report.xml")

    owner = workspace.stat()
    outdir = workspace / "test-results"
    assert (outdir, owner.st_uid, owner.st_gid) in chowned
    assert (outdir / "report.xml", owner.st_uid, owner.st_gid) in chowned


def test_a_workspace_we_cannot_hand_back_only_warns(workspace, given,
                                                    monkeypatch, capsys):
    def refuse(*_):
        raise PermissionError("not permitted")

    monkeypatch.setattr(os, "chown", refuse)
    assert shell(given, "true") == 0
    assert "could not hand" in capsys.readouterr().out


def test_the_plan_and_the_run_agree_on_the_output_directory(workspace, given):
    given(entrypoint="suite", workdir=".", outdir="results")
    assert runner.plan().outdir == workspace / "results"
