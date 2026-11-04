from pathlib import Path

import pytest
import soundfile as sf

from cover_maker.domain import JobSpec, Stem
from cover_maker.pipeline.runner import JobRunner, RightsNotConfirmed
from cover_maker.sources import youtube

from .conftest import tone

LINK = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def fake_download(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def download_audio(
        video_id: str, target_dir: Path, **_: object
    ) -> tuple[Path, youtube.VideoInfo]:
        calls.append(video_id)
        path = target_dir / f"{video_id}.wav"
        sf.write(str(path), tone(), 44_100, subtype="FLOAT")
        return path, youtube.VideoInfo(
            video_id,
            "Some Artist - Some Song",
            "Channel",
            1.0,
            track="Some Song",
            artist="Some Artist",
        )

    def video_info(video_id: str) -> youtube.VideoInfo:
        calls.append(f"info:{video_id}")
        return youtube.VideoInfo(video_id, "Some Artist - Some Song", "Channel", 1.0)

    monkeypatch.setattr(youtube, "download_audio", download_audio)
    monkeypatch.setattr(youtube, "video_info", video_info)
    return calls


def test_online_input_needs_rights_confirmation(runner: JobRunner, tmp_path: Path) -> None:
    with pytest.raises(RightsNotConfirmed):
        runner.submit(JobSpec(inputs=[LINK], stems=[Stem.VOCALS], output_dir=tmp_path))


def test_video_link_is_downloaded_once(
    runner: JobRunner, tmp_path: Path, fake_download: list[str]
) -> None:
    spec = JobSpec(
        inputs=[LINK], stems=[Stem.VOCALS], output_dir=tmp_path / "out", rights_confirmed=True
    )

    assert runner.run(runner.submit(spec)) == "done"
    assert runner.run(runner.submit(spec)) == "done"

    # Metadata is read before the first download; the second run uses the cache.
    assert fake_download == ["info:dQw4w9WgXcQ", "dQw4w9WgXcQ"]
    assert (tmp_path / "out" / "Some Artist - Some Song - Vocals.wav").exists()
    stored = runner.job_spec(1)
    assert stored.rights_confirmed  # the confirmation is recorded with the job


def test_video_items_get_title_and_artist(
    runner: JobRunner, tmp_path: Path, fake_download: list[str]
) -> None:
    seen: list[dict[str, object]] = []
    runner.events.subscribe(lambda event: seen.append(event))  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    spec = JobSpec(
        inputs=[LINK], stems=[Stem.VOCALS], output_dir=tmp_path / "out", rights_confirmed=True
    )
    job = runner.submit(spec)
    assert runner.items(job)[0]["title"] is None  # links are named when they start

    runner.run(job)

    item = runner.items(job)[0]
    # The music metadata from the download wins over the channel name.
    assert (item["title"], item["artist"]) == ("Some Song", "Some Artist")
    metas = [e for e in seen if e.get("type") == "item.meta"]
    assert [(e["title"], e["artist"]) for e in metas] == [
        ("Some Artist - Some Song", "Channel"),
        ("Some Song", "Some Artist"),
    ]
