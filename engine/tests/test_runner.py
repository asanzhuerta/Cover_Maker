import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from cover_maker.audio import io
from cover_maker.domain import ALL_STEMS, JobSpec, Mode, Preset, ResidualMode, Stem
from cover_maker.paths import Paths
from cover_maker.pipeline.runner import JobRunner, ModelNotInstalled
from cover_maker.separation.backends.fake import WEIGHTS, FakeBackend
from cover_maker.separation.catalog import Catalog
from cover_maker.separation.service import InProcessService, NeedsCpuFallback
from cover_maker.store.db import MIGRATIONS, connect, schema_version

from .conftest import tone


def spec(song: Path, tmp_path: Path, **kwargs: object) -> JobSpec:
    return JobSpec.model_validate(
        {"inputs": [song], "stems": [Stem.VOCALS], "output_dir": tmp_path / "out", **kwargs}
    )


def test_extract_exports_selected_stem(runner: JobRunner, song: Path, tmp_path: Path) -> None:
    job = runner.submit(spec(song, tmp_path, stems=[Stem.VOCALS, Stem.GUITAR]))

    assert runner.run(job) == "done"

    out = tmp_path / "out"
    assert sorted(p.name for p in out.iterdir()) == ["My Song - Guitar.wav", "My Song - Vocals.wav"]
    vocals = io.read(out / "My Song - Vocals.wav")
    mix = io.read(song)
    np.testing.assert_allclose(vocals, mix * WEIGHTS[Stem.VOCALS], atol=1e-4)


def test_without_vocals_keep_residual(runner: JobRunner, song: Path, tmp_path: Path) -> None:
    job = runner.submit(spec(song, tmp_path, mode=Mode.WITHOUT))

    runner.run(job)

    result = io.read(tmp_path / "out" / "My Song - without vocals.wav")
    np.testing.assert_allclose(result, io.read(song) * (1 - WEIGHTS[Stem.VOCALS]), atol=1e-4)


def test_without_drop_residual_needs_all_stems(
    runner: JobRunner, song: Path, tmp_path: Path, backend: FakeBackend
) -> None:
    job = runner.submit(
        spec(song, tmp_path, mode=Mode.WITHOUT, residual=ResidualMode.DROP, stems=[Stem.DRUMS])
    )

    runner.run(job)

    assert (tmp_path / "out" / "My Song - without drums.wav").exists()
    assert set(backend.calls[0].stems.values()) == set(ALL_STEMS)


def test_both_exports_stems_and_song_without_them(
    runner: JobRunner, song: Path, tmp_path: Path
) -> None:
    job = runner.submit(spec(song, tmp_path, mode=Mode.BOTH, stems=[Stem.VOCALS, Stem.GUITAR]))

    assert runner.run(job) == "done"

    out = tmp_path / "out"
    assert sorted(p.name for p in out.iterdir()) == [
        "My Song - Guitar.wav",
        "My Song - Vocals.wav",
        "My Song - without vocals, guitar.wav",
    ]
    outputs = runner.items(job)[0]["outputs_json"]
    assert sorted(json.loads(outputs)) == ["Guitar", "Vocals", "without vocals, guitar"]
    mix = io.read(song)
    removed = WEIGHTS[Stem.VOCALS] + WEIGHTS[Stem.GUITAR]
    np.testing.assert_allclose(
        io.read(out / "My Song - without vocals, guitar.wav"), mix * (1 - removed), atol=1e-4
    )


def test_both_with_drop_residual_needs_all_stems(
    runner: JobRunner, song: Path, tmp_path: Path, backend: FakeBackend
) -> None:
    job = runner.submit(
        spec(song, tmp_path, mode=Mode.BOTH, residual=ResidualMode.DROP, stems=[Stem.DRUMS])
    )

    runner.run(job)

    out = tmp_path / "out"
    assert (out / "My Song - Drums.wav").exists()
    assert (out / "My Song - without drums.wav").exists()
    assert set(backend.calls[0].stems.values()) == set(ALL_STEMS)


