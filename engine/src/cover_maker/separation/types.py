"""Messages exchanged between the engine and separation backends."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel

from ..domain import Stem

Device = Literal["gpu", "cpu"]
Precision = Literal["fp32", "fp16"]


class SeparationRequest(BaseModel):
    model_filename: str
    model_dir: Path
    input_path: Path
    output_dir: Path
    stems: dict[str, Stem]  # model output label -> stem id
    device: Device = "gpu"
    precision: Precision = "fp16"
    chunk_s: float | None = None
    threads: int | None = None


class SeparationResult(BaseModel):
    outputs: dict[Stem, Path]
    seconds: float
    device: Device
    precision: Precision
    chunk_s: float | None


class SeparationError(RuntimeError):
    def __init__(self, message: str, *, oom: bool = False) -> None:
        super().__init__(message)
        self.oom = oom


class Cancelled(RuntimeError):
    """The separation was cancelled by the user."""


class Backend(Protocol):
    def separate(self, request: SeparationRequest) -> SeparationResult: ...
