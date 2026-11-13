"""Filesystem locations used by the engine.

Everything lives under one home directory, overridable with
``COVER_MAKER_HOME`` (tests use a temporary folder), inside the platform's
per-user data folder (``data_root``: ``%LOCALAPPDATA%`` on Windows,
``~/Library/Application Support`` on macOS, ADR-013):

* ``Cover_Maker`` for the installed app (the installer puts the app and its
  runtime there too);
* ``Cover_Maker.dev`` when the engine runs from a source checkout (``uv run``
  in ``engine/``), so development never touches the data of an installed copy.

The desktop shell and the DAW plug-in compute the same folders.
"""

from __future__ import annotations

import os
import sys
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


def data_root(platform: str = sys.platform) -> Path:
    """The per-user folder for application data on ``platform``."""
    if platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    if platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def default_home() -> Path:
    override = os.environ.get(HOME_ENV)
    if override:
        return Path(override)
    return data_root() / (DEV_NAME if running_from_source() else INSTALLED_NAME)


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
