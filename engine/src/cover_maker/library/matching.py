# pyright: basic
# (This module reads tags through tinytag, whose attributes are loosely typed.)
"""Match imported playlist entries to audio files the user already has."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from ..sources.links import AUDIO_EXTENSIONS
from ..sources.playlists import PlaylistEntry

AUTO_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.6
_NOISE = re.compile(r"\((?:official|lyric|audio|video|remaster(?:ed)?)[^)]*\)|\[[^\]]*\]", re.I)
_NON_WORD = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class LocalTrack:
    path: Path
    title: str
    artist: str
    album: str
    duration_s: float | None


@dataclass(frozen=True)
class Match:
    track: LocalTrack | None
    score: float

    @property
    def status(self) -> str:
        if self.track is None or self.score < REVIEW_THRESHOLD:
            return "unavailable"
        return "ready" if self.score >= AUTO_THRESHOLD else "needs_review"


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = _NOISE.sub(" ", text.lower())
    text = re.sub(r"\b(feat|ft)\b.*", " ", text)
    return _NON_WORD.sub(" ", text).strip()


def _similarity(a: str, b: str) -> float:
    a, b = normalise(a), normalise(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def score(entry: PlaylistEntry, track: LocalTrack) -> float:
    title = _similarity(entry.title, track.title)
    if not entry.artist:
        base = title
    else:
        artist = _similarity(entry.artist.split(",")[0], track.artist)
        base = 0.65 * title + 0.35 * artist
    if entry.duration_s and track.duration_s:
        difference = abs(entry.duration_s - track.duration_s)
        base -= min(difference / 60, 0.3)  # 30 s off costs 0.15
    return max(0.0, min(1.0, base))


def best_match(entry: PlaylistEntry, tracks: Iterable[LocalTrack]) -> Match:
    best: LocalTrack | None = None
    best_score = 0.0
    for track in tracks:
        value = score(entry, track)
        if value > best_score:
            best, best_score = track, value
    return Match(best, round(best_score, 3))


def read_track(path: Path) -> LocalTrack:
    """Read tags with tinytag (MIT); fall back to 'Artist - Title' in the file name."""
    title, artist, album, duration = "", "", "", None
    try:
        from tinytag import TinyTag

        tag = TinyTag.get(str(path))
        title = str(tag.title or "")
        artist = str(tag.artist or "")
        album = str(tag.album or "")
        duration = float(tag.duration) if tag.duration else None
    except Exception:  # unreadable or unsupported tags must not break the scan
        pass
    if not title:
        stem = re.sub(r"^\d+[\s._-]+", "", path.stem)  # drop track numbers
        left, _, right = stem.partition(" - ")
        artist, title = (left, right) if right else (artist, stem)
    return LocalTrack(path, title.strip(), artist.strip(), album.strip(), duration)


def scan_folder(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
