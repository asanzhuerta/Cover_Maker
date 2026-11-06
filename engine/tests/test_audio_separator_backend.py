"""The audio-separator backend reuses a loaded model across jobs."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from cover_maker.domain import Stem
from cover_maker.separation.backends.audio_separator import AudioSeparatorBackend
from cover_maker.separation.types import SeparationRequest


class FakeSeparator:
    """Writes stems where the loaded model says, like audio-separator does."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = str(output_dir)
        self.model_instance = SimpleNamespace(output_dir=str(output_dir))

    def separate(self, _input: str) -> list[str]:
        out = Path(self.model_instance.output_dir)
        names = ["song_(vocals)_M.wav", "song_(other)_M.wav"]
        for name in names:
            (out / name).write_bytes(b"RIFF")
        return names


def request(tmp_path: Path, job: str) -> SeparationRequest:
    return SeparationRequest(
        model_filename="m.ckpt",
        model_dir=tmp_path / "models",
        input_path=tmp_path / "song.wav",
        output_dir=tmp_path / job,
        stems={"vocals": Stem.VOCALS, "other": Stem.OTHER},
    )


def test_second_job_with_the_same_model_finds_its_stems(tmp_path: Path) -> None:
    backend = AudioSeparatorBackend()
    first = request(tmp_path, "job1")
    key: tuple[Any, ...] = (
        first.model_filename,
        first.precision,
        first.chunk_s,
        str(first.model_dir),
    )
    (first.output_dir / "_raw").mkdir(parents=True)
    backend._key, backend._separator = key, FakeSeparator(first.output_dir / "_raw")

    assert backend.separate(first).outputs[Stem.VOCALS].exists()

    second = request(tmp_path, "job2")
    result = backend.separate(second)

    assert result.outputs[Stem.VOCALS] == second.output_dir / "vocals.wav"
    assert result.outputs[Stem.VOCALS].exists()
    assert result.outputs[Stem.OTHER].exists()
