"""What a DAW session holds, independent of the project format."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ..audio.analysis import PITCH_CLASSES


class DawFormat(StrEnum):
    REAPER = "reaper"  # .RPP
    DAWPROJECT = "dawproject"  # .dawproject (Bitwig Studio, Studio One, Cubase, ...)
    MIDI = "midi"  # tempo map, markers and key as a Standard MIDI File


@dataclass(frozen=True)
class Track:
    name: str
    file: str  # file name, relative to the project folder
    seconds: float  # length of the audio file
    channels: int
    gain: float = 1.0  # linear (1 = 0 dB)
    pan: float = 0.0  # -1 (left) .. 1 (right)
    muted: bool = False


@dataclass(frozen=True)
class TempoPoint:
    """A tempo that holds from ``time`` until the next point."""

    time: float  # seconds
    bpm: float
    numerator: int = 4  # beats per bar from this point on (quarter-note beats)
    bar_start: bool = True  # whether a time signature marker starts a bar here


@dataclass(frozen=True)
class Marker:
    name: str
    time: float  # seconds


@dataclass(frozen=True)
class Key:
    tonic: str  # one of PITCH_CLASSES
    mode: str  # "major" or "minor"

    def label(self) -> str:
        return f"{self.tonic} {self.mode}"

    def fifths(self) -> int:
        """Sharps (positive) or flats (negative) of the key signature, -6..6."""
        pitch = PITCH_CLASSES.index(self.tonic)
        major = pitch if self.mode == "major" else (pitch + 3) % 12
        fifths = (major * 7) % 12
        return fifths - 12 if fifths > 6 else fifths


@dataclass(frozen=True)
class Session:
    title: str
    sample_rate: int
    bpm: float  # the song's tempo, for the project's base tempo and notes
    tracks: tuple[Track, ...]
    tempo: tuple[TempoPoint, ...]  # never empty; the first point is at 0
    markers: tuple[Marker, ...] = ()
    key: Key | None = None
    tuning_cents: float | None = None
    artist: str | None = None
    generator: str = "Cover_Maker"
    notes: tuple[str, ...] = field(default=())

    def summary(self) -> list[str]:
        """Human-readable facts for project notes and comments."""
        lines = [f"{self.title}", f"Tempo: {self.bpm:.2f} BPM"]
        if self.key is not None:
            lines.append(f"Key: {self.key.label()}")
        if self.tuning_cents is not None:
            lines.append(f"Tuning: {self.tuning_cents:+.1f} cents from A440")
        lines.extend(self.notes)
        lines.append(f"Exported by {self.generator}.")
        return lines
