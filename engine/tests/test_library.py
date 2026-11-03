from pathlib import Path

import pytest
import soundfile as sf

from cover_maker.library.collections import Library
from cover_maker.library.matching import LocalTrack, best_match, normalise, read_track
from cover_maker.sources.playlists import PlaylistEntry
from cover_maker.sources.youtube import VideoInfo
from cover_maker.store.db import connect

from .conftest import tone


def write_song(folder: Path, name: str, seconds: float = 1.0) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    sf.write(str(path), tone(seconds), 44_100, subtype="PCM_16")
    return path


def test_normalise_drops_noise() -> None:
    assert normalise("Song (Official Video) [HD]") == "song"
    assert normalise("Café feat. Someone") == "cafe"


def test_best_match_prefers_title_and_artist() -> None:
    entry = PlaylistEntry("Sun Killer", "Spiritbox", duration_s=200)
    tracks = [
        LocalTrack(Path("a.flac"), "Sun Killer", "Spiritbox", "", 201),
        LocalTrack(Path("b.flac"), "Sun Killer (Live)", "Tribute Band", "", 260),
    ]

    match = best_match(entry, tracks)

    assert match.track is not None and match.track.path == Path("a.flac")
    assert match.status == "ready"


def test_unrelated_track_is_unavailable() -> None:
    match = best_match(
        PlaylistEntry("Totally Different", "Nobody"),
        [LocalTrack(Path("x"), "Song", "Band", "", None)],
    )

    assert match.status == "unavailable"


def test_filename_fallback(tmp_path: Path) -> None:
    path = write_song(tmp_path, "07 Band - Great Song.wav")

    track = read_track(path)

    assert (track.artist, track.title) == ("Band", "Great Song")


@pytest.fixture
def library(tmp_path: Path) -> Library:
    return Library(connect(tmp_path / "db.sqlite3"))


def test_folder_sync_is_incremental(library: Library, tmp_path: Path) -> None:
    folder = tmp_path / "music"
    write_song(folder, "Band - One.wav")
    collection = library.add_folder(folder)

    first = library.sync(collection)
    write_song(folder, "Band - Two.wav")
    second = library.sync(collection)
    (folder / "Band - One.wav").unlink()
    third = library.sync(collection)

    assert (first.added, len(first.ready)) == (1, 1)
    assert (second.added, second.unchanged) == (1, 1)
    assert (third.removed, len(third.ready)) == (1, 1)
    assert library.add_folder(folder) == collection  # same folder, same collection


def test_video_playlist_sync(tmp_path: Path) -> None:
    entries = [VideoInfo("aaaaaaaaaaa", "First", "Channel", 100.0)]
    library = Library(connect(tmp_path / "db.sqlite3"), playlist_loader=lambda url: list(entries))
    collection = library.add_video_playlist("PL1")

    first = library.sync(collection)
    entries.append(VideoInfo("bbbbbbbbbbb", "Second", "Channel", 120.0))
    second = library.sync(collection)

    assert first.ready == ["https://www.youtube.com/watch?v=aaaaaaaaaaa"]
    assert (second.added, second.unchanged, len(second.ready)) == (1, 1, 2)


def test_imported_playlist_matching_and_review(library: Library, tmp_path: Path) -> None:
    music = tmp_path / "music"
    write_song(music, "Spiritbox - Sun Killer.wav")
    playlist = tmp_path / "list.m3u"
    playlist.write_text(
        "#EXTINF:1,Spiritbox - Sun Killer\nx\n#EXTINF:1,Nobody - Missing\ny\n", "utf-8"
    )

    [collection] = library.import_playlist_file(playlist, [music])
    result = library.sync(collection)

    assert len(result.ready) == 1
    assert result.unavailable == 1
    missing = next(row for row in library.items(collection) if row["status"] == "unavailable")
    chosen = write_song(music, "Something Else.wav")
    library.set_match(missing["id"], chosen)

    resynced = library.sync(collection)

    assert len(resynced.ready) == 2  # the manual correction survives re-sync


def test_tags_are_read_from_the_file(tmp_path: Path) -> None:
    path = tmp_path / "01 - untitled.flac"
    with sf.SoundFile(path, "w", samplerate=44100, channels=2, format="FLAC") as f:
        f.title = "Night Drive"
        f.artist = "The Testers"
        f.album = "Demo Tapes"
        f.write(tone(1.0))
    track = read_track(path)
    assert (track.title, track.artist, track.album) == ("Night Drive", "The Testers", "Demo Tapes")
    assert track.duration_s == pytest.approx(1.0, abs=0.05)
