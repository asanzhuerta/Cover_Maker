"""Download a catalogue model into the models folder after licence acceptance.

The download itself is delegated to audio-separator (it knows each model's
original source and companion files) and runs in a subprocess so the engine
never imports PyTorch.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ..store.assets import sha256_file
from .catalog import Installs, ModelSpec


class InstallError(RuntimeError):
    pass


def separation_available() -> bool:
    """True when the optional separation dependencies are installed."""
    from importlib.util import find_spec

    return find_spec("audio_separator") is not None and find_spec("torch") is not None


def install(model: ModelSpec, models_dir: Path, installs: Installs, *, accepted: bool) -> Path:
    if not accepted:
        raise InstallError("The licence notice must be accepted before downloading the model.")
    if not separation_available():
        raise InstallError(
            "Separation support is not installed. In a development checkout run: "
            "uv sync --extra separation"
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
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
        )
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
