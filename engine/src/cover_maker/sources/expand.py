"""Expand user inputs into job inputs: folders become files, playlists become videos."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..library.matching import scan_folder
from .links import InputKind, parse_input
from .youtube import VideoInfo, playlist_entries

RIGHTS_NOTICE = (
    "Only download content you own or are allowed to use. You are responsible for "
    "complying with your local law and the platform's terms (see DISCLAIMER.md)."
)


def expand_inputs(
    raw_inputs: list[str],
    *,
    list_playlist: Callable[[str], list[VideoInfo]] = playlist_entries,
) -> tuple[list[str], int]:
    """Return (job inputs, number of online inputs)."""
    expanded: list[str] = []
    online = 0
    for raw in raw_inputs:
        parsed = parse_input(raw)
        if parsed.kind is InputKind.FOLDER:
            expanded += [str(path) for path in scan_folder(Path(parsed.value))]
        elif parsed.kind is InputKind.FILE:
            if not Path(parsed.value).exists():
                raise FileNotFoundError(f"file not found: {parsed.value}")
            expanded.append(parsed.value)
        elif parsed.kind is InputKind.PLAYLIST:
            entries = list_playlist(parsed.url)
            expanded += [f"https://www.youtube.com/watch?v={entry.video_id}" for entry in entries]
            online += len(entries)
        else:
            expanded.append(parsed.url)
            online += 1
    return expanded, online
