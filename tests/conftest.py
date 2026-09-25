import pytest


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A checkout for the action to work on."""
    root = tmp_path.resolve()
    monkeypatch.setenv("GITHUB_WORKSPACE", str(root))
    return root


@pytest.fixture
def given(monkeypatch):
    """Set action inputs: given(entrypoint="tests", runner="pytest")."""
    def set_inputs(**values):
        for name, value in values.items():
            monkeypatch.setenv("INPUT_" + name.upper(), str(value))
    return set_inputs
