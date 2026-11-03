"""Waveform peaks for drawing stems in the preview mixer."""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np

from . import io


def compute_peaks(path: Path, points: int) -> list[list[float]]:
    """Return ``points`` [min, max] pairs of the mono mix-down, rounded to 4 decimals."""
    audio = io.read(path)
    mono = audio.mean(axis=1) if audio.size else np.zeros(0, dtype=np.float32)
    if mono.size == 0:
        return [[0.0, 0.0]] * points
    edges = np.linspace(0, mono.size, points + 1, dtype=np.int64)
    peaks: list[list[float]] = []
    for start, end in itertools.pairwise(edges):
        chunk = mono[start : max(end, start + 1)]
        peaks.append([round(float(chunk.min()), 4), round(float(chunk.max()), 4)])
    return peaks
