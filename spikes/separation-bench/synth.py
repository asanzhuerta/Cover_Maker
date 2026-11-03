"""Deterministic synthetic multitrack (CC0) with known stems for benchmarking.

Produces vocals, guitar, drums, bass, piano and other at 44.1 kHz stereo, plus
their sum as the mix. It is not meant to sound like a real record; it gives the
models realistic spectral content per stem and an exact ground truth for SDR.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44_100
BPM = 112
STEMS = ("vocals", "guitar", "drums", "bass", "piano", "other")
# I - V - vi - IV in A minor-ish territory (root MIDI notes).
PROGRESSION = (57, 52, 54, 50)


def _midi_hz(note: float) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def _env(n: int, attack: float, release: float) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    r = np.exp(-t / max(release, 1e-4))
    return a * r


def _pan(mono: np.ndarray, pan: float) -> np.ndarray:
    left = np.cos((pan + 1) * np.pi / 4)
    right = np.sin((pan + 1) * np.pi / 4)
    return np.stack([mono * left, mono * right], axis=1)


def generate(seconds: float, seed: int = 7) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    beat = 60 / BPM
    bar = 4 * beat
    out = {name: np.zeros(n) for name in STEMS}
    t_all = np.arange(n) / SR

    for bar_index in range(int(seconds / bar) + 1):
        start = int(bar_index * bar * SR)
        if start >= n:
            break
        root = PROGRESSION[bar_index % len(PROGRESSION)]
        length = min(int(bar * SR), n - start)
        t = np.arange(length) / SR
        seg = slice(start, start + length)

        # Bass: plucked saw on root, eighth notes.
        for k in range(8):
            s = int(k * beat / 2 * SR)
            if s >= length:
                break
            m = min(int(beat / 2 * SR), length - s)
            tt = np.arange(m) / SR
            f = _midi_hz(root - 12)
            saw = 2 * ((f * tt) % 1) - 1
            out["bass"][start + s : start + s + m] += 0.35 * np.tanh(2 * saw) * _env(m, 0.005, 0.25)

        # Guitar: distorted power chord, strummed on beats.
        for k in range(4):
            s = int(k * beat * SR)
            m = min(int(beat * SR), length - s)
            if m <= 0:
                break
            tt = np.arange(m) / SR
            chord = sum(np.sin(2 * np.pi * _midi_hz(root + iv) * tt) for iv in (0, 7, 12))
            out["guitar"][start + s : start + s + m] += 0.22 * np.tanh(4 * chord) * _env(m, 0.01, 0.6)

        # Piano: arpeggio of the triad, decaying harmonics.
        for k in range(8):
            s = int(k * beat / 2 * SR)
            m = min(int(beat * 1.5 * SR), length - s)
            if m <= 0:
                break
            tt = np.arange(m) / SR
            note = root + 12 + (0, 3, 7, 12)[k % 4]
            f = _midi_hz(note)
            tone = sum(np.sin(2 * np.pi * f * h * tt) / h**1.5 for h in range(1, 6))
            out["piano"][start + s : start + s + m] += 0.12 * tone * _env(m, 0.002, 0.5)

        # Other: slow pad (detuned saws), whole bar.
        f = _midi_hz(root + 19)
        pad = sum(2 * (((f * d) * t) % 1) - 1 for d in (0.995, 1.0, 1.005))
        out["other"][seg] += 0.05 * pad * np.minimum(1, t / 0.4)

        # Vocals: sung melody with vibrato and simple formants.
        for k in range(4):
            s = int(k * beat * SR)
            m = min(int(beat * 0.9 * SR), length - s)
            if m <= 0:
                break
            tt = np.arange(m) / SR
            note = root + 12 + (0, 2, 3, 5)[(k + bar_index) % 4]
            f0 = _midi_hz(note) * (1 + 0.01 * np.sin(2 * np.pi * 5.5 * tt))
            phase = 2 * np.pi * np.cumsum(f0) / SR
            voiced = sum(np.sin(h * phase) * np.exp(-((h * f0 - 700) ** 2) / 2e5) for h in range(1, 20))
            breath = 0.02 * rng.standard_normal(m)
            out["vocals"][start + s : start + s + m] += 0.25 * (voiced + breath) * _env(m, 0.03, 1.2)

        # Drums: kick on 1/3, snare on 2/4, hi-hat eighths.
        for k in range(8):
            s = int(k * beat / 2 * SR)
            m = min(int(0.25 * SR), length - s)
            if m <= 0:
                break
            tt = np.arange(m) / SR
            hit = np.zeros(m)
            if k % 4 == 0:
                hit += np.sin(2 * np.pi * (50 + 80 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 12)
            if k % 4 == 2:
                hit += 0.6 * rng.standard_normal(m) * np.exp(-tt * 25)
            hat = np.diff(rng.standard_normal(m + 1)) * np.exp(-tt * 80)
            hit += 0.15 * hat
            out["drums"][start + s : start + s + m] += 0.5 * hit

    pans = {"vocals": 0.0, "guitar": -0.5, "drums": 0.0, "bass": 0.0, "piano": 0.4, "other": 0.2}
    stems = {name: _pan(sig, pans[name]).astype(np.float32) for name, sig in out.items()}
    del t_all
    return stems


def write_multitrack(directory: Path, seconds: float) -> Path:
    """Write stems and mix; returns the mix path. Peak-normalises the mix to -1 dBFS."""
    directory.mkdir(parents=True, exist_ok=True)
    stems = generate(seconds)
    mix = sum(stems.values())
    gain = 10 ** (-1 / 20) / float(np.max(np.abs(mix)))
    for name, signal in stems.items():
        sf.write(directory / f"{name}.wav", signal * gain, SR, subtype="FLOAT")
    mix_path = directory / "mix.wav"
    sf.write(mix_path, mix * gain, SR, subtype="FLOAT")
    return mix_path
