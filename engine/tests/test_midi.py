"""Audio-to-MIDI (FR-MIDI-01): synthetic tones, chords and drums with known notes."""

from __future__ import annotations

import struct
from dataclasses import dataclass

import numpy as np
import pytest
from numpy.typing import NDArray

from cover_maker.daw.tempo import beats_at, tempo_map
from cover_maker.midi import convert, smf
from cover_maker.midi.basic_pitch import BasicPitch, frame_times
from cover_maker.midi.notes import Note, monophonic

SR = 44_100
ONSET_TOLERANCE = 0.05  # seconds
OFFSET_TOLERANCE = 0.12  # note ends are less precise than starts


def _signal(seconds: float) -> NDArray[np.float64]:
    return np.zeros(int(seconds * SR))


def _add_tone(y: NDArray[np.float64], pitch: int, start: float, length: float, amp: float) -> None:
    """A harmonic tone (four partials) with short fades, like a plucked or sung note."""
    first = int(start * SR)
    t = np.arange(int(length * SR)) / SR
    envelope = np.minimum(1.0, t / 0.01) * np.minimum(1.0, (length - t) / 0.02)
    freq = 440.0 * 2 ** ((pitch - 69) / 12)
    for harmonic, weight in ((1, 1.0), (2, 0.5), (3, 0.25), (4, 0.12)):
        y[first : first + len(t)] += (
            amp * weight * np.sin(2 * np.pi * freq * harmonic * t) * envelope
        )


def _stereo(y: NDArray[np.float64]) -> NDArray[np.float32]:
    return np.stack([y, y], axis=1).astype(np.float32)


@pytest.fixture(scope="module")
def model() -> BasicPitch:
    return BasicPitch(threads=2)


MELODY = [(60, 0.5), (64, 1.5), (67, 2.5), (72, 3.5), (45, 4.5)]  # (pitch, start)


def test_a_melody_gives_each_note_with_its_pitch_and_timing(model: BasicPitch) -> None:
    y = _signal(6.0)
    for pitch, start in MELODY:
        _add_tone(y, pitch, start, 0.6, 0.3)

    notes = convert.transcribe("vocals", _stereo(y), SR, model=model)

    assert [n.pitch for n in notes] == [p for p, _ in MELODY]
    for note, (_, start) in zip(notes, MELODY, strict=True):
        assert abs(note.start - start) <= ONSET_TOLERANCE
        assert abs(note.end - (start + 0.6)) <= OFFSET_TOLERANCE
        assert 64 <= note.velocity <= 127


def test_a_chord_gives_its_three_notes_as_the_strongest(model: BasicPitch) -> None:
    y = _signal(3.0)
    for pitch in (60, 64, 67):  # C major
        _add_tone(y, pitch, 0.5, 1.5, 0.2)

    notes = convert.transcribe("piano", _stereo(y), SR, model=model)

    strongest = sorted(notes, key=lambda n: -n.velocity)[:3]
    assert {n.pitch for n in strongest} == {60, 64, 67}
    for note in strongest:
        assert abs(note.start - 0.5) <= ONSET_TOLERANCE
        assert abs(note.end - 2.0) <= OFFSET_TOLERANCE
    # Anything else is a weaker overtone of the chord, never a wrong pitch class below it.
    assert all(n.pitch >= 60 for n in notes)


def test_the_bass_profile_ignores_notes_above_its_range(model: BasicPitch) -> None:
    y = _signal(3.0)
    _add_tone(y, 40, 0.5, 0.8, 0.3)  # E2
    _add_tone(y, 84, 1.8, 0.8, 0.3)  # C6, far above a bass

    notes = convert.transcribe("bass", _stereo(y), SR, model=model)

    assert [n.pitch for n in notes] == [40]


def test_silence_gives_no_notes(model: BasicPitch) -> None:
    assert convert.transcribe("guitar", _stereo(_signal(2.0)), SR, model=model) == []


def test_frame_times_follow_the_window_hop() -> None:
    times = frame_times(300)
    assert times[0] == 0.0
    assert times[1] == pytest.approx(256 / 22_050)
    # Frame 142 is the first of the second window, one hop (36 164 samples) later.
    assert times[142] == pytest.approx(36_164 / 22_050)


def test_monophonic_keeps_the_louder_of_overlapping_notes() -> None:
    notes = [Note(0.0, 1.0, 60, 100), Note(0.5, 1.5, 72, 40), Note(0.8, 2.0, 64, 110)]

    kept = monophonic(notes)

    assert kept == [Note(0.0, 0.8, 60, 100), Note(0.8, 2.0, 64, 110)]


# ------------------------------------------------------------------ drums

KICKS = [0.2, 1.2]
SNARES = [0.7, 1.7]
HATS = [0.2 + 0.25 * i for i in range(8)]


def _drum_pattern() -> NDArray[np.float64]:
    from scipy.signal import butter, sosfilt  # pyright: ignore[reportUnknownVariableType]

    rng = np.random.default_rng(1)
    y = _signal(2.5)
    t = np.arange(int(0.3 * SR)) / SR
    kick = 0.9 * np.sin(2 * np.pi * (50 * t + 70 * (1 - np.exp(-t * 30)) / 30)) * np.exp(-t * 12)
    band = butter(4, [200, 4000], "bandpass", fs=SR, output="sos")
    snare = 0.5 * np.asarray(sosfilt(band, rng.standard_normal(len(t)))) * np.exp(-t * 25)
    snare = snare + 0.3 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30)
    high = butter(4, 7000, "highpass", fs=SR, output="sos")
    hat = 0.3 * np.asarray(sosfilt(high, rng.standard_normal(len(t)))) * np.exp(-t * 60)
    for times, sound in ((KICKS, kick), (SNARES, snare), (HATS, hat)):
        for at in times:
            first = int(at * SR)
            y[first : first + len(t)] += np.asarray(sound)[: len(y) - first]
    return y