def test_second_run_does_no_separation(
    runner: JobRunner, song: Path, tmp_path: Path, backend: FakeBackend
) -> None:
    runner.run(runner.submit(spec(song, tmp_path)))
    calls = len(backend.calls)

    runner.run(runner.submit(spec(song, tmp_path)))

    assert len(backend.calls) == calls


def test_new_stem_reuses_previous_separation(
    runner: JobRunner, song: Path, tmp_path: Path, backend: FakeBackend
) -> None:
    runner.run(runner.submit(spec(song, tmp_path, stems=[Stem.VOCALS])))

    runner.run(runner.submit(spec(song, tmp_path, stems=[Stem.BASS])))

    assert len(backend.calls) == 1  # SW already produced bass in the first pass


LEAD, BACKING = Stem.VOCALS_LEAD, Stem.VOCALS_BACKING
KARAOKE_FILE = "bs_roformer_karaoke_anvuew.ckpt"


def test_lead_and_backing_split_the_vocals(
    runner: JobRunner, song: Path, tmp_path: Path, backend: FakeBackend
) -> None:
    job = runner.submit(spec(song, tmp_path, stems=[LEAD, BACKING]))

    assert runner.run(job) == "done"

    out = tmp_path / "out"
    assert sorted(p.name for p in out.iterdir()) == [
        "My Song - Backing vocals.wav",
        "My Song - Lead vocals.wav",
    ]
    vocals = io.read(song) * WEIGHTS[Stem.VOCALS]
    np.testing.assert_allclose(
        io.read(out / "My Song - Lead vocals.wav"), vocals * WEIGHTS[LEAD], atol=1e-4
    )
    np.testing.assert_allclose(
        io.read(out / "My Song - Backing vocals.wav"), vocals * WEIGHTS[BACKING], atol=1e-4
    )
    assert [call.model_filename for call in backend.calls] == ["BS-Roformer-SW.ckpt", KARAOKE_FILE]
    preview = runner.preview(runner.items(job)[0]["id"])
    assert preview is not None
    assert {"vocals", "vocals.lead", "vocals.backing"} <= preview["stems"].keys()


@pytest.mark.parametrize("residual", list(ResidualMode))
def test_without_lead_keeps_the_backing(
    runner: JobRunner, song: Path, tmp_path: Path, residual: ResidualMode
) -> None:
    job = runner.submit(spec(song, tmp_path, mode=Mode.WITHOUT, stems=[LEAD], residual=residual))

    assert runner.run(job) == "done"

    result = io.read(tmp_path / "out" / "My Song - without lead vocals.wav")
    lead = WEIGHTS[Stem.VOCALS] * WEIGHTS[LEAD]
    np.testing.assert_allclose(result, io.read(song) * (1 - lead), atol=1e-4)


def test_lead_reuses_the_cached_vocals(
    runner: JobRunner, song: Path, tmp_path: Path, backend: FakeBackend
) -> None:
    runner.run(runner.submit(spec(song, tmp_path, stems=[Stem.VOCALS])))
    runner.run(runner.submit(spec(song, tmp_path, stems=[LEAD])))
    runner.run(runner.submit(spec(song, tmp_path, stems=[BACKING], mode=Mode.WITHOUT)))

    # SW once for the vocals, the karaoke model once on them; the rest is cached.
    assert [call.model_filename for call in backend.calls] == ["BS-Roformer-SW.ckpt", KARAOKE_FILE]
    assert backend.calls[1].stems == {"Vocals": LEAD, "Instrumental": BACKING}


def test_max_preset_runs_ensemble(
    runner: JobRunner, song: Path, tmp_path: Path, backend: FakeBackend
) -> None:
    runner.run(runner.submit(spec(song, tmp_path, preset=Preset.MAX, stems=[Stem.GUITAR])))

    assert [call.model_filename for call in backend.calls] == [
        "BS-Roformer-SW.ckpt",
        "bs_roformer_vocals_resurrection_unwa.ckpt",
        "BS-Roformer-SW.ckpt",
    ]
    assert (tmp_path / "out" / "My Song - Guitar.wav").exists()


