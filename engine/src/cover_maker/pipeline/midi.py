"""Audio-to-MIDI step: one MIDI file per stem, with the song's tempo map (ADR-012).

The step runs on demand from the mixer, after separation. It is split so the
caller can keep the library (SQLite) work short and run the transcription on a
CPU thread: :func:`plan` and :func:`finish` touch the database, :func:`convert`
and :func:`export` only read and write files.

Each stem's MIDI file is cached in the asset store under a ``cache_key`` made of
the stem's asset id, the transcription version and the tempo map, so asking
again (or for another stem) never transcribes a stem twice.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..audio import io
from ..audio.analysis import Analysis
from ..midi import convert as midi
from ..midi.basic_pitch import BasicPitch
from ..midi.tempo import TempoPoint, tempo_map
from .runner import CACHE_VERSION, JobRunner, safe_title

STEP = "midi"
NOTES_STEP = "midi_notes"


class StemNotAvailable(ValueError):
    def __init__(self, stems: list[str]) -> None:
        super().__init__(f"this item has no separated stem: {', '.join(stems)}")
        self.stems = stems


@dataclass(frozen=True)
class MidiTask:
    stem: str
    source: Path  # the stem's audio in the library
    key: str  # step cache key
    cached: str | None  # asset id of the MIDI file when it was made before
    notes: int  # notes in the cached file (0 when not cached)
    target: Path  # the exported file next to the stem exports


@dataclass(frozen=True)
class MidiPlan:
    title: str
    tempo: tuple[TempoPoint, ...]
    from_analysis: bool  # False: no beat grid, a single default tempo
    tasks: list[MidiTask]


def _digest(tempo: tuple[TempoPoint, ...]) -> str:
    raw = json.dumps([(p.time, p.bpm, p.bar_start, p.numerator) for p in tempo])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def plan(
    runner: JobRunner, item_id: int, stems: list[str], analysis: Analysis | None
) -> MidiPlan | None:
    """What to convert for an item (database work only). None: nothing separated yet."""
    preview = runner.preview(item_id)
    job = runner.conn.execute("SELECT job_id FROM job_items WHERE id = ?", (item_id,)).fetchone()
    if preview is None or job is None:
        return None
    available: dict[str, str] = preview["stems"]
    missing = [stem for stem in stems if stem not in available]
    if missing:
        raise StemNotAvailable(missing)
    has_grid = analysis is not None and analysis.bpm > 0 and bool(analysis.downbeats)
    tempo = (
        tempo_map(analysis.downbeats, analysis.bpm) if analysis and has_grid else tempo_map([], 0)
    )
    title = safe_title(preview.get("title") or "track")
    output_dir = runner.job_spec(job["job_id"]).output_dir
    digest = _digest(tempo)
    tasks: list[MidiTask] = []
    for stem in dict.fromkeys(stems):  # keep the order, drop repeats
        sha = available[stem]
        key = f"{CACHE_VERSION}:{sha}:{stem}:midi-v{midi.MIDI_VERSION}:{digest}"
        cached = runner.cached(STEP, key)
        count = runner.remembered(NOTES_STEP, key) if cached else None
        tasks.append(
            MidiTask(
                stem=stem,
                source=runner.assets.require(sha),
                key=key,
                cached=str(cached) if cached else None,
                notes=int(count) if isinstance(count, int) else 0,
                target=output_dir / f"{title} - {stem.capitalize()}.mid",
            )
        )
    return MidiPlan(title=title, tempo=tempo, from_analysis=has_grid, tasks=tasks)


def convert(
    task: MidiTask,
    midi_plan: MidiPlan,
    *,
    model: BasicPitch | None = None,
    progress: Callable[[float], None] | None = None,
    cancel: threading.Event | None = None,
) -> tuple[bytes, int]:
    """Transcribe one stem (CPU work, no database). Returns the file and its note count."""
    audio = io.read(task.source)
    notes = midi.transcribe(
        task.stem, audio, io.SAMPLE_RATE, model=model, progress=progress, cancel=cancel
    )
    return midi.to_midi(notes, midi_plan.tempo, task.stem, midi_plan.title), len(notes)


def finish(runner: JobRunner, task: MidiTask, data: bytes, notes: int) -> str:
    """Keep a new MIDI file in the library and remember it under the task's cache key."""
    with tempfile.TemporaryDirectory(dir=runner.paths.tmp) as scratch:
        path = Path(scratch) / f"{task.stem}.mid"
        path.write_bytes(data)
        sha = runner.assets.put(path, "midi", move=True)
    runner.store(STEP, task.key, sha)
    runner.store(NOTES_STEP, task.key, notes)
    return sha


def export(source: Path, target: Path) -> Path:
    """Copy a MIDI file next to the stem exports (the same name, ``.mid``)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.read_bytes() != source.read_bytes():
        shutil.copyfile(source, target)
    return target
