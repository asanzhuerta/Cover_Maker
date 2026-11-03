import subprocess
import sys
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

    def run(command: list[str], on_tick: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        on_tick()
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
    monkeypatch.setattr(installer, "_run", run)

    installer.install(model, tmp_path / "models", installs, accepted=True)

    command = run.calls[0]
    assert "from audio_separator.utils.cli import main; main()" in command
    assert "--download_model_only" in command
    assert installs.is_installed(model)


def test_silent_failure_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, installs: Installs
) -> None:
    monkeypatch.setattr(installer, "separation_available", lambda: True)
    monkeypatch.setattr(installer, "_run", fake_run(None))

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


def test_progress_counts_partial_files(tmp_path: Path) -> None:
    target = tmp_path / "model.ckpt"
    assert installer.downloaded_bytes(target) == 0
    (tmp_path / "model.ckpt.1234.partial").write_bytes(b"x" * 1024 * 512)
    (tmp_path / "other.ckpt").write_bytes(b"x" * 4096)
    assert installer.downloaded_bytes(target) == 1024 * 512
    assert installer.download_fraction(1024 * 512, 1) == pytest.approx(0.5)
    assert installer.download_fraction(10 * 1024 * 1024, 1) == 0.99
    assert installer.download_fraction(100, 0) is None


def test_download_reports_progress(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, installs: Installs
) -> None:
    model = Catalog.load().get("htdemucs")
    target = tmp_path / "models" / model.filename

    def run(command: list[str], on_tick: Any) -> subprocess.CompletedProcess[str]:
        target.parent.mkdir(parents=True, exist_ok=True)
        (target.parent / f"{target.name}.1.partial").write_bytes(b"x" * 1024 * 1024)
        on_tick()
        (target.parent / f"{target.name}.1.partial").rename(target)
        return subprocess.CompletedProcess(command, 0, "", "")

    seen: list[float] = []
    monkeypatch.setattr(installer, "separation_available", lambda: True)
    monkeypatch.setattr(installer, "_run", run)
    installer.install(model, target.parent, installs, accepted=True, progress=seen.append)
    assert seen and 0 < seen[0] < 1


def test_run_ticks_while_the_process_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "POLL_S", 0.05)
    ticks: list[int] = []
    completed = installer._run(  # pyright: ignore[reportPrivateUsage]
        [sys.executable, "-c", "import time; time.sleep(0.3); print('ok')"],
        lambda: ticks.append(1),
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == "ok"
    assert ticks
