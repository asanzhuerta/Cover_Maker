"""Disk usage of the library and clean-up of files nothing needs any more.

Every processed song keeps its decoded mix and final stems for the preview
mixer (``job_items.preview_json``). Everything else in the asset store
(downloads, intermediate separations, decoded files of deleted jobs) is a
cache: removing it frees space and only makes a later re-run slower.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..paths import Paths


@dataclass(frozen=True)
class Usage:
    library_bytes: int
    library_files: int
    reclaimable_bytes: int
    reclaimable_files: int
    models_bytes: int
    tmp_bytes: int


def folder_bytes(folder: Path) -> int:
    if not folder.exists():
        return 0
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())


def kept_assets(conn: sqlite3.Connection) -> set[str]:
    """Assets the preview mixer of an existing job item still needs."""
    keep: set[str] = set()
    for row in conn.execute("SELECT preview_json FROM job_items WHERE preview_json IS NOT NULL"):
        try:
            preview: dict[str, Any] = json.loads(row["preview_json"])
        except ValueError:
            continue
        keep.add(str(preview.get("mix", "")))
        stems: dict[str, object] = preview.get("stems") or {}
        keep.update(str(sha) for sha in stems.values())
    return keep


def _reclaimable(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    keep = kept_assets(conn)
    return [
        row
        for row in conn.execute("SELECT sha256, rel_path, bytes FROM assets")
        if row["sha256"] not in keep
    ]


def usage(conn: sqlite3.Connection, paths: Paths) -> Usage:
    total = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(bytes), 0) AS b FROM assets"
    ).fetchone()
    spare = _reclaimable(conn)
    return Usage(
        library_bytes=int(total["b"]),
        library_files=int(total["n"]),
        reclaimable_bytes=sum(int(r["bytes"]) for r in spare),
        reclaimable_files=len(spare),
        models_bytes=folder_bytes(paths.models),
        tmp_bytes=folder_bytes(paths.tmp),
    )


@dataclass(frozen=True)
class TempEntry:
    """One item in the temp folder: usually a job's working folder."""

    name: str
    bytes: int
    files: int
    modified: datetime


def _entry(path: Path) -> TempEntry:
    stat = path.stat()
    if path.is_dir():
        files = [p for p in path.rglob("*") if p.is_file()]
        size, count = sum(p.stat().st_size for p in files), len(files)
        newest = max([stat.st_mtime, *(p.stat().st_mtime for p in files)])
    else:
        size, count, newest = stat.st_size, 1, stat.st_mtime
    return TempEntry(
        name=path.name, bytes=size, files=count,
        modified=datetime.fromtimestamp(newest, tz=UTC),
    )  # fmt: skip


def temporary(paths: Paths) -> list[TempEntry]:
    """What :func:`clear_temporary` would delete, newest first."""
    if not paths.tmp.exists():
        return []
    entries = [_entry(child) for child in paths.tmp.iterdir()]
    return sorted(entries, key=lambda e: e.modified, reverse=True)


def clear_temporary(paths: Paths) -> int:
    """Empty the temp folder (job working folders left by stopped or failed
    jobs). Call it only while no job runs. Returns the bytes freed."""
    freed = 0
    if not paths.tmp.exists():
        return 0
    for child in paths.tmp.iterdir():
        try:
            size = folder_bytes(child) if child.is_dir() else child.stat().st_size
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except OSError:
            continue  # in use or already gone: leave it for the next clean-up
        freed += size
    return freed


def _mentions(value: object, removed: set[str]) -> bool:
    if isinstance(value, str):
        return value in removed
    if isinstance(value, dict):
        return any(_mentions(v, removed) for v in value.values())  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    if isinstance(value, list):
        return any(_mentions(v, removed) for v in value)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return False


def clean_up(conn: sqlite3.Connection, paths: Paths) -> int:
    """Delete cached assets that no preview needs and empty the temp folder.

    Call it only while no job runs. Returns the bytes freed.
    """
    spare = _reclaimable(conn)
    removed = {str(r["sha256"]) for r in spare}
    freed = 0
    for row in spare:
        path = paths.assets / row["rel_path"]
        if path.exists():
            freed += path.stat().st_size
            path.unlink()
    conn.executemany("DELETE FROM assets WHERE sha256 = ?", [(sha,) for sha in removed])
    # Forget cache entries that pointed at the removed files (peaks are keyed by asset).
    stale = [
        (row["step"], row["cache_key"])
        for row in conn.execute("SELECT step, cache_key, output_json FROM step_cache")
        if row["cache_key"] in removed or _mentions(json.loads(row["output_json"]), removed)
    ]
    conn.executemany("DELETE FROM step_cache WHERE step = ? AND cache_key = ?", stale)
    return freed + clear_temporary(paths)
