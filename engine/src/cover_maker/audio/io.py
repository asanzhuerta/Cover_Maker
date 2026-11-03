"""Audio decoding and encoding.

Every input is first decoded to a canonical WAV (44.1 kHz, stereo, float32).
Separation models receive that file, so their stems line up sample by sample
with the mix used for the residual in the mixer.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf  # pyright: ignore[reportMissingTypeStubs]
from numpy.typing import NDArray

SAMPLE_RATE = 44_100
CHANNELS = 2
Audio = NDArray[np.float32]

_FFMPEG_ENV_NOTE = "Install ffmpeg and make sure it is on PATH."


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def _canonical(raw: object) -> Audio:
    data = np.asarray(raw, dtype=np.float32)
    if data.ndim == 1:
        data = data[:, None]
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    return np.ascontiguousarray(data[:, :CHANNELS], dtype=np.float32)


def decode_to_canonical(source: Path, target: Path) -> Path:
    """Decode any supported input to a canonical float32 WAV at 44.1 kHz stereo."""
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        info = sf.info(str(source))
        native = info.samplerate == SAMPLE_RATE
    except RuntimeError:
        native = False
    if native:
        data, _ = sf.read(str(source), dtype="float32", always_2d=True)
        sf.write(str(target), _canonical(data), SAMPLE_RATE, subtype="FLOAT")
        return target

    ffmpeg = ffmpeg_path()
    if ffmpeg is None:
        raise RuntimeError(f"Cannot decode {source.name} without ffmpeg. {_FFMPEG_ENV_NOTE}")
    command = [
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
        "-vn", "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE), "-c:a", "pcm_f32le", str(target),
    ]  # fmt: skip
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg could not decode {source.name}: {completed.stderr.strip()}")
    return target


def write_float(audio: Audio, target: Path) -> Path:
    """Write an intermediate 32-bit float WAV (lossless, used inside the library)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(target), audio, SAMPLE_RATE, subtype="FLOAT")
    return target


def read(path: Path) -> Audio:
    data, rate = sf.read(str(path), dtype="float32", always_2d=True)
    if rate != SAMPLE_RATE:
        raise ValueError(f"{path.name} is {rate} Hz; expected canonical {SAMPLE_RATE} Hz")
    return _canonical(data)


def write(audio: Audio, target: Path, fmt: str) -> Path:
    """Write audio as WAV (24-bit), FLAC (24-bit) or MP3 (320 kbps via ffmpeg)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "wav":
        sf.write(str(target), audio, SAMPLE_RATE, subtype="PCM_24")
    elif fmt == "flac":
        sf.write(str(target), audio, SAMPLE_RATE, subtype="PCM_24", format="FLAC")
    elif fmt == "mp3":
        ffmpeg = ffmpeg_path()
        if ffmpeg is None:
            raise RuntimeError(f"MP3 export needs ffmpeg. {_FFMPEG_ENV_NOTE}")
        temporary = target.with_suffix(".tmp.wav")
        sf.write(str(temporary), audio, SAMPLE_RATE, subtype="FLOAT")
        command = [ffmpeg, "-nostdin", "-loglevel", "error", "-y", "-i", str(temporary),
                   "-c:a", "libmp3lame", "-b:a", "320k", str(target)]  # fmt: skip
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        temporary.unlink(missing_ok=True)
        if completed.returncode != 0:
            raise RuntimeError(f"ffmpeg could not encode MP3: {completed.stderr.strip()}")
    else:
        raise ValueError(f"unsupported output format: {fmt}")
    return target
