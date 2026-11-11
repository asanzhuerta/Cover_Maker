"""The example song offered on first run.

A short Creative Commons clip ships inside the engine package, so a new user
can hear a separation within minutes, before looking for audio of their own.
Its attribution travels with it: ``add`` copies the clip into the library with
a credits sidecar, and the export then writes ``CREDITS.txt`` next to the stems.

Only CC0 or CC BY audio qualifies, under ``MAX_SECONDS`` and ``MAX_BYTES``.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from .catalogs import Credits, attach

# CC0 or CC BY only: no non-commercial, no-derivatives or share-alike terms.
ALLOWED_LICENCES = (
    "https://creativecommons.org/publicdomain/zero/1.0/",
    "https://creativecommons.org/licenses/by/3.0/",
    "https://creativecommons.org/licenses/by/4.0/",
)
MAX_SECONDS = 30.0
MAX_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class Example:
    file: str
    duration_s: float
    credits: Credits

    @property
    def path(self) -> Path:
        return data_dir() / self.file

    @property
    def size_bytes(self) -> int:
        return self.path.stat().st_size


def data_dir() -> Path:
    return Path(str(resources.files("cover_maker").joinpath("data/example")))


def load() -> Example:
    raw: dict[str, Any] = yaml.safe_load((data_dir() / "example.yaml").read_text("utf-8"))
    credits = Credits(
        title=str(raw["title"]), artist=str(raw["artist"]),
        licence_name=str(raw["licence_name"]), licence_url=str(raw["licence_url"]),
        page_url=str(raw["page_url"]), source="example", changes=str(raw.get("changes", "")),
    )  # fmt: skip
    return Example(file=str(raw["file"]), duration_s=float(raw["duration_s"]), credits=credits)


def add(library: Path) -> Path:
    """Copy the example into the library's ``example`` folder with its credits."""
    example = load()
    return attach(example.path, example.credits, library / "example")
