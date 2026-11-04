import io
import json
from pathlib import Path
from typing import Any

import pytest

from cover_maker.sources import catalogs

CC_BY = "http://creativecommons.org/licenses/by/3.0/"
CC_BY_NC_ND = "https://creativecommons.org/licenses/by-nc-nd/4.0/"


def ccmixter_upload(**overrides: Any) -> dict[str, Any]:
    upload: dict[str, Any] = {
        "upload_id": 1,
        "upload_name": "Reverie",
        "user_name": "ghost",
        "user_real_name": "Ghost",
        "license_name": "Attribution (3.0)",
        "license_url": CC_BY,
        "file_page_url": "https://ccmixter.org/files/ghost/1",
        "files": [
            {
                "file_name": "reverie.mp3",
                "download_url": "https://ccmixter.org/content/ghost/reverie.mp3",
                "file_rawsize": 1000,
                "file_format_info": {"media-type": "audio"},
            },
            {
                "file_name": "reverie.zip",
                "download_url": "https://ccmixter.org/content/ghost/reverie.zip",
                "file_format_info": {"media-type": "archive"},
            },
        ],
    }
    upload.update(overrides)
    return upload


def test_licence_restrictions() -> None:
    assert catalogs.licence_restrictions(CC_BY) == []
    assert catalogs.licence_restrictions(CC_BY_NC_ND) == ["NC", "ND"]
    sampling = "http://creativecommons.org/licenses/nc-sampling+/1.0/"
    assert catalogs.licence_restrictions(sampling) == ["NC"]
    assert catalogs.is_open_licence(CC_BY)
    assert catalogs.is_open_licence("https://creativecommons.org/publicdomain/zero/1.0/")
    assert not catalogs.is_open_licence("https://example.com/licence")
    assert not catalogs.is_open_licence(None)
    assert catalogs.licence_name_from_url(CC_BY_NC_ND) == "CC BY-NC-ND 4.0"


def test_ccmixter_keeps_open_audio_only() -> None:
    entries = catalogs.parse_ccmixter(
        [ccmixter_upload(), ccmixter_upload(upload_id=2, license_url="https://example.com/x")]
    )
    assert len(entries) == 1
    entry = entries[0]
    assert (entry.title, entry.artist, entry.source) == ("Reverie", "Ghost", "ccmixter")
    assert [f.name for f in entry.files] == ["reverie.mp3"]


def test_archive_search_and_best_file_per_track() -> None:
    search = {
        "response": {
            "docs": [
                {"identifier": "live-set", "title": "Live set", "creator": ["A", "B"],
                 "licenseurl": CC_BY_NC_ND},
                {"identifier": "closed", "title": "Closed", "licenseurl": "https://example.com"},
            ]
        }
    }  # fmt: skip
    [entry] = catalogs.parse_archive_search(search)
    assert (entry.artist, entry.restrictions) == ("A, B", ["NC", "ND"])

    metadata = {
        "metadata": {"licenseurl": CC_BY},
        "files": [
            {"name": "01 Intro.mp3", "format": "VBR MP3", "size": "10"},
            {"name": "01 Intro.flac", "format": "Flac", "size": "50"},
            {"name": "01 Intro.png", "format": "PNG"},
            {"name": "02 Song.mp3", "format": "VBR MP3", "title": "Song"},
        ],
    }
    files = catalogs.parse_archive_files("live-set", metadata)
    assert [(f.name, f.title) for f in files] == [
        ("01 Intro.flac", "01 Intro"),
        ("02 Song.mp3", "Song"),
    ]
    assert files[0].url == "https://archive.org/download/live-set/01%20Intro.flac"

    with pytest.raises(catalogs.CatalogError):
        catalogs.parse_archive_files("x", {"metadata": {}, "files": []})


def test_downloads_only_from_the_catalogues() -> None:
    assert catalogs.allowed_download("https://archive.org/download/x/a.flac")
    assert catalogs.allowed_download("https://ia800.us.archive.org/1/items/x/a.flac")
    # ccMixter blocks automated downloads: the user downloads on its site.
    assert not catalogs.allowed_download("https://ccmixter.org/content/a.mp3")
    assert not catalogs.allowed_download("http://archive.org/download/x/a.mp3")
    assert not catalogs.allowed_download("https://evil.example/archive.org/a.mp3")
    assert not catalogs.allowed_download("https://notarchive.org/a.mp3")


def credits(licence_url: str = CC_BY) -> catalogs.Credits:
    return catalogs.Credits(
        title="Reverie", artist="Ghost", licence_name="CC BY 3.0", licence_url=licence_url,
        page_url="https://ccmixter.org/files/ghost/1", source="ccmixter",
    )  # fmt: skip


def test_download_writes_file_and_credits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def urlopen(request: Any, timeout: float) -> Any:
        assert "Cover_Maker" in request.headers["User-agent"]
        return io.BytesIO(b"ID3 audio")

    monkeypatch.setattr(catalogs.urllib.request, "urlopen", urlopen)
    file = catalogs.CatalogFile("reverie.mp3", "https://archive.org/download/x/r.mp3", "Reverie")

    path = catalogs.download(file, credits(), tmp_path)

    assert path.name == "Ghost - Reverie.mp3"
    assert path.read_bytes() == b"ID3 audio"
    assert catalogs.read_credits(path) == credits()
    assert json.loads(catalogs.credits_path(path).read_text("utf-8"))["source"] == "ccmixter"


def test_download_refuses_other_hosts(tmp_path: Path) -> None:
    file = catalogs.CatalogFile("x.mp3", "https://example.com/x.mp3", "X")
    with pytest.raises(catalogs.CatalogError):
        catalogs.download(file, credits(), tmp_path)


def test_credits_file_lists_each_track_once(tmp_path: Path) -> None:
    catalogs.write_credits(tmp_path, credits())
    catalogs.write_credits(tmp_path, credits())
    catalogs.write_credits(tmp_path, credits(CC_BY_NC_ND))
    text = (tmp_path / "CREDITS.txt").read_text("utf-8")
    assert text.count("Reverie - Ghost") == 2  # the BY and the BY-NC-ND entries
    assert "no-derivatives" in text


def test_attach_copies_a_downloaded_file_with_credits(tmp_path: Path) -> None:
    downloaded = tmp_path / "Downloads" / "snowflake_-_In_Peace.mp3"
    downloaded.parent.mkdir()
    downloaded.write_bytes(b"ID3")

    path = catalogs.attach(downloaded, credits(), tmp_path / "library")

    assert path.name == "Ghost - Reverie.mp3"
    assert downloaded.exists()  # the original stays where the user saved it
    assert catalogs.read_credits(path) == credits()
    with pytest.raises(catalogs.CatalogError):
        catalogs.attach(downloaded, credits("https://example.com/licence"), tmp_path)
