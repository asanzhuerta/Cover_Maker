"""Core value types shared by the engine modules."""

from __future__ import annotations

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


ALL_STEMS: tuple[Stem, ...] = tuple(Stem)


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
