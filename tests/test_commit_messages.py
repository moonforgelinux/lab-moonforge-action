import shutil
import subprocess

import pytest

from test_sanatizers import SCRIPTS

CHECKER = "sanatizer-git-commit-messages"


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def repo_with_commit(path, message):
    """A repository with no remote, carrying one commit."""
    git("init", "-qb", "main", cwd=path)
    git("config", "user.email", "test@example.com", cwd=path)
    git("config", "user.name", "Test", cwd=path)
    (path / "a-file").write_text("contents\n")
    git("add", "a-file", cwd=path)
    git("commit", "-qm", message, cwd=path)
    shutil.copytree(SCRIPTS, path / ".github" / "scripts")
    return path / ".github" / "scripts" / CHECKER


@pytest.mark.parametrize("message, accepted", [
    ("action: Do a thing\n\nChange-type: patch", True),
    ("action: Do a thing\n\nMaintenance-type: chore", True),
    ("no scope in this subject\n\nChange-type: patch", False),
    ("action: Do a thing", False),
])
def test_the_checker_judges_a_single_commit(tmp_path, message, accepted):
    """A lone commit is the case a missing trailing newline hides."""
    checker = repo_with_commit(tmp_path, message)
    done = subprocess.run([str(checker)], capture_output=True, text=True)
    assert (done.returncode == 0) is accepted, done.stdout + done.stderr
