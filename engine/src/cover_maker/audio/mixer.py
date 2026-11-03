"""Rendering of "track without X" mixes.

With ``residual=keep`` the result is exactly the mix minus the removed stems:
nothing the models missed is lost, at the price of some bleed of the removed
instruments. With ``residual=drop`` the result is the sum of the remaining
stems only, which is cleaner but loses whatever no stem captured.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from ..domain import ResidualMode, Stem
from .io import Audio

PEAK_LIMIT = 10 ** (-0.1 / 20)  # -0.1 dBFS


@dataclass(frozen=True)
class RenderResult:
    audio: Audio
    peak_dbfs: float
    gain_db: float


def _fit(signal: Audio, frames: int) -> Audio:
    """Pad with silence or trim so every stem has the mix's length."""
    if len(signal) == frames:
        return signal
    if len(signal) > frames:
        return signal[:frames]
    padding = np.zeros((frames - len(signal), signal.shape[1]), dtype=np.float32)
    return np.concatenate([signal, padding])


def without(
    mix: Audio,
    stems: Mapping[Stem, Audio],
    removed: set[Stem],
    residual: ResidualMode,
) -> Audio:
    """Return the song without the ``removed`` stems (float32, unclipped)."""
    frames = len(mix)
    if residual is ResidualMode.KEEP:
        missing = removed - stems.keys()
        if missing:
            raise ValueError(f"missing stems for removal: {sorted(missing)}")
        result = mix.astype(np.float32, copy=True)
        for stem in removed:
            result -= _fit(stems[stem], frames)
        return result
    result = np.zeros_like(mix, dtype=np.float32)
    for stem, signal in stems.items():
        if stem not in removed:
            result += _fit(signal, frames)
    return result


def mix_gains(
    mix: Audio,
    stems: Mapping[Stem, Audio],
    gains: Mapping[Stem, float],
    residual: ResidualMode,
) -> Audio:
    """Return a custom mix: every stem scaled by its linear gain (default 1).

    The residual (the mix minus every stem) is added back at unity gain with
    ``residual=keep`` and left out with ``drop``. All gains at 1 with ``keep``
    give the original mix; gain 0 on a stem matches :func:`without`. The
    preview mixer in the desktop app uses the same formula.
    """
    frames = len(mix)
    fitted = {stem: _fit(signal, frames) for stem, signal in stems.items()}
    if residual is ResidualMode.KEEP:
        result = mix.astype(np.float32, copy=True)
        for stem, signal in fitted.items():
            result += (gains.get(stem, 1.0) - 1.0) * signal
        return result
    result = np.zeros_like(mix, dtype=np.float32)
    for stem, signal in fitted.items():
        result += gains.get(stem, 1.0) * signal
    return result


def protect_peaks(audio: Audio) -> RenderResult:
    """Reduce gain only when the signal would clip; never clip silently."""
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    gain = 1.0 if peak <= PEAK_LIMIT or peak == 0 else PEAK_LIMIT / peak
    peak_dbfs = 20 * np.log10(peak) if peak > 0 else float("-inf")
    return RenderResult(
        (audio * gain).astype(np.float32), float(peak_dbfs), float(20 * np.log10(gain))
    )
