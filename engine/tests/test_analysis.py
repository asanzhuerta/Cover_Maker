"""Musical analysis on synthetic signals only (clicks, sine chords, detuned tones)."""

import numpy as np
import pytest

from cover_maker.audio.analysis import (
    ANALYSIS_RATE,
    Analysis,
    analyse,
    estimate_key,
    estimate_tuning_cents,
    track_beats,
)

SR = ANALYSIS_RATE


def tone(freq: float, seconds: float, sr: int = SR, harmonics: int = 4) -> np.ndarray:
    t = np.arange(int(seconds * sr)) / sr
    wave = sum(np.sin(2 * np.pi * freq * h * t) / h for h in range(1, harmonics + 1))
    envelope = np.minimum(1.0, np.minimum(t, seconds - t) * 20)  # no clicks at the edges
    return (0.2 * wave * envelope).astype(np.float32)


def midi_hz(note: int, cents: float = 0.0) -> float:
    return 440.0 * 2 ** ((note - 69 + cents / 100) / 12)


def chord(notes: list[int], seconds: float, cents: float = 0.0) -> np.ndarray:
    return sum(tone(midi_hz(n, cents), seconds) for n in notes).astype(np.float32)  # type: ignore[return-value]


def progression(chords: list[list[int]], seconds: float = 1.5) -> np.ndarray:
    return np.concatenate([chord(c, seconds) for c in chords * 2])


def clicks(bpm: float, seconds: float, accent_every: int = 4, offset: int = 0) -> np.ndarray:
    """A click track; every ``accent_every``-th click (from ``offset``) is a louder, lower thump."""
    y = np.zeros(int(seconds * SR), dtype=np.float32)
    period = 60.0 / bpm
    burst = np.arange(int(0.03 * SR)) / SR
    decay = np.exp(-burst * 120)
    high = (np.sin(2 * np.pi * 2000 * burst) * decay * 0.5).astype(np.float32)
    low = (np.sin(2 * np.pi * 80 * burst) * decay * 1.0).astype(np.float32)
    for i, start in enumerate(np.arange(0.5, seconds - 0.1, period)):
        at = int(start * SR)
        accented = (i - offset) % accent_every == 0
        sample = high + (low if accented else 0)
        y[at : at + len(sample)] += sample[: len(y) - at]
    return y


@pytest.mark.parametrize("cents", [-30.0, 0.0, 25.0])
def test_tuning_offset_of_detuned_tones(cents: float) -> None:
    y = np.concatenate([tone(midi_hz(n, cents), 1.0) for n in (57, 60, 64, 69, 72)])

    assert estimate_tuning_cents(y) == pytest.approx(cents, abs=6)


@pytest.mark.parametrize(
    ("chords", "tonic", "mode"),
    [
        ([[60, 64, 67], [65, 69, 72], [67, 71, 74], [60, 64, 67]], "C", "major"),
        ([[57, 60, 64], [62, 65, 69], [64, 68, 71], [57, 60, 64]], "A", "minor"),
        ([[62, 66, 69], [67, 71, 74], [69, 73, 76], [62, 66, 69]], "D", "major"),
    ],
)
def test_key_of_sine_chord_progressions(chords: list[list[int]], tonic: str, mode: str) -> None:
    key = estimate_key(progression(chords))

    assert (key.tonic, key.mode) == (tonic, mode)
    assert key.confidence > 0


def test_key_follows_a_detuned_recording() -> None:
    y = np.concatenate([chord(c, 1.5, cents=-40) for c in [[63, 67, 70], [68, 72, 75]] * 2])

    key = estimate_key(y, tuning_cents=estimate_tuning_cents(y))

    assert (key.tonic, key.mode) == ("Eb", "major")


@pytest.mark.parametrize("bpm", [100.0, 120.0, 140.0])
def test_tempo_of_click_tracks(bpm: float) -> None:
    measured, beats, _ = track_beats(clicks(bpm, 20.0))

    assert measured == pytest.approx(bpm, rel=0.03)
    assert np.median(np.diff(beats)) == pytest.approx(60 / bpm, rel=0.03)


@pytest.mark.parametrize("offset", [0, 1, 2, 3])
def test_downbeats_land_on_the_accented_clicks(offset: int) -> None:
    bpm = 120.0
    y = clicks(bpm, 20.0, offset=offset)
    accented = [0.5 + i * 60 / bpm for i in range(40) if (i - offset) % 4 == 0]

    _, _, downbeats = track_beats(y)

    assert len(downbeats) >= 6
    # Most detected downbeats sit on an accented click (within 70 ms).
    hits = sum(min(abs(d - a) for a in accented) < 0.07 for d in downbeats)
    assert hits / len(downbeats) > 0.8


def test_analyse_stereo_44k_and_round_trip() -> None:
    mono = clicks(120.0, 12.0)[: SR * 12]
    stereo = np.repeat(np.interp(np.arange(0, len(mono), SR / 44_100), np.arange(len(mono)), mono)[:, None], 2, axis=1).astype(np.float32)  # fmt: skip

    result = analyse(stereo, 44_100)

    assert result.bpm == pytest.approx(120.0, rel=0.03)
    assert Analysis.from_json(result.to_json()) == result


def test_analyse_silence_is_neutral() -> None:
    result = analyse(np.zeros((44_100 * 2, 2), dtype=np.float32), 44_100)

    assert result.bpm == 0.0
    assert result.beats == []
