"""Data folder: installed app vs source checkout."""

from pathlib import Path

import pytest

from cover_maker import paths


def test_source_checkout_uses_the_dev_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(paths.HOME_ENV, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\x\AppData\Local")

    assert paths.running_from_source()
    assert paths.default_home() == Path(r"C:\Users\x\AppData\Local") / "Cover_Maker.dev"


def test_installed_package_uses_the_install_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(paths.HOME_ENV, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\x\AppData\Local")
    monkeypatch.setattr(paths, "running_from_source", lambda: False)

    assert paths.default_home() == Path(r"C:\Users\x\AppData\Local") / "Cover_Maker"


def test_override_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(paths.HOME_ENV, str(tmp_path))

    assert paths.default_home() == tmp_path
