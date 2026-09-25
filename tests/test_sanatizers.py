import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".github" / "scripts"
TOOLS = ("pycodestyle", "pyflakes", "radon", "shellcheck")


def env_with_venv():
    """The linters live in the venv pytest itself is running from."""
    env = dict(os.environ)
    binaries = str(Path(sys.executable).parent)
    env["PATH"] = binaries + os.pathsep + env.get("PATH", "")
    return env


def discover(function):
    script = f'. "{SCRIPTS}/common.sh"; cd_repo_root; {function}'
    done = subprocess.run(
        ["bash", "-c", script],
        capture_output=True, text=True, check=True,
    )
    return done.stdout.split()


def test_python_discovery_finds_modules_without_a_shebang():
    """Keying only on the shebang, as upstream does, finds none of ours."""
    assert "./lab_action/__init__.py" in discover("python_sources")


def test_shell_discovery_finds_the_sanatizers_themselves():
    found = discover("shell_sources")
    assert "./.github/scripts/common.sh" in found
    assert "./.github/scripts/sanatizer-radon" in found


def test_the_sanatizers_pass():
    env = env_with_venv()
    missing = [t for t in TOOLS if not shutil.which(t, path=env["PATH"])]
    if missing:
        pytest.skip("not installed: " + ", ".join(missing))

    done = subprocess.run(
        [str(SCRIPTS / "run-all-sanatizers")],
        capture_output=True, text=True, env=env,
    )
    assert done.returncode == 0, done.stdout + done.stderr
