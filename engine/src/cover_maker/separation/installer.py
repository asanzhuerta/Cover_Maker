"""Download a catalogue model into the models folder after licence acceptance.

The download itself is delegated to audio-separator (it knows each model's
original source and companion files) and runs in a subprocess so the engine
never imports PyTorch.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from ..store.assets import sha256_file
from .catalog import Installs, ModelSpec

# Fraction of the model downloaded so far, in [0, 1).
Progress = Callable[[float], None]
POLL_S = 0.5


class InstallError(RuntimeError):
    """A model could not be installed; ``code`` lets the UI show its own text."""

    def __init__(self, message: str, code: str = "install_failed") -> None:
        super().__init__(message)
        self.code = code


def separation_available() -> bool:
    """True when the optional separation dependencies are installed.

    The installed app adds them in the background while the engine runs, so
    the import system's directory caches are refreshed first.
    """
    from importlib import invalidate_caches
    from importlib.util import find_spec

    invalidate_caches()
    return find_spec("audio_separator") is not None and find_spec("torch") is not None


def downloaded_bytes(target: Path) -> int:
    """Bytes written so far: audio-separator streams into ``<name>.<pid>.partial``."""
    if not target.parent.exists():
        return 0
    return sum(
        path.stat().st_size for path in target.parent.glob(f"{target.name}*") if path.is_file()
    )


def download_fraction(written: int, size_mb: int) -> float | None:
    """Progress against the catalogue size; never 1 before the download ends."""
    if size_mb <= 0:
        return None
    return min(0.99, written / (size_mb * 1024 * 1024))


def _run(command: list[str], on_tick: Callable[[], None]) -> subprocess.CompletedProcess[str]:
    """Run the download, calling ``on_tick`` while it is in progress."""
    process = subprocess.Popen(  # nosemgrep: python.lang.compatibility.python36.python36-compatibility-Popen1, python.lang.compatibility.python36.python36-compatibility-Popen2
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )  # fmt: skip
    while True:
        try:
            stdout, stderr = process.communicate(timeout=POLL_S)
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            on_tick()


def install(
    model: ModelSpec,
    models_dir: Path,
    installs: Installs,
    *,
    accepted: bool,
    progress: Progress | None = None,
) -> Path:
    if not accepted:
        raise InstallError("The licence notice must be accepted before downloading the model.")
    if not separation_available():
        raise InstallError(
            "Separation support is not installed yet. The app installs it in the "
            "background after the first start; in a development checkout run: "
            "uv sync --extra separation --extra cu128 (or --extra cpu; --extra mps on macOS)",
            code="separation_missing",
        )
    models_dir.mkdir(parents=True, exist_ok=True)
    target = models_dir / model.filename
    if not target.exists():
        # audio_separator.utils.cli has no __main__ guard, so `python -m` would do
        # nothing; call its entry point explicitly.
        command = [
            sys.executable, "-c", "from audio_separator.utils.cli import main; main()",
            "--download_model_only", "--model_filename", model.filename,
            "--model_file_dir", str(models_dir), "--log_level", "warning",
        ]  # fmt: skip

        def tick() -> None:
            fraction = download_fraction(downloaded_bytes(target), model.size_mb)
            if progress is not None and fraction is not None:
                progress(fraction)

        completed = _run(command, tick)
        if completed.returncode != 0 or not target.exists():
            output = (completed.stderr or completed.stdout).strip()[-500:]
            detail = output or f"exit code {completed.returncode}, no file was downloaded"
            raise InstallError(f"download of {model.filename} failed: {detail}")

    digest = sha256_file(target) if target.stat().st_size > 1024 else None
    if model.sha256 and digest and digest != model.sha256:
        target.unlink(missing_ok=True)
        raise InstallError(
            f"{model.filename} does not match the catalogue checksum; the file was removed."
        )
    installs.record(model, digest)
    return target
