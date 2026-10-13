import pytest

from lab_action import inputs, runner


def test_arguments_of_an_unset_input_is_empty():
    assert runner.arguments() == []


def test_arguments_splits_a_single_line_the_way_a_shell_would(given):
    given(run_args='-k "not slow" --reruns 2')
    assert runner.arguments() == ["-k", "not slow", "--reruns", "2"]


def test_arguments_treats_newlines_as_whitespace(given):
    given(run_args="-k\nsmoke\n--reruns\n2\n")
    assert runner.arguments() == ["-k", "smoke", "--reruns", "2"]


def test_arguments_keeps_a_quoted_value_in_one_piece(given):
    given(run_args='--deselect\n"tests/test_a.py::test_b[a b]"')
    assert runner.arguments() == [
        "--deselect", "tests/test_a.py::test_b[a b]",
    ]


def test_arguments_takes_as_many_as_it_is_given(given):
    given(run_args="\n".join(f"--flag-{n}" for n in range(64)))
    assert len(runner.arguments()) == 64


def test_workdir_defaults_to_the_workspace_root(workspace):
    assert runner.directories()[0] == workspace


def test_workdir_is_resolved_against_the_workspace(workspace, given):
    (workspace / "tests").mkdir()
    given(workdir="tests")
    assert runner.directories()[0] == workspace / "tests"


def test_workdir_has_to_exist(workspace, given, capsys):
    given(workdir="nowhere")
    with pytest.raises(SystemExit):
        runner.directories()
    assert "workdir does not exist" in capsys.readouterr().out


@pytest.mark.parametrize("workdir", ["../elsewhere", "/etc"])
def test_workdir_may_not_leave_the_workspace(workspace, given, capsys,
                                             workdir):
    given(workdir=workdir)
    with pytest.raises(SystemExit) as exit_info:
        runner.directories()

    assert exit_info.value.code == inputs.FAILURE
    assert "workdir is outside the workspace" in capsys.readouterr().out


def test_outdir_defaults_to_a_directory_under_workdir(workspace, given):
    (workspace / "tests").mkdir()
    given(workdir="tests")
    assert runner.directories()[1] == workspace / "tests" / "test-results"


def test_outdir_may_not_leave_the_workspace(workspace, given, capsys):
    given(outdir="../../somewhere")
    with pytest.raises(SystemExit):
        runner.directories()
    assert "outdir is outside the workspace" in capsys.readouterr().out


def test_pytest_command_reports_into_outdir(tmp_path):
    command = runner.pytest_command("suite", [], tmp_path)
    assert command[0] == "pytest"
    assert f"--junitxml={tmp_path}/junit.xml" in command
    assert f"cache_dir={tmp_path}/pytest-cache" in command


def test_pytest_command_lets_the_caller_override_our_flags(tmp_path):
    command = runner.pytest_command("suite", ["--junitxml=mine.xml"],
                                    tmp_path)
    ours = command.index(f"--junitxml={tmp_path}/junit.xml")
    assert ours < command.index("--junitxml=mine.xml")


def test_pytest_command_ends_with_the_entry_point(tmp_path):
    command = runner.pytest_command("suite", ["-x"], tmp_path)
    assert command[-1] == "suite"


def test_a_command_runner_prefers_a_file_from_the_checkout(tmp_path):
    script = tmp_path / "run-tests.sh"
    script.write_text("#!/bin/sh\n")
    command = runner.direct_command("run-tests.sh", ["rpi5"], tmp_path)
    assert command == [str(script), "rpi5"]


def test_a_command_runner_falls_back_to_a_program_on_path(tmp_path):
    assert runner.direct_command("true", [], tmp_path) == ["true"]


def test_an_unknown_runner_is_refused(workspace, given, capsys):
    given(runner="cucumber", run="suite")
    with pytest.raises(SystemExit):
        runner.plan()
    assert "unknown runner: cucumber" in capsys.readouterr().out


def test_something_to_run_is_required(workspace, given, capsys):
    given(runner="pytest")
    with pytest.raises(SystemExit):
        runner.plan()
    assert "run is required" in capsys.readouterr().out


def test_a_plan_carries_the_command_and_the_directories(workspace, given):
    (workspace / "tests").mkdir()
    given(run="integration", workdir="tests", run_args="-x")

    made = runner.plan()

    assert made.command[0] == "pytest"
    assert made.workdir == workspace / "tests"
    assert made.outdir == workspace / "tests" / "test-results"
    assert made.command[-2:] == ["-x", "integration"]


def test_a_plan_for_a_command_runner_leaves_the_command_alone(workspace,
                                                              given):
    given(runner="command", run="true", run_args="--now")

    assert runner.plan().command == ["true", "--now"]