def test_drums_become_kick_snare_and_hi_hat_on_their_beats() -> None:
    notes = convert.transcribe("drums", _stereo(_drum_pattern()), SR)

    for pitch, expected in ((36, KICKS), (38, SNARES), (42, HATS)):
        found = [n.start for n in notes if n.pitch == pitch]
        assert len(found) == len(expected), (pitch, found)
        for got, want in zip(found, expected, strict=True):
            assert abs(got - want) <= 0.03
    assert {n.pitch for n in notes} == {36, 38, 42}


# ------------------------------------------------------------------ tempo map and file


def test_tempo_map_puts_bar_lines_on_the_downbeats_after_a_pickup() -> None:
    # 120 BPM in 4/4, first downbeat after one beat of pickup.
    downbeats = [0.5 + 2.0 * bar for bar in range(8)]

    tempo = tempo_map(downbeats, 120.0)

    assert tempo[0].time == 0.0 and tempo[0].numerator == 1
    assert beats_at(tempo, 0.5) == pytest.approx(1.0)
    for bar, time in enumerate(downbeats):
        assert beats_at(tempo, time) == pytest.approx(1.0 + 4 * bar, abs=1e-3)


def test_without_a_beat_grid_the_tempo_is_120_bpm() -> None:
    tempo = tempo_map([], 0.0)
    assert len(tempo) == 1 and tempo[0].bpm == 120.0


@dataclass
class _Track:
    name: str = ""
    tempos: list[tuple[int, int]] | None = None  # (tick, microseconds per quarter)
    signatures: list[tuple[int, int]] | None = None  # (tick, numerator)
    notes: list[tuple[int, int, int, int]] | None = None  # (on tick, off tick, channel, pitch)
    program: int | None = None


def _vlq(data: bytes, at: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[at]
        at += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, at


def _parse(data: bytes) -> tuple[int, int, list[_Track]]:
    """A minimal reader for the files the writer makes (no running status)."""
    assert data[:4] == b"MThd"
    _, fmt, count, division = struct.unpack(">IHHH", data[4:14])
    at = 14
    tracks: list[_Track] = []
    for _ in range(count):
        assert data[at : at + 4] == b"MTrk"
        (length,) = struct.unpack(">I", data[at + 4 : at + 8])
        end = at + 8 + length
        at += 8
        track = _Track(tempos=[], signatures=[], notes=[])
        tick = 0
        open_notes: dict[tuple[int, int], int] = {}
        while at < end:
            delta, at = _vlq(data, at)
            tick += delta
            status = data[at]
            if status == 0xFF:
                kind = data[at + 1]
                size, at = _vlq(data, at + 2)
                payload = data[at : at + size]
                at += size
                if kind == 0x03:
                    track.name = payload.decode()
                elif kind == 0x51:
                    track.tempos.append((tick, int.from_bytes(payload, "big")))  # type: ignore[union-attr]
                elif kind == 0x58:
                    track.signatures.append((tick, payload[0]))  # type: ignore[union-attr]
            elif status & 0xF0 == 0xC0:
                track.program = data[at + 1]
                at += 2
            else:
                channel, pitch, velocity = status & 0x0F, data[at + 1], data[at + 2]
                at += 3
                if status & 0xF0 == 0x90 and velocity > 0:
                    open_notes[(channel, pitch)] = tick
                else:
                    started = open_notes.pop((channel, pitch))
                    track.notes.append((started, tick, channel, pitch))  # type: ignore[union-attr]
        assert not open_notes
        tracks.append(track)
    return fmt, division, tracks


def test_the_file_has_the_tempo_map_and_notes_on_the_beat_grid() -> None:
    downbeats = [0.5 + 2.0 * bar for bar in range(4)]
    tempo = tempo_map(downbeats, 120.0)
    notes = [Note(0.5, 1.0, 60, 100), Note(2.5, 3.0, 67, 90), Note(2.75, 3.0, 67, 80)]

    data = convert.to_midi(notes, tempo, "piano", "Song")
    fmt, division, (conductor, part) = _parse(data)

    assert (fmt, division) == (1, smf.TICKS_PER_QUARTER)
    assert conductor.name == "Song" and part.name == "Piano"
    assert conductor.signatures == [(0, 1), (960, 4)]
    assert conductor.tempos is not None and conductor.tempos[-1] == (960, 500_000)
    assert part.program == 0
    q = smf.TICKS_PER_QUARTER
    # A note at the first downbeat sits on bar 2, beat 1; repeated pitches never overlap.
    assert part.notes == [
        (q, 2 * q, 0, 60),
        (5 * q, int(5.5 * q), 0, 67),
        (int(5.5 * q), 6 * q, 0, 67),
    ]


def test_drum_files_use_the_percussion_channel() -> None:
    data = convert.to_midi([Note(0.0, 0.06, 36, 120)], tempo_map([], 0.0), "drums", "Song")
    _, _, (_, part) = _parse(data)
    assert part.program is None
    assert part.notes is not None and part.notes[0][2] == smf.DRUM_CHANNEL
