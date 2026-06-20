"""Launch-time dependency installation."""
from unittest.mock import patch

from src.app.deps_install import (
    has_install_deps_flag,
    is_frozen,
    project_root,
    requirements_path,
    should_skip_bootstrap,
)


def test_has_install_deps_flag():
    assert has_install_deps_flag(["--install-deps"])
    assert has_install_deps_flag(["-d"])
    assert not has_install_deps_flag(["--autostart"])


def test_should_skip_bootstrap_on_help():
    assert should_skip_bootstrap(["--help"])
    assert should_skip_bootstrap(["-h"])


def test_requirements_path_points_to_repo_root():
    path = requirements_path()
    assert path.endswith("requirements.txt")
    assert project_root() in path


@patch("sys.frozen", True, create=True)
def test_is_frozen():
    assert is_frozen() is True
