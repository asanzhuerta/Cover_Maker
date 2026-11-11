"""Practice transforms for exports: tempo, pitch and the click stem (ADR-012).

The preview mixer plays every source with ``playbackRate = tempo`` (a resample,
which also moves the pitch) and corrects the pitch on the master bus with one
Signalsmith Stretch node. Exports do the same two steps in the same order, with
the same library (``python-stretch``, MIT), so what the user hears is what they
get:

1. resample by the tempo factor (soxr, through librosa);
2. transpose by ``semitones + cents/100 - 12*log2(tempo)`` with Signalsmith
   Stretch, using the same tonality limit as the web build (8 kHz).

The click stem is synthesised from the stored beat grid with the same recipe as
the UI (``desktop/src/lib/practice.ts``): short decaying sine blips, higher and
louder on downbeats.
"""

# librosa and the Signalsmith binding have partial type information.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import math
from dataclasses import dataclass

import librosa
import numpy as np
import python_stretch as ps  # pyright: ignore[reportMissingTypeStubs]
from numpy.typing import NDArray

from .io import SAMPLE_RATE, Audio

MIN_TEMPO = 0.5
MAX_TEMPO = 1.5
MAX_SEMITONES = 12.0
MAX_CENTS = 50.0
# Same default as the Web Audio release of Signalsmith Stretch.
TONALITY_HZ = 8_000.0

CLICK_HZ = 1_000.0
ACCENT_HZ = 1_500.0
CLICK_SECONDS = 0.03
CLICK_DECAY = 150.0  # 1/s
CLICK_LEVEL = 0.5
ACCENT_LEVEL = 0.8


@dataclass(frozen=True)
class Practice:
    """Tempo factor (1 = original) and pitch shift of a practice render."""

    tempo: float = 1.0
    semitones: float = 0.0
    cents: float = 0.0

    def __post_init__(self) -> None:
        if not MIN_TEMPO <= self.tempo <= MAX_TEMPO:
            raise ValueError(f"tempo must be between {MIN_TEMPO} and {MAX_TEMPO}")
        if abs(self.semitones) > MAX_SEMITONES:
            raise ValueError(f"semitones must be between -{MAX_SEMITONES:g} and {MAX_SEMITONES:g}")
        if abs(self.cents) > MAX_CENTS:
            raise ValueError(f"cents must be between -{MAX_CENTS:g} and {MAX_CENTS:g}")

    @property
    def identity(self) -> bool:
        return self.tempo == 1.0 and self.semitones == 0.0 and self.cents == 0.0

    @property
    def correction(self) -> float:
        """Transposition the stretch applies after the resample, in semitones."""
        return self.semitones + self.cents / 100.0 - 12.0 * math.log2(self.tempo)

    def suffix(self) -> str:
        """File-name tag, e.g. ``-1 st, 80 %``."""
        parts: list[str] = []
        shift = self.semitones + self.cents / 100.0
        if shift:
            parts.append(f"{shift:+g} st")
        if self.tempo != 1.0:
            parts.append(f"{round(self.tempo * 100):d} %")
        return ", ".join(parts)


def resample_for_tempo(audio: Audio, tempo: float, rate: int = SAMPLE_RATE) -> Audio:
    """Play ``audio`` ``tempo`` times faster, like ``AudioBufferSourceNode.playbackRate``."""
    if tempo == 1.0:
        return audio
    # Pretend the file was recorded at rate*tempo and bring it back to the canonical rate.
    out = librosa.resample(
        np.ascontiguousarray(audio.T), orig_sr=rate * tempo, target_sr=rate, axis=-1
    )
    return np.ascontiguousarray(np.asarray(out, dtype=np.float32).T)


def transpose(audio: Audio, semitones: float, rate: int = SAMPLE_RATE) -> Audio:
    """Shift the pitch without changing the length (Signalsmith Stretch, latency compensated)."""
    if abs(semitones) < 1e-6 or len(audio) == 0:
        return audio
    stretch = ps.Signalsmith.Stretch()
    stretch.preset(audio.shape[1], float(rate))
    stretch.setTransposeSemitones(float(semitones), TONALITY_HZ / rate)
    shifted = stretch.process(np.ascontiguousarray(audio.T, dtype=np.float32))
    out: NDArray[np.float32] = np.asarray(shifted, dtype=np.float32).T
    return np.ascontiguousarray(out[: len(audio)])


def apply(audio: Audio, practice: Practice, rate: int = SAMPLE_RATE) -> Audio:
    """Tempo then pitch, in the same order as the preview."""
    if practice.identity:
        return audio
    return transpose(resample_for_tempo(audio, practice.tempo, rate), practice.correction, rate)


def render_click(
    beats: list[float], downbeats: list[float], frames: int, rate: int = SAMPLE_RATE
) -> NDArray[np.float32]:
    """Mono click track on the beat grid (seconds), accented on downbeats."""
    out = np.zeros(frames, dtype=np.float32)
    length = int(CLICK_SECONDS * rate)
    t = np.arange(length, dtype=np.float64) / rate
    envelope = np.exp(-t * CLICK_DECAY)
    plain = (np.sin(2 * np.pi * CLICK_HZ * t) * envelope * CLICK_LEVEL).astype(np.float32)
    accent = (np.sin(2 * np.pi * ACCENT_HZ * t) * envelope * ACCENT_LEVEL).astype(np.float32)
    accented = {round(d, 3) for d in downbeats}
    for beat in beats:
        start = round(beat * rate)
        if start < 0 or start >= frames:
            continue
        blip = accent if round(beat, 3) in accented else plain
        end = min(frames, start + length)
        out[start:end] += blip[: end - start]
    return out


def click_stereo(beats: list[float], downbeats: list[float], frames: int) -> Audio:
    mono = render_click(beats, downbeats, frames)
    return np.ascontiguousarray(np.stack([mono, mono], axis=1))
