"""Stored musical analysis and section markers, keyed by the decoded mix."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from ..audio.analysis import ANALYSIS_VERSION, Analysis


def analysis_key(mix_sha: str) -> str:
    """Cache key of the analysis step: the same mix and algorithm are never analysed twice."""
    return f"{mix_sha}:analysis-v{ANALYSIS_VERSION}"


def load(conn: sqlite3.Connection, mix_sha: str) -> Analysis | None:
    row = conn.execute(
        "SELECT tuning_cents, key, mode, key_confidence, bpm, beats_json, downbeats_json, version "
        "FROM analyses WHERE cache_key = ?",
        (analysis_key(mix_sha),),
    ).fetchone()
    if row is None:
        return None
    return Analysis(
        tuning_cents=float(row["tuning_cents"]),
        key=str(row["key"]),
        mode=str(row["mode"]),
        key_confidence=float(row["key_confidence"]),
        bpm=float(row["bpm"]),
        beats=[float(t) for t in json.loads(row["beats_json"])],
        downbeats=[float(t) for t in json.loads(row["downbeats_json"])],
        version=int(row["version"]),
    )


def save(conn: sqlite3.Connection, mix_sha: str, analysis: Analysis) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO analyses (cache_key, mix_sha, version, tuning_cents, key, mode, "
        "key_confidence, bpm, beats_json, downbeats_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            analysis_key(mix_sha),
            mix_sha,
            analysis.version,
            analysis.tuning_cents,
            analysis.key,
            analysis.mode,
            analysis.key_confidence,
            analysis.bpm,
            json.dumps(analysis.beats),
            json.dumps(analysis.downbeats),
        ),
    )


@dataclass(frozen=True)
class Marker:
    name: str
    time: float  # seconds from the start of the song

    def to_json(self) -> dict[str, Any]:
        return {"name": self.name, "time": self.time}


def load_markers(conn: sqlite3.Connection, mix_sha: str) -> list[Marker]:
    row = conn.execute("SELECT markers_json FROM markers WHERE mix_sha = ?", (mix_sha,)).fetchone()
    if row is None:
        return []
    raw: list[dict[str, Any]] = json.loads(row["markers_json"])
    return [Marker(name=str(m["name"]), time=float(m["time"])) for m in raw]


def save_markers(conn: sqlite3.Connection, mix_sha: str, markers: list[Marker]) -> list[Marker]:
    ordered = sorted(markers, key=lambda m: m.time)
    conn.execute(
        "INSERT OR REPLACE INTO markers (mix_sha, markers_json) VALUES (?, ?)",
        (mix_sha, json.dumps([m.to_json() for m in ordered])),
    )
    return ordered
