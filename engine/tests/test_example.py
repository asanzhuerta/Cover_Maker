"""The example song offered on first run."""

from __future__ import annotations

from pathlib import Path

import pytest
import soundfile as sf

from cover_maker.pipeline.runner import JobRunner
from cover_maker.sources import catalogs, example

from .test_storage import run_job


def test_example_clip_is_short_small_and_cc0_or_cc_by() -> None:
    clip = example.load()

    assert clip.credits.licence_url in example.ALLOWED_LICENCES
    assert catalogs.licence_restrictions(clip.credits.licence_url) == []
    assert clip.path.is_file()
    assert 0 < clip.size_bytes <= example.MAX_BYTES
    info = sf.info(str(clip.path))
    assert info.duration <= example.MAX_SECONDS
    assert info.duration == pytest.approx(clip.duration_s, abs=0.5)
    # Decoded without ffmpeg: 44.1 kHz stereo, like the canonical mix.
    assert (info.samplerate, info.channels) == (44_100, 2)


def test_example_is_credited_in_the_third_party_notices() -> None:
    clip = example.load()
    notices = (Path(__file__).resolve().parents[2] / "THIRD_PARTY_NOTICES.md").read_text("utf-8")

    for value in (clip.file, clip.credits.artist, clip.credits.page_url, clip.credits.licence_url):
        assert value in notices


def test_adding_the_example_copies_it_with_its_credits(tmp_path: Path) -> None:
    path = example.add(tmp_path / "library")

    assert path.parent == tmp_path / "library" / "example"
    assert path.read_bytes() == example.load().path.read_bytes()
    assert catalogs.read_credits(path) == example.load().credits
    assert example.add(tmp_path / "library") == path  # adding it again reuses the copy


def test_credits_mention_the_changes_made() -> None:
    credits = example.load().credits

    assert credits.changes
    assert f"Changes: {credits.changes}" in credits.text()


def test_stems_of_the_example_come_with_credits(runner: JobRunner, tmp_path: Path) -> None:
    song = example.add(tmp_path / "library")

    run_job(runner, song, tmp_path / "out")

    text = (tmp_path / "out" / "CREDITS.txt").read_text("utf-8")
    assert "Josh Woodward" in text
    assert example.load().credits.licence_url in text
