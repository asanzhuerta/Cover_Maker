"""Preset tuning from measured runs (M10)."""

from pathlib import Path

import pytest

from cover_maker.domain import JobSpec, Preset, Stem
from cover_maker.paths import Paths
from cover_maker.pipeline.runner import JobRunner, preset_models, resolve_preset
from cover_maker.separation.backends.fake import FakeBackend
from cover_maker.separation.catalog import Catalog
from cover_maker.separation.service import GPU_LADDER, InProcessService
from cover_maker.separation.tuning import OOM_STREAK, SLOW_RTF, Tuning
from cover_maker.store.db import connect


@pytest.fixture
def tuning(paths: Paths) -> Tuning:
    return Tuning(connect(paths.db))


def job(song: Path, tmp_path: Path) -> JobSpec:
    return JobSpec.model_validate(
        {"inputs": [song], "stems": [Stem.VOCALS], "output_dir": tmp_path / "out"}
    )


def test_runs_are_recorded_and_known_ooms_skipped(paths: Paths, song: Path, tmp_path: Path) -> None:
    backend = FakeBackend(fail_oom_above_chunk=5.0)
    runner = JobRunner(paths, connect(paths.db), Catalog.load(), InProcessService(backend))
    for model in runner.catalog.models.values():
        runner.installs.record(model, None)

    for _ in range(OOM_STREAK):
        # A new output folder each time so the separation itself is not cached.
        runner.conn.execute("DELETE FROM step_cache")
        assert runner.run(runner.submit(job(song, tmp_path))) == "done"
    first = [c.chunk_s for c in backend.calls]
    assert first == [None, 8.0, 4.0] * OOM_STREAK

    rows = runner.conn.execute("SELECT * FROM separation_runs ORDER BY id").fetchall()
    assert [(r["chunk_s"], r["oom"]) for r in rows[:3]] == [(None, 1), (8.0, 1), (4.0, 0)]
    assert rows[2]["audio_s"] > 0 and rows[2]["wall_s"] is not None

    backend.calls.clear()
    runner.conn.execute("DELETE FROM step_cache")
    assert runner.run(runner.submit(job(song, tmp_path))) == "done"
    assert [c.chunk_s for c in backend.calls] == [4.0]


def test_a_success_resets_the_streak(tuning: Tuning) -> None:
    for _ in range(OOM_STREAK):
        tuning.record("m", "gpu", "fp16", None, 60, None, True)
    assert tuning.first_gpu_rung("m", GPU_LADDER) == 1
    tuning.record("m", "gpu", "fp16", None, 60, 30, False)
    assert tuning.first_gpu_rung("m", GPU_LADDER) == 0


def test_the_smallest_gpu_setting_is_always_tried(tuning: Tuning) -> None:
    for precision, chunk in GPU_LADDER:
        for _ in range(OOM_STREAK):
            tuning.record("m", "gpu", precision, chunk, 60, None, True)
    assert tuning.first_gpu_rung("m", GPU_LADDER) == len(GPU_LADDER) - 1


def test_auto_preset_follows_measured_speed(tuning: Tuning) -> None:
    models = preset_models()
    assert resolve_preset("auto", True, tuning) is Preset.BALANCED
    assert resolve_preset("auto", False, tuning) is Preset.FAST
    for model in models[Preset.BALANCED]:
        tuning.record(model, "gpu", "fp16", 4.0, 100, 100 * (SLOW_RTF + 1), False)
    assert resolve_preset("auto", True, tuning) is Preset.FAST
    assert resolve_preset("max", True, tuning) is Preset.MAX
    assert tuning.summary(models)["balanced"] == pytest.approx(SLOW_RTF + 1)


def test_fast_gpu_keeps_balanced(tuning: Tuning) -> None:
    for model in preset_models()[Preset.BALANCED]:
        tuning.record(model, "gpu", "fp16", None, 100, 20, False)
    assert resolve_preset("auto", True, tuning) is Preset.BALANCED
