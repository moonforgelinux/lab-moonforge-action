import pytest

from lab_action import inputs


def test_get_returns_the_default_when_unset():
    assert inputs.get("absent", "fallback") == "fallback"


def test_get_strips_surrounding_whitespace(monkeypatch):
    monkeypatch.setenv("INPUT_RUNNER", "  pytest \n")
    assert inputs.get("runner") == "pytest"


def test_get_treats_a_blank_value_as_unset(monkeypatch):
    """GitHub sets every declared input, empty default included."""
    monkeypatch.setenv("INPUT_RUNNER", "   ")
    assert inputs.get("runner", "pytest") == "pytest"


def test_get_fails_when_a_required_input_is_missing(capsys):
    with pytest.raises(SystemExit) as exit_info:
        inputs.get("entrypoint", required=True)

    assert exit_info.value.code == inputs.FAILURE
    assert "::error::entrypoint is required" in capsys.readouterr().out


def test_get_int_reads_a_number(monkeypatch):
    monkeypatch.setenv("INPUT_DUT_BOOT_RETRIES", "7")
    assert inputs.get_int("dut_boot_retries", 10) == 7


def test_get_int_returns_the_default_when_unset():
    assert inputs.get_int("dut_boot_retries", 10) == 10


def test_get_int_fails_on_something_that_is_not_a_number(monkeypatch,
                                                         capsys):
    monkeypatch.setenv("INPUT_DUT_BOOT_RETRIES", "soon")
    with pytest.raises(SystemExit) as exit_info:
        inputs.get_int("dut_boot_retries", 10)

    assert exit_info.value.code == inputs.FAILURE
    assert "is not a number: soon" in capsys.readouterr().out


def test_lines_drops_blanks_and_strips(monkeypatch):
    monkeypatch.setenv("INPUT_RUN_ARGS", "\n -k smoke \n\n  --reruns 2\n\n")
    assert inputs.lines("run_args") == ["-k smoke", "--reruns 2"]


def test_lines_of_an_unset_input_is_empty():
    assert inputs.lines("run_args") == []


def test_mask_emits_the_directive(capsys):
    inputs.mask("s3cret")
    assert capsys.readouterr().out == "::add-mask::s3cret\n"


def test_mask_says_nothing_about_an_empty_secret(capsys):
    inputs.mask("")
    assert capsys.readouterr().out == ""


def test_warn_emits_the_directive(capsys):
    inputs.warn("the device was not wiped")
    assert "::warning::the device was not wiped" in capsys.readouterr().out


def test_set_output_appends_a_name_and_value(tmp_path, monkeypatch):
    path = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))

    inputs.set_output("runner", "pytest")
    inputs.set_output("exit_code", 0)

    assert path.read_text() == "runner=pytest\nexit_code=0\n"


def test_set_output_uses_a_delimiter_for_a_multiline_value(tmp_path,
                                                           monkeypatch):
    """Otherwise a newline in a value forges further outputs."""
    path = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))

    inputs.set_output("outdir", "results\nadmin=true")

    written = path.read_text()
    assert not written.startswith("outdir=")
    marker = written.split("<<", 1)[1].splitlines()[0]
    assert written == f"outdir<<{marker}\nresults\nadmin=true\n{marker}\n"


def test_set_output_does_nothing_outside_a_workflow(monkeypatch):
    """
    No GITHUB_OUTPUT means no file to write to, which is how the
    container runs by hand.

    There is no assert: with no destination there is nothing to look
    at afterwards. What this catches is the call raising, which it
    does without the guard, and pytest fails on that by itself.
    """
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    inputs.set_output("runner", "pytest")
