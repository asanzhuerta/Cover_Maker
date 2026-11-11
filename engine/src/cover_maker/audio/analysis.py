"""Musical analysis of a mix: tuning, key, tempo, beats and downbeats.

Everything runs on librosa (ISC) with classic signal processing, so no model
weights are needed:

- **Tuning**: ``librosa.estimate_tuning`` gives the offset of the pitch content
  from the A440 equal-tempered grid, in fractions of a semitone.
- **Key**: the mean constant-Q chroma of the harmonic part (HPSS removes drums,
  whose noise smears every pitch class), corrected for that tuning, is correlated
  with the 24 rotations of the Krumhansl-Kessler and Temperley key profiles; the
  scores of both profile sets are averaged.
- **Tempo and beats**: ``librosa.beat.beat_track`` (dynamic programming over the
  onset envelope).
- **Downbeats**: librosa has no downbeat tracker. Assuming 4/4, the bar phase is
  the beat offset (0-3) whose beats carry the most low-frequency onset energy.
"""

# librosa ships without type information.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import librosa
import numpy as np
from numpy.typing import NDArray

# Bump when the algorithm changes so cached results are recomputed.
ANALYSIS_VERSION = 1
ANALYSIS_RATE = 22_050
BEATS_PER_BAR = 4

PITCH_CLASSES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")

# Krumhansl & Kessler (1982) probe-tone ratings.
_KK_MAJOR = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
_KK_MINOR = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)
# Temperley (1999) revised profiles.
_TEMPERLEY_MAJOR = (5.0, 2.0, 3.5, 2.0, 4.5, 4.0, 2.0, 4.5, 2.0, 3.5, 1.5, 4.0)
_TEMPERLEY_MINOR = (5.0, 2.0, 3.5, 4.5, 2.0, 4.0, 2.0, 4.5, 3.5, 2.0, 1.5, 4.0)

Signal = NDArray[np.float32]


@dataclass(frozen=True)
class KeyEstimate:
    tonic: str
    mode: str  # "major" or "minor"
    confidence: float  # best score minus the runner-up, 0..2


@dataclass(frozen=True)
class Analysis:
    tuning_cents: float
    key: str
    mode: str
    key_confidence: float
    bpm: float
    beats: list[float] = field(default_factory=list[float])
    downbeats: list[float] = field(default_factory=list[float])
    version: int = ANALYSIS_VERSION

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Analysis:
        return cls(**data)


def to_mono(audio: NDArray[np.float32], rate: int) -> Signal:
    """Down-mix (frames x channels) audio and resample to the analysis rate."""
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    mono = np.ascontiguousarray(mono, dtype=np.float32)
    if rate != ANALYSIS_RATE:
        mono = librosa.resample(mono, orig_sr=rate, target_sr=ANALYSIS_RATE)
    return np.asarray(mono, dtype=np.float32)


def estimate_tuning_cents(y: Signal, sr: int = ANALYSIS_RATE) -> float:
    """Offset of the recording from A440 in cents, in [-50, 50)."""
    fraction = float(librosa.estimate_tuning(y=y, sr=sr, bins_per_octave=12))
    return round(fraction * 100.0, 1)


def _profile_scores(chroma: NDArray[np.float64]) -> NDArray[np.float64]:
    """Correlation of a 12-bin chroma vector with every key: shape (2 modes, 12 tonics)."""
    scores = np.zeros((2, 12))
    for major, minor in ((_KK_MAJOR, _KK_MINOR), (_TEMPERLEY_MAJOR, _TEMPERLEY_MINOR)):
        for mode, profile in enumerate((major, minor)):
            base = np.asarray(profile, dtype=np.float64)
            for tonic in range(12):
                scores[mode, tonic] += np.corrcoef(chroma, np.roll(base, tonic))[0, 1]
    return scores / 2.0


def estimate_key(y: Signal, sr: int = ANALYSIS_RATE, tuning_cents: float = 0.0) -> KeyEstimate:
    harmonic = librosa.effects.harmonic(y, margin=2.0)
    chroma = librosa.feature.chroma_cqt(y=harmonic, sr=sr, tuning=tuning_cents / 100.0)
    profile = np.asarray(chroma, dtype=np.float64).mean(axis=1)
    if not np.any(profile > 0) or np.allclose(profile, profile[0]):
        return KeyEstimate(tonic="C", mode="major", confidence=0.0)
    scores = _profile_scores(profile)
    order = np.argsort(scores, axis=None)[::-1]
    mode, tonic = np.unravel_index(int(order[0]), scores.shape)
    runner_up = float(scores.flat[int(order[1])])
    return KeyEstimate(
        tonic=PITCH_CLASSES[int(tonic)],
        mode="major" if int(mode) == 0 else "minor",
        confidence=round(float(scores[mode, tonic]) - runner_up, 3),
    )


def track_beats(y: Signal, sr: int = ANALYSIS_RATE) -> tuple[float, list[float], list[float]]:
    """Tempo in BPM, beat times and downbeat times (seconds)."""
    hop = 512
    envelope = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    tempo, frames = librosa.beat.beat_track(onset_envelope=envelope, sr=sr, hop_length=hop)
    beat_frames = np.asarray(frames, dtype=np.int64)
    beats = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)
    beat_times = [round(float(t), 4) for t in np.asarray(beats)]
    bpm = float(np.atleast_1d(np.asarray(tempo, dtype=np.float64))[0])
    if len(beat_times) >= 2:
        # The median inter-beat interval follows the grid more closely than the global estimate.
        bpm = 60.0 / float(np.median(np.diff(beat_times)))
    downbeats = _downbeats(y, sr, beat_frames, beat_times, hop)
    return round(bpm, 2), beat_times, downbeats


def _downbeats(
    y: Signal, sr: int, beat_frames: NDArray[np.int64], beat_times: list[float], hop: int
) -> list[float]:
    if len(beat_times) < BEATS_PER_BAR:
        return beat_times[:1]
    # Bass and kick accents mark the start of a bar more often than any other beat.
    low = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop, fmax=250.0, n_mels=32)
    low = np.asarray(low, dtype=np.float64)
    frames = np.clip(beat_frames, 0, len(low) - 1)
    strengths = low[frames]
    phase_scores = [float(strengths[p::BEATS_PER_BAR].mean()) for p in range(BEATS_PER_BAR)]
    phase = int(np.argmax(phase_scores))
    return beat_times[phase::BEATS_PER_BAR]


def analyse(audio: NDArray[np.float32], rate: int) -> Analysis:
    """Analyse a (frames x channels) or mono signal."""
    y = to_mono(audio, rate)
    if y.size < ANALYSIS_RATE // 2 or not np.any(np.abs(y) > 1e-6):
        return Analysis(tuning_cents=0.0, key="C", mode="major", key_confidence=0.0, bpm=0.0)
    tuning = estimate_tuning_cents(y)
    key = estimate_key(y, tuning_cents=tuning)
    bpm, beats, downbeats = track_beats(y)
    return Analysis(
        tuning_cents=tuning,
        key=key.tonic,
        mode=key.mode,
        key_confidence=key.confidence,
        bpm=bpm,
        beats=beats,
        downbeats=downbeats,
    )
