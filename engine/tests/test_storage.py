import json
from pathlib import Path

import soundfile as sf

from cover_maker.domain import JobSpec, Stem
from cover_maker.paths import Paths
from cover_maker.pipeline.runner import JobRunner
from cover_maker.sources import catalogs
from cover_maker.store import storage

from .conftest import tone


def run_job(runner: JobRunner, song: Path, out: Path) -> int:
    job = runner.submit(JobSpec(inputs=[str(song)], stems=[Stem.VOCALS], output_dir=out))
    assert runner.run(job) == "done"
    return job


def test_cleanup_keeps_what_the_mixer_needs(
    runner: JobRunner, paths: Paths, tmp_path: Path
) -> None:
    song = tmp_path / "Song.wav"
    sf.write(str(song), tone(), 44_100, subtype="FLOAT")
    job = run_job(runner, song, tmp_path / "out")
    (paths.tmp / "leftover.bin").write_bytes(b"x" * 100)

    before = storage.usage(runner.conn, paths)
    assert before.library_files > 0
    assert before.tmp_bytes == 100

    freed = storage.clean_up(runner.conn, paths)

    after = storage.usage(runner.conn, paths)
    assert freed >= 100
    assert after.reclaimable_files == 0
    assert after.tmp_bytes == 0
    # The mixer still has the mix and the stems of the processed song.
    item = runner.items(job)[0]
    assert runner.mix_sources(item["id"]) is not None


def test_cleanup_after_deleting_history_frees_everything(
    runner: JobRunner, paths: Paths, tmp_path: Path
) -> None:
    song = tmp_path / "Song.wav"
    sf.write(str(song), tone(), 44_100, subtype="FLOAT")
    job = run_job(runner, song, tmp_path / "out")
    runner.conn.execute("DELETE FROM job_items WHERE job_id = ?", (job,))

    storage.clean_up(runner.conn, paths)

    assert storage.usage(runner.conn, paths).library_files == 0
    stale = runner.conn.execute("SELECT COUNT(*) AS n FROM step_cache WHERE step = 'decode'")
    assert stale.fetchone()["n"] == 0
    # A re-run works from scratch.
    run_job(runner, song, tmp_path / "out2")


def test_export_writes_credits_for_cc_audio(runner: JobRunner, tmp_path: Path) -> None:
    song = tmp_path / "Ghost - Reverie.wav"
    sf.write(str(song), tone(), 44_100, subtype="FLOAT")
    credits = catalogs.Credits(
        title="Reverie", artist="Ghost", licence_name="CC BY 3.0",
        licence_url="http://creativecommons.org/licenses/by/3.0/",
        page_url="https://ccmixter.org/files/ghost/1", source="ccmixter",
    )  # fmt: skip
    catalogs.credits_path(song).write_text(json.dumps(credits.__dict__), "utf-8")

    run_job(runner, song, tmp_path / "out")

    assert "Reverie - Ghost" in (tmp_path / "out" / "CREDITS.txt").read_text("utf-8")
