"""Standard MIDI File writer for one transcribed stem.

A format 1 file with two tracks:

1. the conductor track: song title, time signatures (``FF 58``) and tempo
   changes (``FF 51``) from the tempo map;
2. the stem's notes on one channel (channel 10 for drums, General MIDI
   percussion), after its name and a program change.

Note times in seconds become ticks through the same tempo map, so a DAW that
follows the file's tempo plays every note where it sounds in the stem.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence

from .notes import Note
from .tempo import TempoPoint, beats_at, time_signature_changes

TICKS_PER_QUARTER = 960
DRUM_CHANNEL = 9  # channel 10, counting from 1


def _vlq(value: int) -> bytes:
    """MIDI variable-length quantity."""
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(out))


def _meta(kind: int, data: bytes) -> bytes:
    return bytes([0xFF, kind]) + _vlq(len(data)) + data


def _text(text: str) -> bytes:
    return " ".join(text.split()).encode("utf-8")


def _track(events: list[tuple[int, int, bytes]]) -> bytes:
    """Chunk from (tick, order, event) tuples; at one tick, lower orders come first."""
    data = bytearray()
    now = 0
    for at, _order, event in sorted(events, key=lambda e: (e[0], e[1])):
        data += _vlq(at - now) + event
        now = at
    data += _vlq(0) + _meta(0x2F, b"")
    return b"MTrk" + struct.pack(">I", len(data)) + bytes(data)


def _separate(notes: Sequence[Note]) -> list[Note]:
    """Shorten a note that would still sound when the same pitch starts again."""
    ordered = sorted(notes, key=lambda n: (n.pitch, n.start))
    out: list[Note] = []
    for note in ordered:
        if out and out[-1].pitch == note.pitch and out[-1].end > note.start:
            last = out.pop()
            if note.start > last.start:
                out.append(Note(last.start, note.start, last.pitch, last.velocity))
        out.append(note)
    return out


def write(
    notes: Sequence[Note],
    tempo: Sequence[TempoPoint],
    *,
    title: str,
    track: str,
    program: int = 0,
    drums: bool = False,
) -> bytes:
    """The ``.mid`` file's bytes."""

    def tick(seconds: float) -> int:
        return round(beats_at(tempo, max(0.0, seconds)) * TICKS_PER_QUARTER)

    conductor: list[tuple[int, int, bytes]] = [(0, 0, _meta(0x03, _text(title)))]
    for point in time_signature_changes(tempo):
        # numerator, denominator as a power of two (4 = 2^2), clocks per click, 32nds per quarter
        conductor.append((tick(point.time), 1, _meta(0x58, bytes([point.numerator, 2, 24, 8]))))
    for point in tempo:
        micros = round(60_000_000 / point.bpm)
        conductor.append((tick(point.time), 2, _meta(0x51, micros.to_bytes(3, "big"))))

    channel = DRUM_CHANNEL if drums else 0
    events: list[tuple[int, int, bytes]] = [(0, 0, _meta(0x03, _text(track)))]
    if not drums:
        events.append((0, 1, bytes([0xC0 | channel, program & 0x7F])))
    for note in _separate(notes):
        start = tick(note.start)
        end = max(start + 1, tick(note.end))
        pitch = max(0, min(127, note.pitch))
        velocity = max(1, min(127, note.velocity))
        events.append((start, 3, bytes([0x90 | channel, pitch, velocity])))
        events.append((end, 2, bytes([0x80 | channel, pitch, 0])))  # offs before ons

    header = b"MThd" + struct.pack(">IHHH", 6, 1, 2, TICKS_PER_QUARTER)
    return header + _track(conductor) + _track(events)
