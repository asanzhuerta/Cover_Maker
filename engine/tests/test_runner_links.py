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
        return path, youtube.VideoInfo(video_id, "Some Artist - Some Song", "Channel", 1.0)

    monkeypatch.setattr(youtube, "download_audio", download_audio)
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

    assert fake_download == ["dQw4w9WgXcQ"]
    assert (tmp_path / "out" / "Some Artist - Some Song - Vocals.wav").exists()
    stored = runner.job_spec(1)
    assert stored.rights_confirmed  # the confirmation is recorded with the job
