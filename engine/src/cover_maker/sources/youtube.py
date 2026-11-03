# pyright: basic
# (yt-dlp is untyped; this module only adapts its dictionaries.)
"""Audio download from user-pasted video links, through the unmodified yt-dlp library.

Only the audio track is downloaded, in its original container (no re-encoding);
the engine decodes it like any local file.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Best audio-only stream, avoiding dynamic-range-compressed (DRC) variants.
AUDIO_FORMAT = "bestaudio[format_id!*=drc]/bestaudio/best"

Progress = Callable[[float | None], None]


@dataclass(frozen=True)
class VideoInfo:
    video_id: str
    title: str
    uploader: str | None
    duration_s: float | None


class DownloadError(RuntimeError):
    pass


class DownloadCancelled(RuntimeError):
    pass


def _ydl(options: dict[str, Any]) -> Any:
    import yt_dlp  # pyright: ignore[reportMissingTypeStubs]

    base: dict[str, Any] = {"quiet": True, "no_warnings": True, "noprogress": True}
    return yt_dlp.YoutubeDL({**base, **options})  # type: ignore[arg-type]  # yt-dlp types params as a TypedDict


def playlist_entries(url: str) -> list[VideoInfo]:
    """List the videos of a playlist without downloading anything."""
    try:
        with _ydl({"extract_flat": "in_playlist", "skip_download": True}) as ydl:
            info: dict[str, Any] = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise DownloadError(f"could not read playlist: {exc}") from exc
    entries: list[VideoInfo] = []
    for entry in info.get("entries") or []:
        if not entry or not entry.get("id"):
            continue
        entries.append(
            VideoInfo(
                video_id=str(entry["id"]),
                title=str(entry.get("title") or entry["id"]),
                uploader=entry.get("uploader") or entry.get("channel"),
                duration_s=entry.get("duration"),
            )
        )
    return entries


def download_audio(
    video_id: str,
    target_dir: Path,
    *,
    progress: Progress | None = None,
    cancel: threading.Event | None = None,
) -> tuple[Path, VideoInfo]:
    """Download the best audio stream of one video into ``target_dir``."""
    target_dir.mkdir(parents=True, exist_ok=True)

    def hook(status: dict[str, Any]) -> None:
        if cancel is not None and cancel.is_set():
            import yt_dlp.utils  # pyright: ignore[reportMissingTypeStubs]

            raise yt_dlp.utils.DownloadCancelled()  # pyright: ignore[reportUnknownMemberType]
        if progress and status.get("status") == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            done = status.get("downloaded_bytes")
            progress(done / total if total and done else None)

    options: dict[str, Any] = {
        "format": AUDIO_FORMAT,
        "noplaylist": True,
        "outtmpl": str(target_dir / "%(id)s.%(ext)s"),
        "progress_hooks": [hook],
        "writesubtitles": False,
        "writethumbnail": False,
    }
    try:
        with _ydl(options) as ydl:
            info: dict[str, Any] = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}")
            path = Path(ydl.prepare_filename(info))
    except Exception as exc:
        if type(exc).__name__ == "DownloadCancelled" or (cancel is not None and cancel.is_set()):
            raise DownloadCancelled("download cancelled") from exc
        raise DownloadError(f"could not download {video_id}: {exc}") from exc
    if not path.exists():
        candidates = sorted(target_dir.glob(f"{video_id}.*"))
        if not candidates:
            raise DownloadError(f"yt-dlp finished but no audio file was found for {video_id}")
        path = candidates[0]
    meta = VideoInfo(
        video_id=video_id,
        title=str(info.get("title") or video_id),
        uploader=info.get("uploader") or info.get("channel"),
        duration_s=info.get("duration"),
    )
    return path, meta