def test_missing_model_is_reported(paths: Paths, song: Path, tmp_path: Path) -> None:
    runner = JobRunner(paths, connect(paths.db), Catalog.load(), InProcessService(FakeBackend()))

    with pytest.raises(ModelNotInstalled):
        runner.run(runner.submit(spec(song, tmp_path)))


def test_missing_input_fails_item_not_job(runner: JobRunner, song: Path, tmp_path: Path) -> None:
    job = runner.submit(
        JobSpec(
            inputs=[str(tmp_path / "nope.wav"), str(song)],
            stems=[Stem.VOCALS],
            output_dir=tmp_path / "out",
        )
    )

    assert runner.run(job) == "failed"

    statuses = [row["status"] for row in runner.items(job)]
    assert statuses == ["failed", "done"]


def test_recover_resets_interrupted_items(runner: JobRunner, song: Path, tmp_path: Path) -> None:
    job = runner.submit(spec(song, tmp_path))
    runner.conn.execute("UPDATE job_items SET status = 'running', current_step = 'decode'")

    assert runner.recover() == 1
    assert runner.run(job) == "done"


def test_oom_steps_down_chunk(paths: Paths, song: Path, tmp_path: Path) -> None:
    backend = FakeBackend(fail_oom_above_chunk=5.0)
    conn = connect(paths.db)
    runner = JobRunner(paths, conn, Catalog.load(), InProcessService(backend))
    for model in runner.catalog.models.values():
        runner.installs.record(model, None)

    assert runner.run(runner.submit(spec(song, tmp_path))) == "done"

    assert [call.chunk_s for call in backend.calls] == [None, 8.0, 4.0]


def test_oom_everywhere_asks_for_cpu(paths: Paths, song: Path, tmp_path: Path) -> None:
    backend = FakeBackend(fail_oom_above_chunk=1.0)
    runner = JobRunner(paths, connect(paths.db), Catalog.load(), InProcessService(backend))
    for model in runner.catalog.models.values():
        runner.installs.record(model, None)

    job = runner.submit(spec(song, tmp_path))
    assert runner.run(job) == "failed"
    assert "Allow CPU mode" in (runner.items(job)[0]["error"] or "")
    assert issubclass(NeedsCpuFallback, Exception)


def test_cpu_fallback_when_allowed(paths: Paths, song: Path, tmp_path: Path) -> None:
    backend = FakeBackend(fail_oom_above_chunk=1.0)
    runner = JobRunner(paths, connect(paths.db), Catalog.load(), InProcessService(backend))
    for model in runner.catalog.models.values():
        runner.installs.record(model, None)

    assert runner.run(runner.submit(spec(song, tmp_path, allow_cpu_fallback=True))) == "done"
    assert backend.calls[-1].device == "cpu"


def test_schema_is_migrated(paths: Paths) -> None:
    assert schema_version(connect(paths.db)) == len(MIGRATIONS)


def test_file_items_are_named_from_tags_or_file_name(runner: JobRunner, tmp_path: Path) -> None:
    tagged = tmp_path / "track01.flac"
    with sf.SoundFile(tagged, "w", samplerate=44_100, channels=2, format="FLAC") as f:
        f.title = "Night Drive"
        f.artist = "The Testers"
        f.write(tone(0.5))
    named = tmp_path / "Band - Great Song.wav"
    sf.write(str(named), tone(0.5), 44_100)

    job = runner.submit(
        JobSpec(inputs=[str(tagged), str(named)], stems=[Stem.VOCALS], output_dir=tmp_path)
    )

    items = runner.items(job)
    assert [(i["title"], i["artist"]) for i in items] == [
        ("Night Drive", "The Testers"),
        ("Great Song", "Band"),
    ]
