"""Practice exports: tempo, pitch and click stem (synthetic signals only)."""

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cover_maker.audio import practice
from cover_maker.audio.practice import Practice

RATE = 44_100


def sine(freq: float, seconds: float = 2.0) -> np.ndarray:
    t = np.arange(int(seconds * RATE)) / RATE
    mono = 0.3 * np.sin(2 * np.pi * freq * t)
    return np.stack([mono, mono], axis=1).astype(np.float32)


def dominant_hz(audio: np.ndarray) -> float:
    middle = audio[len(audio) // 4 : len(audio) // 4 + 16_384, 0]
    spectrum = np.abs(np.fft.rfft(middle * np.hanning(len(middle))))
    return float(np.argmax(spectrum) * RATE / len(middle))


@pytest.mark.parametrize("semitones", [-12.0, -1.0, 2.0, 7.0])
def test_pitch_shift_keeps_length_and_moves_the_pitch(semitones: float) -> None:
    out = practice.apply(sine(440.0), Practice(semitones=semitones))

    assert out.shape == (2 * RATE, 2)
    assert dominant_hz(out) == pytest.approx(440.0 * 2 ** (semitones / 12), rel=0.01)


def test_cents_tune_a_detuned_song_back_to_a440() -> None:
    detuned = sine(440.0 * 2 ** (-30 / 1200))

    out = practice.apply(detuned, Practice(cents=30.0))

    assert dominant_hz(out) == pytest.approx(440.0, rel=0.004)


@pytest.mark.parametrize("tempo", [0.5, 0.8, 1.25, 1.5])
def test_tempo_changes_length_but_not_pitch(tempo: float) -> None:
    out = practice.apply(sine(440.0), Practice(tempo=tempo))

    assert len(out) == pytest.approx(2 * RATE / tempo, abs=2)
    assert dominant_hz(out) == pytest.approx(440.0, rel=0.01)


def test_identity_returns_the_input_untouched() -> None:
    audio = sine(220.0)

    assert practice.apply(audio, Practice()) is audio


@settings(max_examples=40, deadline=None)
@given(
    tempo=st.floats(0.5, 1.5),
    semitones=st.floats(-12, 12),
    cents=st.floats(-50, 50),
)
def test_correction_undoes_the_resample_pitch(tempo: float, semitones: float, cents: float) -> None:
    settings_ = Practice(tempo=tempo, semitones=semitones, cents=cents)
    # Resampling by `tempo` moves the pitch by 12*log2(tempo); the stretch takes it back.
    total = 12 * math.log2(tempo) + settings_.correction

    assert total == pytest.approx(semitones + cents / 100, abs=1e-9)


@pytest.mark.parametrize("bad", [{"tempo": 0.4}, {"tempo": 1.6}, {"semitones": 13}, {"cents": -51}])
def test_out_of_range_settings_are_rejected(bad: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        Practice(**bad)


def test_suffix_names_the_change() -> None:
    assert Practice().suffix() == ""
    assert Practice(tempo=0.8, semitones=-1).suffix() == "-1 st, 80 %"


def test_click_lands_on_the_grid_with_accented_downbeats() -> None:
    beats = [0.5, 1.0, 1.5, 2.0, 2.5]
    click = practice.render_click(beats, [0.5, 2.5], 3 * RATE)

    def peak(at: float) -> float:
        return float(np.abs(click[int(at * RATE) : int((at + 0.03) * RATE)]).max())

    assert all(peak(beat) > 0.1 for beat in beats)
    assert peak(0.5) > peak(1.0)  # downbeats are louder
    assert np.all(click[: int(0.5 * RATE)] == 0)
    assert np.all(click[int(0.55 * RATE) : int(1.0 * RATE)] == 0)
    assert np.all(click[int(2.54 * RATE) :] == 0)


def test_click_ignores_beats_outside_the_song() -> None:
    click = practice.render_click([-1.0, 0.0, 99.0], [], RATE)

    assert np.abs(click[: int(0.03 * RATE)]).max() > 0
    assert np.all(click[int(0.03 * RATE) + 1 :] == 0)
