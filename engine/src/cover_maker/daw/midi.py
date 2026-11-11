"""Tempo map as a Standard MIDI File, for DAWs without RPP or DAWproject import.

A format 0 file with one track of meta events only (no notes): track name,
tempo changes (``FF 51``), time signatures (``FF 58``), the key signature
(``FF 59``) and markers (``FF 06``). Times come from the session's tempo map, so
importing the file into a DAW reproduces the same bar grid over stems placed at 0.
"""

from __future__ import annotations

import struct

from .model import Session
from .tempo import beats_at, time_signature_changes

TICKS_PER_QUARTER = 960


# Standard MIDI File building blocks, shared with the audio-to-MIDI files (midi/smf.py).


def vlq(value: int) -> bytes:
    """MIDI variable-length quantity."""
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(out))


def meta_event(kind: int, data: bytes) -> bytes:
    return bytes([0xFF, kind]) + vlq(len(data)) + data


def text_bytes(text: str) -> bytes:
    return " ".join(text.split()).encode("utf-8")


def track_chunk(events: list[tuple[int, int, bytes]]) -> bytes:
    """An ``MTrk`` chunk from (tick, order, event); at one tick, lower orders come first."""
    data = bytearray()
    now = 0
    for at, _order, event in sorted(events, key=lambda e: (e[0], e[1])):
        data += vlq(at - now) + event
        now = at
    data += vlq(0) + meta_event(0x2F, b"")
    return b"MTrk" + struct.pack(">I", len(data)) + bytes(data)


def write(session: Session) -> bytes:
    """The ``.mid`` file's bytes."""

    def tick(seconds: float) -> int:
        return round(beats_at(session.tempo, seconds) * TICKS_PER_QUARTER)

    # (tick, order, event): at the same tick, signatures come before tempo and text.
    events: list[tuple[int, int, bytes]] = [(0, 0, meta_event(0x03, text_bytes(session.title)))]
    if session.key is not None:
        minor = 1 if session.key.mode == "minor" else 0
        events.append((0, 2, meta_event(0x59, struct.pack(">bB", session.key.fifths(), minor))))
    for point in time_signature_changes(session.tempo):
        # numerator, denominator as a power of two (4 = 2^2), clocks per click, 32nds per quarter
        events.append((tick(point.time), 1, meta_event(0x58, bytes([point.numerator, 2, 24, 8]))))
    for point in session.tempo:
        micros = round(60_000_000 / point.bpm)
        events.append((tick(point.time), 3, meta_event(0x51, micros.to_bytes(3, "big"))))
    for marker in session.markers:
        events.append((tick(marker.time), 4, meta_event(0x06, text_bytes(marker.name))))
    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, TICKS_PER_QUARTER)
    return header + track_chunk(events)
