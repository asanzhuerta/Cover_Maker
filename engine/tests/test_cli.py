from typer.testing import CliRunner

from cover_maker import __version__
from cover_maker.cli import app

runner = CliRunner()


def test_version_flag_prints_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_doctor_runs() -> None:
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
