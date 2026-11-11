"""One stem to one MIDI file: the right transcriber and instrument per stem."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..audio.analysis import to_mono
from ..daw.model import TempoPoint
from . import drums, smf
from .basic_pitch import SAMPLE_RATE, BasicPitch, Settings
from .notes import Note, monophonic

# Bump when the transcription changes so cached MIDI files are made again.
MIDI_VERSION = 1


@dataclass(frozen=True)
class Profile:
    program: int  # General MIDI program, counting from 0
    settings: Settings | None  # None: drum transcription
    mono: bool = False  # melody line: one note at a time


PROFILES: dict[str, Profile] = {
    "vocals": Profile(53, Settings(min_hz=65.0, max_hz=1_400.0), mono=True),  # Voice Oohs
    "bass": Profile(33, Settings(min_hz=30.0, max_hz=420.0), mono=True),  # Electric Bass (finger)
    "guitar": Profile(27, Settings(min_hz=75.0, max_hz=1_500.0)),  # Electric Guitar (clean)
    "piano": Profile(0, Settings()),  # Acoustic Grand Piano
    "other": Profile(4, Settings()),  # Electric Piano 1
    "drums": Profile(0, None),
}


def profile(stem: str) -> Profile:
    """Settings for a stem id; stems without their own profile are transcribed like "other"."""
    if stem in PROFILES:
        return PROFILES[stem]
    return PROFILES["vocals"] if "vocals" in stem else PROFILES["other"]


def transcribe(
    stem: str,
    audio: NDArray[np.float32],
    rate: int,
    *,
    model: BasicPitch | None = None,
    progress: Callable[[float], None] | None = None,
    cancel: threading.Event | None = None,
) -> list[Note]:
    """Notes of a (frames x channels) stem."""
    chosen = profile(stem)
    y = to_mono(audio, rate)
    if chosen.settings is None:
        notes = drums.transcribe(y, SAMPLE_RATE)
        if progress is not None:
            progress(1.0)
        return notes
    notes = (model or BasicPitch()).transcribe(y, chosen.settings, progress, cancel)
    return monophonic(notes) if chosen.mono else notes


def to_midi(notes: Sequence[Note], tempo: Sequence[TempoPoint], stem: str, title: str) -> bytes:
    chosen = profile(stem)
    return smf.write(
        notes,
        tempo,
        title=title,
        track=stem.replace("_", " ").capitalize(),
        program=chosen.program,
        drums=chosen.settings is None,
    )
