"""Classify what the user pasted or dropped: a local file, a folder or a video link.

Only links the user supplies are accepted; the engine never searches for music.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import parse_qs, urlparse

AUDIO_EXTENSIONS = frozenset(
    {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".webm", ".aiff", ".aif", ".wma"}
)
YOUTUBE_HOSTS = frozenset(
    {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
)
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


class InputKind(StrEnum):
    FILE = "file"
    FOLDER = "folder"
    VIDEO = "video"
    PLAYLIST = "playlist"


@dataclass(frozen=True)
class ParsedInput:
    kind: InputKind
    value: str  # absolute path, video id or playlist id

    @property
    def is_online(self) -> bool:
        return self.kind in (InputKind.VIDEO, InputKind.PLAYLIST)

    @property
    def url(self) -> str:
        if self.kind is InputKind.VIDEO:
            return f"https://www.youtube.com/watch?v={self.value}"
        if self.kind is InputKind.PLAYLIST:
            return f"https://www.youtube.com/playlist?list={self.value}"
        return self.value


class UnsupportedInput(ValueError):
    pass


def parse_input(text: str, *, prefer_playlist: bool = False) -> ParsedInput:
    """Parse a path or link. A watch link with ``list=`` is a video unless asked otherwise."""
    raw = text.strip().strip('"')
    if raw.lower().startswith(("http://", "https://")):
        return _parse_url(raw, prefer_playlist=prefer_playlist)
    path = Path(raw).expanduser()
    if path.is_dir():
        return ParsedInput(InputKind.FOLDER, str(path.resolve()))
    if path.suffix.lower() in AUDIO_EXTENSIONS:
        return ParsedInput(InputKind.FILE, str(path.resolve()))
    raise UnsupportedInput(f"not an audio file, folder or supported link: {text}")


def _parse_url(url: str, *, prefer_playlist: bool) -> ParsedInput:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in YOUTUBE_HOSTS:
        raise UnsupportedInput(f"unsupported link (only video links are accepted): {url}")
    query = parse_qs(parsed.query)
    playlist = (query.get("list") or [None])[0]
    if host == "youtu.be":
        video = parsed.path.strip("/").split("/")[0]
    elif parsed.path.startswith(("/shorts/", "/live/")):
        video = parsed.path.split("/")[2]
    else:
        video = (query.get("v") or [None])[0]
    # Auto-generated "RD..." mixes are endless radio lists, not user playlists.
    if playlist and playlist.startswith("RD"):
        playlist = None
    if playlist and (prefer_playlist or not video):
        return ParsedInput(InputKind.PLAYLIST, playlist)
    if video and VIDEO_ID.match(video):
        return ParsedInput(InputKind.VIDEO, video)
    raise UnsupportedInput(f"could not find a video or playlist id in: {url}")
