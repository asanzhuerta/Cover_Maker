"""Data folder: installed app vs source checkout, per platform."""

from pathlib import Path

import pytest

from cover_maker import paths


def test_source_checkout_uses_the_dev_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(paths.HOME_ENV, raising=False)
    monkeypatch.setattr(paths, "data_root", lambda: Path("base"))

    assert paths.running_from_source()
    assert paths.default_home() == Path("base") / "Cover_Maker.dev"


def test_installed_package_uses_the_install_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(paths.HOME_ENV, raising=False)
    monkeypatch.setattr(paths, "data_root", lambda: Path("base"))
    monkeypatch.setattr(paths, "running_from_source", lambda: False)

    assert paths.default_home() == Path("base") / "Cover_Maker"


def test_override_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(paths.HOME_ENV, str(tmp_path))

    assert paths.default_home() == tmp_path


def test_windows_uses_local_app_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\x\AppData\Local")

    assert paths.data_root("win32") == Path(r"C:\Users\x\AppData\Local")


def test_macos_uses_application_support() -> None:
    assert paths.data_root("darwin") == Path.home() / "Library" / "Application Support"


def test_other_systems_follow_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert paths.data_root("linux") == tmp_path

    monkeypatch.delenv("XDG_DATA_HOME")
    assert paths.data_root("linux") == Path.home() / ".local" / "share"
