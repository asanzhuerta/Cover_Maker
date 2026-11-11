"""Write an item's DAW session: stems next to REAPER, DAWproject and MIDI files.

The folder ``<title> - DAW session`` in the job's output folder holds:

- one 32-bit float WAV per stem, named like the stem export (``<title> - Vocals.wav``),
  plus ``Residual`` (the mix minus every stem; muted when the mixer drops it) and the
  ``Original mix`` (muted, for reference). WAV keeps every file sample-aligned at 0,
  which MP3's encoder delay would not;
- ``<title>.RPP``, ``<title>.dawproject`` and ``<title> - tempo map.mid``, which all
  reference the same audio files.

Nothing is ever overwritten: a second export gets ``(2)`` and so on.
"""

from __future__ import annotations

import shutil
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf  # pyright: ignore[reportMissingTypeStubs]

from ..audio import io
from ..audio.analysis import Analysis
from ..domain import ALL_STEMS, ResidualMode, Stem
from ..pipeline.runner import MixSources
from ..store.analyses import Marker as StoredMarker
from . import dawproject, midi, reaper
from .model import DawFormat, Key, Marker, Session, Track
from .tempo import DEFAULT_BPM, tempo_map

RESIDUAL = "Residual"
ORIGINAL = "Original mix"


@dataclass(frozen=True)
class TrackSettings:
    gain: float = 1.0  # linear
    pan: float = 0.0  # -1 .. 1
    muted: bool = False


@dataclass(frozen=True)
class SessionFiles:
    folder: Path
    projects: dict[DawFormat, Path]
    tracks: list[str] = field(default_factory=list[str])


def _free_folder(parent: Path, base: str) -> Path:
    target = parent / base
    counter = 2
    while target.exists():
        target = parent / f"{base} ({counter})"
        counter += 1
    return target


def _audio_file(source: Path, target: Path) -> tuple[float, int]:
    """Copy (or convert to) a float WAV; returns its length in seconds and channels."""
    if source.suffix.lower() == ".wav":
        shutil.copyfile(source, target)
    else:
        io.write_float(io.read(source), target)
    info = sf.info(str(target))
    return float(info.frames) / float(info.samplerate), int(info.channels)


def _residual(sources: MixSources, target: Path) -> tuple[float, int]:
    """Write the mix minus every stem, one stem in memory at a time."""
    rest = io.read(sources.mix).astype(np.float32, copy=True)
    frames = len(rest)
    for path in sources.stems.values():
        stem = io.read(path)[:frames]
        rest[: len(stem)] -= stem
    io.write_float(rest, target)
    return frames / io.SAMPLE_RATE, int(rest.shape[1])


def build_tracks(
    sources: MixSources,
    folder: Path,
    settings: Mapping[Stem, TrackSettings],
    residual: ResidualMode,
) -> list[Track]:
    """Write the audio files into ``folder`` and describe one track per file."""
    tracks: list[Track] = []
    for stem in ALL_STEMS:
        path = sources.stems.get(stem)
        if path is None:
            continue
        name = stem.value.capitalize()
        file = f"{sources.title} - {name}.wav"
        seconds, channels = _audio_file(path, folder / file)
        chosen = settings.get(stem, TrackSettings())
        tracks.append(Track(name, file, seconds, channels, chosen.gain, chosen.pan, chosen.muted))
    file = f"{sources.title} - {RESIDUAL}.wav"
    seconds, channels = _residual(sources, folder / file)
    tracks.append(Track(RESIDUAL, file, seconds, channels, muted=residual is ResidualMode.DROP))
    file = f"{sources.title} - {ORIGINAL}.wav"
    seconds, channels = _audio_file(sources.mix, folder / file)
    tracks.append(Track(ORIGINAL, file, seconds, channels, muted=True))
    return tracks


def build_session(
    title: str,
    tracks: Sequence[Track],
    analysis: Analysis | None,
    markers: Sequence[StoredMarker] = (),
    artist: str | None = None,
) -> Session:
    """The format-independent session: tracks plus tempo map, markers and key."""
    length = max((track.seconds for track in tracks), default=0.0)
    if analysis is not None and analysis.bpm > 0:
        tempo = tempo_map(analysis.downbeats, analysis.bpm)
        bpm = round(analysis.bpm, 2)
    else:
        tempo = tempo_map([], 0.0)
        bpm = DEFAULT_BPM
    key = None
    if analysis is not None and analysis.key_confidence > 0:
        key = Key(analysis.key, analysis.mode)
    return Session(
        title=title,
        sample_rate=io.SAMPLE_RATE,
        bpm=bpm,
        tracks=tuple(tracks),
        tempo=tempo,
        markers=tuple(Marker(m.name, m.time) for m in markers if 0 <= m.time <= length),
        key=key,
        tuning_cents=analysis.tuning_cents if analysis is not None else None,
        artist=artist,
        notes=(
            "Every track starts at 0. Keep this folder together: the project "
            "references the audio files next to it.",
        ),
    )


def write_projects(
    session: Session, folder: Path, formats: Collection[DawFormat]
) -> dict[DawFormat, Path]:
    projects: dict[DawFormat, Path] = {}
    if DawFormat.REAPER in formats:
        target = folder / f"{session.title}.RPP"
        target.write_text(reaper.write(session), encoding="utf-8", newline="\n")
        projects[DawFormat.REAPER] = target
    if DawFormat.DAWPROJECT in formats:
        projects[DawFormat.DAWPROJECT] = dawproject.write(
            session, folder / f"{session.title}.dawproject"
        )
    if DawFormat.MIDI in formats:
        target = folder / f"{session.title} - tempo map.mid"
        target.write_bytes(midi.write(session))
        projects[DawFormat.MIDI] = target
    return projects


def export_session(
    sources: MixSources,
    settings: Mapping[Stem, TrackSettings],
    residual: ResidualMode,
    analysis: Analysis | None,
    markers: Sequence[StoredMarker] = (),
    formats: Collection[DawFormat] = tuple(DawFormat),
) -> SessionFiles:
    """Write a new session folder in the job's output folder (never overwrites)."""
    folder = _free_folder(sources.spec.output_dir, f"{sources.title} - DAW session")
    folder.mkdir(parents=True)
    try:
        tracks = build_tracks(sources, folder, settings, residual)
        session = build_session(sources.title, tracks, analysis, markers)
        projects = write_projects(session, folder, formats)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)  # no half-written session is left behind
        raise
    return SessionFiles(folder=folder, projects=projects, tracks=[t.name for t in tracks])
