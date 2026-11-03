"""Filesystem locations used by the engine.

Everything lives under one home directory, ``%LOCALAPPDATA%/Cover_Maker`` by
default, overridable with ``COVER_MAKER_HOME`` (tests use a temporary folder).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

HOME_ENV = "COVER_MAKER_HOME"


def default_home() -> Path:
    override = os.environ.get(HOME_ENV)
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "Cover_Maker"


@dataclass(frozen=True)
class Paths:
    home: Path

    @classmethod
    def default(cls) -> Paths:
        return cls(default_home())

    @property
    def db(self) -> Path:
        return self.home / "db" / "cover_maker.sqlite3"

    @property
    def assets(self) -> Path:
        return self.home / "library" / "assets"

    @property
    def models(self) -> Path:
        return self.home / "models"

    @property
    def tmp(self) -> Path:
        return self.home / "tmp"

    @property
    def logs(self) -> Path:
        return self.home / "logs"

    def ensure(self) -> Paths:
        for path in (self.db.parent, self.assets, self.models, self.tmp, self.logs):
            path.mkdir(parents=True, exist_ok=True)
        return self
