"""Standard MIDI File writer for one transcribed stem.

A format 1 file with two tracks:

1. the conductor track: song title, time signatures (``FF 58``) and tempo
   changes (``FF 51``) from the tempo map;
2. the stem's notes on one channel (channel 10 for drums, General MIDI
   percussion), after its name and a program change.

Note times in seconds become ticks through the same tempo map, so a DAW that
follows the file's tempo plays every note where it sounds in the stem. The tempo
map and the file's building blocks are the DAW session export's (``daw/tempo.py``,
``daw/midi.py``), so both kinds of file share one bar grid.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence

from ..daw.midi import TICKS_PER_QUARTER, meta_event, text_bytes, track_chunk
from ..daw.model import TempoPoint
from ..daw.tempo import beats_at, time_signature_changes
from .notes import Note

DRUM_CHANNEL = 9  # channel 10, counting from 1


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

    conductor: list[tuple[int, int, bytes]] = [(0, 0, meta_event(0x03, text_bytes(title)))]
    for point in time_signature_changes(tempo):
        # numerator, denominator as a power of two (4 = 2^2), clocks per click, 32nds per quarter
        conductor.append(
            (tick(point.time), 1, meta_event(0x58, bytes([point.numerator, 2, 24, 8])))
        )
    for point in tempo:
        micros = round(60_000_000 / point.bpm)
        conductor.append((tick(point.time), 2, meta_event(0x51, micros.to_bytes(3, "big"))))

    channel = DRUM_CHANNEL if drums else 0
    events: list[tuple[int, int, bytes]] = [(0, 0, meta_event(0x03, text_bytes(track)))]
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
    return header + track_chunk(conductor) + track_chunk(events)
