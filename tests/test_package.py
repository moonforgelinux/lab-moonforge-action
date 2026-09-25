from importlib.metadata import version

import lab_action


def test_version_is_a_dotted_string():
    assert lab_action.__version__.count(".") == 2


def test_the_installed_version_matches_the_package():
    """pyproject reads the version from the package; keep them in step."""
    assert version("lab-moonforge-action") == lab_action.__version__
