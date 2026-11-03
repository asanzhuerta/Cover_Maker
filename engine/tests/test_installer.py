import subprocess
from pathlib import Path
from typing import Any

import pytest

from cover_maker.separation import installer
from cover_maker.separation.catalog import Catalog, Installs
from cover_maker.store.db import connect


@pytest.fixture
def installs(tmp_path: Path) -> Installs:
    return Installs(connect(tmp_path / "db.sqlite3"))


def fake_run(created: Path | None) -> Any:
    calls: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if created is not None:
            created.write_text("weights")
        return subprocess.CompletedProcess(command, 0, "", "")

    run.calls = calls  # type: ignore[attr-defined]
    return run


def test_download_calls_the_cli_entry_point(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, installs: Installs
) -> None:
    model = Catalog.load().get("htdemucs")
    run = fake_run(tmp_path / "models" / model.filename)
    monkeypatch.setattr(installer, "separation_available", lambda: True)
    monkeypatch.setattr(installer.subprocess, "run", run)

    installer.install(model, tmp_path / "models", installs, accepted=True)

    command = run.calls[0]
    assert "from audio_separator.utils.cli import main; main()" in command
    assert "--download_model_only" in command
    assert installs.is_installed(model)


def test_silent_failure_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, installs: Installs
) -> None:
    monkeypatch.setattr(installer, "separation_available", lambda: True)
    monkeypatch.setattr(installer.subprocess, "run", fake_run(None))

    with pytest.raises(installer.InstallError, match="no file was downloaded"):
        installer.install(Catalog.load().get("htdemucs"), tmp_path / "m", installs, accepted=True)


def test_licence_must_be_accepted(tmp_path: Path, installs: Installs) -> None:
    with pytest.raises(installer.InstallError, match="licence"):
        installer.install(Catalog.load().get("htdemucs"), tmp_path, installs, accepted=False)


def test_missing_separation_runtime_has_a_code(
    tmp_path: Path, installs: Installs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(installer, "separation_available", lambda: False)
    with pytest.raises(installer.InstallError) as raised:
        installer.install(Catalog.load().get("htdemucs"), tmp_path, installs, accepted=True)
    assert raised.value.code == "separation_missing"
