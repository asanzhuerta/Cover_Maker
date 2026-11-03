"""Library collections: watched folders, video playlists and imported playlist files.

Syncing a collection refreshes its items and returns the inputs that are ready
to process. Processing is incremental by construction: the job runner caches
every step, so only new or changed items do real work.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from ..sources import youtube
from ..sources.playlists import PlaylistEntry, parse_playlist_file
from .matching import LocalTrack, best_match, read_track, scan_folder


class CollectionKind(StrEnum):
    FOLDER = "folder"
    VIDEO_PLAYLIST = "video_playlist"
    PLAYLIST_FILE = "playlist_file"


@dataclass
class SyncResult:
    collection_id: int
    added: int = 0
    removed: int = 0
    unchanged: int = 0
    ready: list[str] = field(default_factory=list[str])
    needs_review: int = 0
    unavailable: int = 0


@dataclass(frozen=True)
class Item:
    key: str
    title: str
    artist: str = ""
    duration_s: float | None = None
    input: str | None = None  # file path or video URL to process
    score: float | None = None
    status: str = "ready"


EntriesLoader = Callable[[str], list[youtube.VideoInfo]]


class Library:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        playlist_loader: EntriesLoader = youtube.playlist_entries,
    ) -> None:
        self.conn = conn
        self.playlist_loader = playlist_loader

    # ------------------------------------------------------------ collections

    def _create(
        self, kind: CollectionKind, source: str, title: str, extra: dict[str, object]
    ) -> int:
        row = self.conn.execute(
            "SELECT id FROM collections WHERE kind = ? AND source = ?", (kind.value, source)
        ).fetchone()
        if row:
            return int(row["id"])
        cursor = self.conn.execute(
            "INSERT INTO collections (kind, source, title, extra_json) VALUES (?, ?, ?, ?)",
            (kind.value, source, title, json.dumps(extra)),
        )
        return int(cursor.lastrowid or 0)

    def add_folder(self, folder: Path) -> int:
        folder = folder.resolve()
        return self._create(CollectionKind.FOLDER, str(folder), folder.name, {})

    def add_video_playlist(self, playlist_id: str, title: str | None = None) -> int:
        return self._create(CollectionKind.VIDEO_PLAYLIST, playlist_id, title or playlist_id, {})

    def import_playlist_file(self, path: Path, search_folders: Sequence[Path]) -> list[int]:
        """One collection per playlist in the file; entries matched in ``search_folders``."""
        ids: list[int] = []
        folders = [str(folder.resolve()) for folder in search_folders]
        for playlist in parse_playlist_file(path):
            source = f"{path.resolve()}#{playlist.name}"
            ids.append(
                self._create(
                    CollectionKind.PLAYLIST_FILE, source, playlist.name, {"folders": folders}
                )
            )
        return ids

    def collections(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM collection_items i WHERE i.collection_id = c.id "
            "AND i.status != 'removed') AS items FROM collections c ORDER BY c.id"
        ).fetchall()

    def items(self, collection_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM collection_items WHERE collection_id = ? AND status != 'removed' "
            "ORDER BY position",
            (collection_id,),
        ).fetchall()

    def collection(self, collection_id: int) -> sqlite3.Row:
        row = self.conn.execute(
            "SELECT * FROM collections WHERE id = ?", (collection_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"collection {collection_id} does not exist")
        return row

    # ------------------------------------------------------------ sync

    def sync(self, collection_id: int) -> SyncResult:
        row = self.collection(collection_id)
        kind = CollectionKind(row["kind"])
        if kind is CollectionKind.FOLDER:
            items = self._folder_items(Path(row["source"]))
        elif kind is CollectionKind.VIDEO_PLAYLIST:
            items = self._video_items(row["source"])
        else:
            extra = json.loads(row["extra_json"] or "{}")
            items = self._imported_items(
                row["source"], [Path(f) for f in extra.get("folders", [])], collection_id
            )
        result = self._apply(collection_id, items)
        self.conn.execute(
            "UPDATE collections SET synced_at = datetime('now') WHERE id = ?", (collection_id,)
        )
        return result

    def _folder_items(self, folder: Path) -> list[Item]:
        if not folder.exists():
            raise FileNotFoundError(f"watched folder no longer exists: {folder}")
        items: list[Item] = []
        for path in scan_folder(folder):
            track = read_track(path)
            items.append(Item(str(path), track.title, track.artist, track.duration_s, str(path)))
        return items

    def _video_items(self, playlist_id: str) -> list[Item]:
        entries = self.playlist_loader(f"https://www.youtube.com/playlist?list={playlist_id}")
        return [
            Item(
                e.video_id,
                e.title,
                e.uploader or "",
                e.duration_s,
                f"https://www.youtube.com/watch?v={e.video_id}",
            )
            for e in entries
        ]

    def _imported_items(self, source: str, folders: list[Path], collection_id: int) -> list[Item]:
        file_name, _, playlist_name = source.rpartition("#")
        playlists = [p for p in parse_playlist_file(Path(file_name)) if p.name == playlist_name]
        entries: list[PlaylistEntry] = playlists[0].entries if playlists else []
        tracks: list[LocalTrack] = [
            read_track(p) for folder in folders if folder.exists() for p in scan_folder(folder)
        ]
        manual = {
            r["key"]: r
            for r in self.conn.execute(
                "SELECT key, input, title FROM collection_items WHERE collection_id = ? AND manual = 1",
                (collection_id,),
            )
        }
        items: list[Item] = []
        for position, entry in enumerate(entries):
            key = f"{position}:{entry.artist}|{entry.title}".lower()
            if key in manual:  # a user correction always wins over automatic matching
                chosen = manual[key]["input"]
                status = "ready" if chosen else "unavailable"
                items.append(
                    Item(key, entry.title, entry.artist, entry.duration_s, chosen, 1.0, status)
                )
                continue
            match = best_match(entry, tracks)
            chosen = (
                str(match.track.path) if match.track and match.status != "unavailable" else None
            )
            items.append(
                Item(
                    key,
                    entry.title,
                    entry.artist,
                    entry.duration_s,
                    chosen,
                    match.score,
                    match.status,
                )
            )
        return items

    def _apply(self, collection_id: int, items: list[Item]) -> SyncResult:
        result = SyncResult(collection_id)
        existing = {
            r["key"]: r
            for r in self.conn.execute(
                "SELECT key, status FROM collection_items WHERE collection_id = ?", (collection_id,)
            )
        }
        seen: set[str] = set()
        for position, item in enumerate(items):
            seen.add(item.key)
            previous = existing.get(item.key)
            if previous is None or previous["status"] == "removed":
                result.added += 1
            else:
                result.unchanged += 1
            self.conn.execute(
                "INSERT INTO collection_items (collection_id, key, position, title, artist, duration_s, "
                "input, score, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(collection_id, key) DO UPDATE SET position = excluded.position, "
                "title = excluded.title, artist = excluded.artist, duration_s = excluded.duration_s, "
                "input = excluded.input, score = excluded.score, status = excluded.status",
                (
                    collection_id,
                    item.key,
                    position,
                    item.title,
                    item.artist,
                    item.duration_s,
                    item.input,
                    item.score,
                    item.status,
                ),
            )
            if item.status == "ready" and item.input:
                result.ready.append(item.input)
            elif item.status == "needs_review":
                result.needs_review += 1
            elif item.status == "unavailable":
                result.unavailable += 1
        for key, row in existing.items():
            if key not in seen and row["status"] != "removed":
                result.removed += 1
                self.conn.execute(
                    "UPDATE collection_items SET status = 'removed' WHERE collection_id = ? AND key = ?",
                    (collection_id, key),
                )
        return result

    # ------------------------------------------------------------ review

    def set_match(self, item_id: int, path: Path | None) -> None:
        """Choose the file for an imported entry (``None`` marks it unavailable)."""
        self.conn.execute(
            "UPDATE collection_items SET input = ?, status = ?, score = 1.0, manual = 1 WHERE id = ?",
            (str(path.resolve()) if path else None, "ready" if path else "unavailable", item_id),
        )
