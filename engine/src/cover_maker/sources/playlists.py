# pyright: basic
# (This module parses untyped JSON/CSV exported by other tools.)
"""Parsers for playlist files the user exports from elsewhere.

Supported: a streaming service's personal data export (``Playlist*.json`` and
``YourLibrary.json``), CSV with title/artist columns, JSPF and M3U/M3U8. The
entries are only used to find matching files in the user's local library.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PlaylistEntry:
    title: str
    artist: str = ""
    album: str = ""
    duration_s: float | None = None
    location: str | None = None  # M3U path, when present


@dataclass(frozen=True)
class ImportedPlaylist:
    name: str
    entries: list[PlaylistEntry]


class PlaylistFormatError(ValueError):
    pass


def parse_playlist_file(path: Path) -> list[ImportedPlaylist]:
    suffix = path.suffix.lower()
    if suffix in (".m3u", ".m3u8"):
        return [_parse_m3u(path)]
    if suffix == ".csv":
        return [_parse_csv(path)]
    if suffix in (".json", ".jspf"):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return _parse_json(data, path.stem)
    raise PlaylistFormatError(f"unsupported playlist file type: {path.suffix}")


def _parse_json(data: Any, fallback_name: str) -> list[ImportedPlaylist]:
    if isinstance(data, dict) and "playlist" in data:  # JSPF
        playlist = data["playlist"]
        tracks = playlist.get("track") or []
        return [
            ImportedPlaylist(
                playlist.get("title") or fallback_name,
                [
                    PlaylistEntry(
                        title=t.get("title", ""),
                        artist=t.get("creator", ""),
                        album=t.get("album", ""),
                        duration_s=(t["duration"] / 1000) if t.get("duration") else None,
                    )
                    for t in tracks
                    if t.get("title")
                ],
            )
        ]
    if isinstance(data, dict) and "playlists" in data:  # data export: Playlist*.json
        result: list[ImportedPlaylist] = []
        for playlist in data["playlists"]:
            entries = []
            for item in playlist.get("items") or []:
                track = item.get("track") or {}
                if track.get("trackName"):
                    entries.append(
                        PlaylistEntry(
                            title=track["trackName"],
                            artist=track.get("artistName", ""),
                            album=track.get("albumName", ""),
                        )
                    )
            result.append(ImportedPlaylist(playlist.get("name") or fallback_name, entries))
        return result
    if isinstance(data, dict) and "tracks" in data:  # data export: YourLibrary.json
        entries = [
            PlaylistEntry(title=t["track"], artist=t.get("artist", ""), album=t.get("album", ""))
            for t in data["tracks"]
            if t.get("track")
        ]
        return [ImportedPlaylist("Liked songs", entries)]
    raise PlaylistFormatError("unrecognised JSON playlist structure")


_TITLE_COLUMNS = ("track name", "title", "track", "name", "song")
_ARTIST_COLUMNS = ("artist name(s)", "artist name", "artist", "artists", "creator")
_ALBUM_COLUMNS = ("album name", "album")
_DURATION_COLUMNS = ("duration (ms)", "duration_ms", "duration")


def _pick(row: dict[str, str], names: tuple[str, ...]) -> str:
    lowered = {key.strip().lower(): value for key, value in row.items() if key}
    for name in names:
        if lowered.get(name):
            return lowered[name].strip()
    return ""


def _parse_csv(path: Path) -> ImportedPlaylist:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if rows and not _pick(rows[0], _TITLE_COLUMNS):
        raise PlaylistFormatError("CSV needs a title column (e.g. 'Track Name' or 'Title')")
    entries = []
    for row in rows:
        title = _pick(row, _TITLE_COLUMNS)
        if not title:
            continue
        raw_duration = _pick(row, _DURATION_COLUMNS)
        duration = (
            float(raw_duration) / 1000 if raw_duration.replace(".", "", 1).isdigit() else None
        )
        entries.append(
            PlaylistEntry(title, _pick(row, _ARTIST_COLUMNS), _pick(row, _ALBUM_COLUMNS), duration)
        )
    return ImportedPlaylist(path.stem, entries)


_EXTINF = re.compile(r"#EXTINF:(-?\d+(?:\.\d+)?),(.*)")


def _parse_m3u(path: Path) -> ImportedPlaylist:
    entries: list[PlaylistEntry] = []
    pending: tuple[float | None, str] | None = None
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        match = _EXTINF.match(line)
        if match:
            seconds = float(match.group(1))
            pending = (seconds if seconds > 0 else None, match.group(2).strip())
            continue
        if line.startswith("#"):
            continue
        duration, label = pending or (None, Path(line).stem)
        artist, _, title = label.partition(" - ")
        if not title:
            artist, title = "", label
        entries.append(
            PlaylistEntry(title.strip(), artist.strip(), duration_s=duration, location=line)
        )
        pending = None
    return ImportedPlaylist(path.stem, entries)
