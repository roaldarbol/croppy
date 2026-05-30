"""CLI smoke tests — verify --help / --version work without booting Qt."""

from __future__ import annotations

import subprocess
import sys

from typer.testing import CliRunner

from croppy import __version__
from croppy.cli import cli


def test_help_via_subprocess() -> None:
    """`python -m croppy --help` exits 0 and mentions the program name."""
    result = subprocess.run(
        [sys.executable, "-m", "croppy", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "croppy" in result.stdout.lower()


def test_version_flag() -> None:
    """--version prints the package version and exits 0."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
