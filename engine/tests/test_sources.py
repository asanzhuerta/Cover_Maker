import json
from pathlib import Path

import pytest

from cover_maker.sources.links import InputKind, UnsupportedInput, parse_input
from cover_maker.sources.playlists import PlaylistFormatError, parse_playlist_file

VIDEO = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "link",
    [
        f"https://www.youtube.com/watch?v={VIDEO}",
        f"https://youtu.be/{VIDEO}?si=abc",
        f"https://music.youtube.com/watch?v={VIDEO}&feature=share",
        f"https://www.youtube.com/shorts/{VIDEO}",
        f"https://www.youtube.com/watch?v={VIDEO}&list=PL123",  # video wins by default
        f"https://www.youtube.com/watch?v={VIDEO}&list=RDabc",  # radio mixes are ignored
    ],
)
def test_video_links(link: str) -> None:
    parsed = parse_input(link)

    assert parsed.kind is InputKind.VIDEO
    assert parsed.value == VIDEO
    assert parsed.is_online


def test_playlist_link() -> None:
    parsed = parse_input("https://www.youtube.com/playlist?list=PLabc123")

    assert parsed.kind is InputKind.PLAYLIST
    assert parsed.url == "https://www.youtube.com/playlist?list=PLabc123"


def test_watch_link_as_playlist_on_request() -> None:
    parsed = parse_input(f"https://www.youtube.com/watch?v={VIDEO}&list=PL9", prefer_playlist=True)

    assert parsed.kind is InputKind.PLAYLIST


@pytest.mark.parametrize(
    "text",
    ["https://open.spotify.com/track/abc", "https://example.com/song.mp3", "notes.txt"],
)
def test_unsupported_inputs(text: str) -> None:
    with pytest.raises(UnsupportedInput):
        parse_input(text)


def test_local_file_and_folder(tmp_path: Path) -> None:
    song = tmp_path / "a.flac"
    song.write_bytes(b"")

    assert parse_input(str(song)).kind is InputKind.FILE
    assert parse_input(str(tmp_path)).kind is InputKind.FOLDER


def test_data_export_playlists(tmp_path: Path) -> None:
    path = tmp_path / "Playlist1.json"
    data = {
        "playlists": [
            {
                "name": "Covers",
                "items": [
                    {"track": {"trackName": "Song A", "artistName": "Band", "albumName": "LP"}},
                    {"episode": {"episodeName": "ignored"}},
                ],
            }
        ]
    }
    path.write_text(json.dumps(data), encoding="utf-8")

    [playlist] = parse_playlist_file(path)

    assert playlist.name == "Covers"
    assert [(e.artist, e.title, e.album) for e in playlist.entries] == [("Band", "Song A", "LP")]


def test_data_export_library(tmp_path: Path) -> None:
    path = tmp_path / "YourLibrary.json"
    path.write_text(json.dumps({"tracks": [{"artist": "X", "album": "Y", "track": "Z"}]}), "utf-8")

    [playlist] = parse_playlist_file(path)

    assert playlist.entries[0].title == "Z"


def test_jspf(tmp_path: Path) -> None:
    path = tmp_path / "list.jspf"
    track = {"title": "T", "creator": "C", "duration": 200_000}
    path.write_text(json.dumps({"playlist": {"title": "J", "track": [track]}}), "utf-8")

    [playlist] = parse_playlist_file(path)

    assert playlist.name == "J"
    assert playlist.entries[0].duration_s == 200


def test_csv_with_exported_columns(tmp_path: Path) -> None:
    path = tmp_path / "mix.csv"
    path.write_text(
        "Track Name,Artist Name(s),Album Name,Duration (ms)\nSong,Artist,Album,180000\n", "utf-8"
    )

    [playlist] = parse_playlist_file(path)

    entry = playlist.entries[0]
    assert (entry.title, entry.artist, entry.duration_s) == ("Song", "Artist", 180)


def test_m3u(tmp_path: Path) -> None:
    path = tmp_path / "set.m3u8"
    path.write_text("#EXTM3U\n#EXTINF:215,Artist - Title\nmusic/track.flac\nother.mp3\n", "utf-8")

    [playlist] = parse_playlist_file(path)

    first, second = playlist.entries
    assert (first.artist, first.title, first.duration_s) == ("Artist", "Title", 215)
    assert second.title == "other"


def test_unknown_json(tmp_path: Path) -> None:
    path = tmp_path / "x.json"
    path.write_text("{}", "utf-8")

    with pytest.raises(PlaylistFormatError):
        parse_playlist_file(path)
