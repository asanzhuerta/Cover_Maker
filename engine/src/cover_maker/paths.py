"""Filesystem locations used by the engine.

Everything lives under one home directory, overridable with
``COVER_MAKER_HOME`` (tests use a temporary folder):

* ``%LOCALAPPDATA%/Cover_Maker`` for the installed app (the installer puts the
  app and its runtime there too);
* ``%LOCALAPPDATA%/Cover_Maker.dev`` when the engine runs from a source
  checkout (``uv run`` in ``engine/``), so development never touches the data
  of an installed copy.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

HOME_ENV = "COVER_MAKER_HOME"


INSTALLED_NAME = "Cover_Maker"
DEV_NAME = "Cover_Maker.dev"


def running_from_source() -> bool:
    """True for a source checkout: ``engine/pyproject.toml`` sits above the package."""
    project = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        return 'name = "cover-maker"' in project.read_text(encoding="utf-8")
    except OSError:
        return False


def default_home() -> Path:
    override = os.environ.get(HOME_ENV)
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / (DEV_NAME if running_from_source() else INSTALLED_NAME)


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
