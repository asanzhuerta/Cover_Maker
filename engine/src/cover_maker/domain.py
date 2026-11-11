"""Core value types shared by the engine modules."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Stem(StrEnum):
    VOCALS = "vocals"
    GUITAR = "guitar"
    DRUMS = "drums"
    BASS = "bass"
    PIANO = "piano"
    OTHER = "other"
    # Sub-stems: a stem split further; the id is "<parent>.<part>".
    VOCALS_LEAD = "vocals.lead"
    VOCALS_BACKING = "vocals.backing"


# Top-level stems: together they make the whole song.
ALL_STEMS: tuple[Stem, ...] = (
    Stem.VOCALS,
    Stem.GUITAR,
    Stem.DRUMS,
    Stem.BASS,
    Stem.PIANO,
    Stem.OTHER,
)

# Sub-stems of a top-level stem: together they make their parent.
SUB_STEMS: dict[Stem, tuple[Stem, ...]] = {
    Stem.VOCALS: (Stem.VOCALS_LEAD, Stem.VOCALS_BACKING),
}

_LABELS: dict[Stem, str] = {
    Stem.VOCALS_LEAD: "Lead vocals",
    Stem.VOCALS_BACKING: "Backing vocals",
}


def parent_of(stem: Stem) -> Stem | None:
    """The stem a sub-stem is part of, or None for a top-level stem."""
    return next((top for top, parts in SUB_STEMS.items() if stem in parts), None)


def stem_label(stem: Stem) -> str:
    """Name used in exported file names: "Vocals", "Lead vocals"."""
    return _LABELS.get(stem, stem.value.capitalize())


def split_for(selected: Iterable[Stem]) -> set[Stem]:
    """Stems that together make the whole song, with a stem replaced by its
    sub-stems whenever one of them is selected."""
    chosen = set(selected)
    parts = set(ALL_STEMS)
    for top, subs in SUB_STEMS.items():
        if chosen & set(subs):
            parts.discard(top)
            parts.update(subs)
    return parts


def finest(available: Iterable[Stem]) -> set[Stem]:
    """The available stems with each one replaced by its sub-stems when all of
    them are available, so that no audio is counted twice."""
    present = set(available)
    for top, subs in SUB_STEMS.items():
        if set(subs) <= present:
            present.discard(top)
    return present


def as_parts(stems: Iterable[Stem], parts: set[Stem]) -> set[Stem]:
    """``stems`` written as members of ``parts``: a stem that ``parts`` splits
    becomes its sub-stems."""
    result: set[Stem] = set()
    for stem in stems:
        if stem in parts:
            result.add(stem)
        else:
            result.update(sub for sub in SUB_STEMS.get(stem, ()) if sub in parts)
    return result


class Mode(StrEnum):
    EXTRACT = "extract"  # export the selected stems
    WITHOUT = "without"  # export the song without the selected stems
    BOTH = "both"  # export the selected stems and the song without them


class ResidualMode(StrEnum):
    KEEP = "keep"  # without-X = mix minus selected stems (nothing lost)
    DROP = "drop"  # without-X = sum of the remaining stems (cleaner)


class Preset(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    MAX = "max"


class OutputFormat(StrEnum):
    WAV = "wav"
    FLAC = "flac"
    MP3 = "mp3"


class JobSpec(BaseModel):
    """What the user asked for; stored with the job."""

    inputs: list[str] = Field(min_length=1)  # file paths or video links
    stems: list[Stem] = Field(min_length=1)
    mode: Mode = Mode.EXTRACT
    residual: ResidualMode = ResidualMode.KEEP
    preset: Preset = Preset.BALANCED
    output_dir: Path
    output_format: OutputFormat = OutputFormat.WAV
    allow_cpu_fallback: bool = False
    rights_confirmed: bool = False  # the user confirmed rights to online inputs (FR-SRC-06)

    @field_validator("inputs", mode="before")
    @classmethod
    def _stringify(cls, value: Any) -> Any:
        return [str(item) for item in value] if isinstance(value, list | tuple) else value  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
