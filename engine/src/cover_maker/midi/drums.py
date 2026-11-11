"""Drum stem to General MIDI percussion: kick, snare and closed hi-hat.

Classic signal processing only (no model). The power spectrum is summed in one
frequency band per drum. A candidate hit is a sharp rise (in dB) of any band;
at each candidate, the power gained by every band is compared with that band's
typical hit. A drum sounds when its band gained a good share of its typical hit
and, because the attack of one drum leaks into the other bands (a kick's beater
click reaches the snare band), at least a part of what the strongest band
gained. Toms and cymbals other than the hi-hat are not told apart.
"""

# librosa ships without type information.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import librosa
import numpy as np
from numpy.typing import NDArray

from .notes import Note

KICK = 36  # Bass Drum 1
SNARE = 38  # Acoustic Snare
HIHAT = 42  # Closed Hi-Hat

# (GM note, low Hz, high Hz)
BANDS: tuple[tuple[int, float, float], ...] = (
    (KICK, 30.0, 150.0),
    (SNARE, 150.0, 4_000.0),
    (HIHAT, 6_000.0, 11_000.0),
)
N_FFT = 1024  # ~46 ms windows: short enough to time hits, long enough for the kick band
HOP = 256
RISE_DB = 9.0  # minimum jump of a band's level over ~23 ms for a candidate hit
MIN_SHARE = 0.1  # of the band's typical hit (-10 dB)
MIN_RELATIVE = 0.4  # of the strongest band's share at the same moment
MIN_GAP = 0.05  # seconds between two candidate hits
NOTE_LENGTH = 0.06  # seconds; percussion notes have no real length
_SPAN = 3  # frames before and after a candidate that are compared


def _gain(power: NDArray[np.float64], frame: int) -> float:
    """Power a band gained at ``frame``: the peak just after minus the floor just before."""
    before = power[max(0, frame - _SPAN) : frame]
    after = power[frame : frame + _SPAN]
    if before.size == 0 or after.size == 0:
        return 0.0
    return max(0.0, float(after.max()) - float(before.min()))


def transcribe(y: NDArray[np.float32], sr: int) -> list[Note]:
    """Drum hits of a mono signal, as short notes."""
    if y.size < N_FFT or not np.any(np.abs(y) > 1e-6):
        return []
    spectrum = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    powers = [
        np.asarray(spectrum[(freqs >= low) & (freqs < high)].sum(axis=0), dtype=np.float64)
        for _, low, high in BANDS
    ]
    candidates = _candidates(powers, max(1, round(MIN_GAP * sr / HOP)))
    if not candidates:
        return []
    gains = np.array([[_gain(power, f) for power in powers] for f in candidates])
    typical = np.percentile(gains, 90, axis=0)
    shares = gains / np.maximum(typical, 1e-12)
    notes: list[Note] = []
    for row, frame in enumerate(candidates):
        strongest = float(shares[row].max())
        start = float(librosa.frames_to_time(frame, sr=sr, hop_length=HOP))
        for column, (pitch, _, _) in enumerate(BANDS):
            share = float(shares[row, column])
            if share < MIN_SHARE or share < MIN_RELATIVE * strongest:
                continue
            velocity = int(np.clip(127 + 10.0 * np.log10(min(share, 1.0)) * 3.0, 20, 127))
            notes.append(Note(start, start + NOTE_LENGTH, pitch, velocity))
    return sorted(notes, key=lambda n: (n.start, n.pitch))


def _candidates(powers: list[NDArray[np.float64]], gap: int) -> list[int]:
    """Frames where some band's level rises sharply, at least ``gap`` frames apart."""
    rises: list[NDArray[np.float64]] = []
    for power in powers:
        level = 10.0 * np.log10(power + 1e-12)
        previous = np.concatenate([np.full(2, level[0]), level[:-2]])
        rises.append(level - previous)  # over two frames: attacks span a frame boundary
    rise = np.max(rises, axis=0)
    frames: list[int] = []
    for frame in range(1, len(rise) - 1):
        if rise[frame] < RISE_DB or rise[frame] < rise[frame - 1] or rise[frame] < rise[frame + 1]:
            continue
        if frames and frame - frames[-1] < gap:
            if rise[frame] > rise[frames[-1]]:
                frames[-1] = frame
            continue
        frames.append(frame)
    return frames
