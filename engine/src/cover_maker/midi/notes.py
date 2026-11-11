"""Note events shared by the transcribers and the MIDI writer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Note:
    start: float  # seconds from the start of the song
    end: float
    pitch: int  # MIDI note number (60 = middle C)
    velocity: int  # 1-127


def monophonic(notes: list[Note], min_length: float = 0.06) -> list[Note]:
    """Keep one note at a time (melody lines such as a lead vocal or a bass line).

    When two notes overlap, the louder one wins: the other is shortened to the
    gap left, or dropped when less than ``min_length`` seconds remain.
    """
    kept: list[Note] = []
    for note in sorted(notes, key=lambda n: (n.start, -n.velocity)):
        # A louder note cuts the quieter notes still sounding.
        while kept and note.start < kept[-1].end and note.velocity > kept[-1].velocity:
            last = kept.pop()
            if note.start - last.start >= min_length:
                kept.append(Note(last.start, note.start, last.pitch, last.velocity))
                break
        if kept and note.start < kept[-1].end:
            # A louder note is sounding: keep only what this one adds after it.
            last = kept[-1]
            if note.end - last.end >= min_length:
                kept.append(Note(last.end, note.end, note.pitch, note.velocity))
            continue
        kept.append(note)
    return kept
