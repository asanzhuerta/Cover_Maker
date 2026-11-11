"""Job runner: turns a :class:`JobSpec` into exported stems, step by step.

Steps per input: hash → decode → analyse → separation nodes → render/export. Every step
has a cache key stored in ``step_cache``; finished work is reused, so running
the same job again does no separation at all. Job and item states live in
SQLite, so an interrupted job resumes on the next start.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..audio import analysis, io, mixer, practice
from ..domain import (
    ALL_STEMS,
    JobSpec,
    Mode,
    Preset,
    ResidualMode,
    Stem,
    split_for,
    stem_label,
)
from ..library.matching import read_track
from ..paths import Paths
from ..separation import recipes
from ..separation.catalog import Catalog, Installs, ModelSpec
from ..separation.recipes import MINUS, STEM, Node, Recipe, Ref
from ..separation.service import GPU_LADDER, SeparationService, with_ladder
from ..separation.tuning import Tuning
from ..separation.types import Cancelled, SeparationRequest
from ..sources import catalogs, youtube
from ..sources.links import InputKind, parse_input
from ..store import analyses
from ..store.assets import AssetStore, sha256_file
from .events import EventBus

CACHE_VERSION = "1"
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


# Columns of `job_items` that `JobRunner._set_item` may update.
_ITEM_COLUMNS = frozenset(
    {"status", "error", "current_step", "title", "artist", "outputs_json", "preview_json"}
)


class JobCancelled(RuntimeError):
    pass


class RightsNotConfirmed(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "This job downloads online content. Confirm that you own it or are allowed to "
            "use it before processing (see DISCLAIMER.md)."
        )


class ModelNotInstalled(RuntimeError):
    def __init__(self, model: ModelSpec) -> None:
        super().__init__(
            f"Model '{model.id}' ({model.name}) is not installed. "
            f"Run: cover-maker models install {model.id}"
        )
        self.model = model


@dataclass(frozen=True)
class MixSources:
    title: str
    mix: Path
    stems: dict[Stem, Path]
    spec: JobSpec


@dataclass(frozen=True)
class BeatGrid:
    beats: list[float]
    downbeats: list[float]


def _free_path(folder: Path, base: str, suffix: str) -> Path:
    target = folder / f"{base}{suffix}"
    counter = 2
    while target.exists():
        target = folder / f"{base} ({counter}){suffix}"
        counter += 1
    return target


def render_custom_mix(
    sources: MixSources,
    gains: dict[Stem, float],
    residual: ResidualMode,
    fmt: str | None = None,
    pans: dict[Stem, float] | None = None,
    *,
    practice_settings: practice.Practice | None = None,
    click_gain: float = 0.0,
    grid: BeatGrid | None = None,
    with_stems: bool = False,
) -> tuple[Path, mixer.RenderResult]:
    """Render mixer settings to a new file in the job's output folder (never overwrites).

    With practice settings, the mix (and each stem when ``with_stems``) is rendered at
    the chosen tempo and pitch with the same chain as the preview (ADR-010). A click
    stem from the beat grid is mixed in at ``click_gain`` and exported with the stems.
    """
    fmt = fmt or sources.spec.output_format.value
    settings = practice_settings or practice.Practice()
    mix = io.read(sources.mix)
    stems = {stem: io.read(path) for stem, path in sources.stems.items()}
    mixed = mixer.mix_gains(mix, stems, gains, residual, pans)
    click = practice.click_stereo(grid.beats, grid.downbeats, len(mixed)) if grid else None
    if click is not None and click_gain > 0:
        mixed = (mixed + click * np.float32(click_gain)).astype(np.float32)
    result = mixer.protect_peaks(practice.apply(mixed, settings))
    tag = settings.suffix()
    label = f" ({tag})" if tag else ""
    folder = sources.spec.output_dir
    target = _free_path(folder, f"{sources.title} - custom mix{label}", f".{fmt}")
    io.write(result.audio, target, fmt)
    if with_stems:
        stem_dir = _free_path(folder, f"{sources.title} - stems{label}", "")
        stem_dir.mkdir(parents=True)
        tracks: dict[str, io.Audio] = {
            stem_label(stem).lower(): audio for stem, audio in stems.items()
        }
        if click is not None:
            tracks["click"] = click
        for name, audio in tracks.items():
            shaped = mixer.protect_peaks(practice.apply(audio, settings)).audio
            io.write(shaped, stem_dir / f"{sources.title} - {name}.{fmt}", fmt)
    return target, result


def file_meta(raw_input: str) -> tuple[str | None, str | None]:
    """Title and artist of a local file from its tags or its name; links get theirs later."""
    if raw_input.lower().startswith(("http://", "https://")):
        return None, None
    track = read_track(Path(raw_input))
    return track.title or None, track.artist or None


def safe_title(name: str) -> str:
    cleaned = _UNSAFE.sub(" ", name).strip(" .")
    return re.sub(r"\s+", " ", cleaned)[:120] or "track"


def stems_to_separate(spec: JobSpec) -> set[Stem]:
    """Stems the models must produce for this job."""
    selected = set(spec.stems)
    if spec.mode is not Mode.EXTRACT and spec.residual is ResidualMode.DROP:
        # The remaining stems are summed, split as finely as the selection.
        return split_for(selected) | selected
    return selected  # extract, or without+keep (mix minus the selected stems)


class JobRunner:
    def __init__(
        self,
        paths: Paths,
        conn: sqlite3.Connection,
        catalog: Catalog,
        service: SeparationService,
        events: EventBus | None = None,
        *,
        use_gpu: bool = True,
    ) -> None:
        self.paths = paths
        self.conn = conn
        self.catalog = catalog
        self.service = service
        self.events = events or EventBus()
        self.use_gpu = use_gpu
        self.assets = AssetStore(paths.assets, conn)
        self.installs = Installs(conn)
        self.tuning = Tuning(conn)
        self._cancel = threading.Event()
        self._pause = threading.Event()

    # ------------------------------------------------------------ job state

    def submit(self, spec: JobSpec) -> int:
        online = [raw for raw in spec.inputs if raw.lower().startswith(("http://", "https://"))]
        if online and not spec.rights_confirmed:
            raise RightsNotConfirmed()
        cursor = self.conn.execute(
            "INSERT INTO jobs (spec_json) VALUES (?)", (spec.model_dump_json(),)
        )
        job_id = int(cursor.lastrowid or 0)
        for ordinal, path in enumerate(spec.inputs):
            title, artist = file_meta(str(path))
            self.conn.execute(
                "INSERT INTO job_items (job_id, ordinal, input_path, title, artist) "
                "VALUES (?, ?, ?, ?, ?)",
                (job_id, ordinal, str(path), title, artist),
            )
        self.events.emit("job.submitted", job=job_id, items=len(spec.inputs))
        return job_id

    def retry(self, job_id: int) -> int:
        """Make failed and cancelled items pending again. Returns how many."""
        cursor = self.conn.execute(
            "UPDATE job_items SET status = 'pending', error = NULL "
            "WHERE job_id = ? AND status IN ('failed', 'cancelled')",
            (job_id,),
        )
        self._set_job(job_id, "pending")
        return cursor.rowcount

    def jobs(self, limit: int = 100) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT j.id, j.status, j.error, j.created_at, j.updated_at, j.spec_json, "
            "COUNT(i.id) AS items, SUM(i.status = 'done') AS done, SUM(i.status = 'failed') AS failed "
            "FROM jobs j LEFT JOIN job_items i ON i.job_id = j.id "
            "GROUP BY j.id ORDER BY j.id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def recover(self) -> int:
        """Reset work interrupted by a crash so it runs again. Returns items reset."""
        cursor = self.conn.execute(
            "UPDATE job_items SET status = 'pending', current_step = NULL WHERE status = 'running'"
        )
        self.conn.execute("UPDATE jobs SET status = 'pending' WHERE status = 'running'")
        return cursor.rowcount

    def pause(self) -> None:
        """Stop after the current item; the remaining items stay pending."""
        self._pause.set()

    def cancel(self) -> None:
        self._cancel.set()
        self.service.cancel()

    def _set_item(self, item_id: int, **fields: Any) -> None:
        unknown = fields.keys() - _ITEM_COLUMNS
        if unknown:
            raise ValueError(f"not a job item column: {', '.join(sorted(unknown))}")
        # Column names come from the allowlist above; every value is a bound parameter.
        assignments = ", ".join(f"{name} = ?" for name in fields)
        self.conn.execute(  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            f"UPDATE job_items SET {assignments}, updated_at = datetime('now') WHERE id = ?",
            (*fields.values(), item_id),
        )

    def _set_job(self, job_id: int, status: str, error: str | None = None) -> None:
        self.conn.execute(
            "UPDATE jobs SET status = ?, error = ?, updated_at = datetime('now') WHERE id = ?",
            (status, error, job_id),
        )

    def job_spec(self, job_id: int) -> JobSpec:
        row = self.conn.execute("SELECT spec_json FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"job {job_id} does not exist")
        return JobSpec.model_validate_json(row["spec_json"])

    def items(self, job_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM job_items WHERE job_id = ? ORDER BY ordinal", (job_id,)
        ).fetchall()

    # ------------------------------------------------------------ execution

    def run(self, job_id: int) -> str:
        """Run every pending item of a job. Returns the final job status."""
        self._cancel.clear()
        self._pause.clear()
        spec = self.job_spec(job_id)
        recipe = recipes.load(spec.preset)
        wanted = stems_to_separate(spec)
        for model_id in recipe.models(wanted):
            model = self.catalog.get(model_id)
            if not self.installs.is_installed(model):
                raise ModelNotInstalled(model)

        self._set_job(job_id, "running")
        failures = 0
        for item in self.items(job_id):
            if item["status"] == "done":
                continue
            if self._cancel.is_set() or self._pause.is_set():
                break
            try:
                self._set_item(item["id"], status="running", error=None)
                outputs = self._run_item(
                    job_id, item["id"], item["input_path"], spec, recipe, wanted
                )
                self._set_item(
                    item["id"], status="done", current_step=None, outputs_json=json.dumps(outputs)
                )
                self.events.emit("item.done", job=job_id, item=item["id"], outputs=outputs)
            except (Cancelled, JobCancelled):
                self._set_item(item["id"], status="cancelled", current_step=None)
                self.events.emit("item.cancelled", job=job_id, item=item["id"])
                break
            except Exception as exc:
                failures += 1
                self._set_item(item["id"], status="failed", current_step=None, error=str(exc))
                self.events.emit("item.failed", job=job_id, item=item["id"], error=str(exc))

        if self._cancel.is_set():
            status = "cancelled"
        elif self._pause.is_set():
            status = "paused"
        elif failures:
            status = "failed"
        else:
            status = "done"
        self._set_job(job_id, status)
        self.events.emit("job.finished", job=job_id, status=status)
        return status

    def _set_meta(self, job_id: int, item_id: int, title: str, artist: str | None) -> None:
        """Record what an item is, for the queue (tags or video metadata)."""
        self._set_item(item_id, title=title, artist=artist)
        self.events.emit("item.meta", job=job_id, item=item_id, title=title, artist=artist)

    def _step(self, job_id: int, item_id: int, step: str) -> None:
        if self._cancel.is_set():
            raise JobCancelled()
        self._set_item(item_id, current_step=step)
        self.events.emit("item.step", job=job_id, item=item_id, step=step)

    # ------------------------------------------------------------ cache

    def _remembered(self, step: str, key: str) -> Any | None:
        """A cached plain value (not asset references), or None."""
        row = self.conn.execute(
            "SELECT output_json FROM step_cache WHERE step = ? AND cache_key = ?", (step, key)
        ).fetchone()
        return json.loads(row["output_json"]) if row else None

    def _cached(self, step: str, key: str) -> Any | None:
        row = self.conn.execute(
            "SELECT output_json FROM step_cache WHERE step = ? AND cache_key = ?", (step, key)
        ).fetchone()
        if row is None:
            return None
        value: Any = json.loads(row["output_json"])
        # A cache entry is only valid while every asset it points to still exists.
        shas: list[object] = (
            [*value.values()] if isinstance(value, dict) else [value]  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        )
        if all(isinstance(s, str) and self.assets.path_for(s) for s in shas):
            return value  # pyright: ignore[reportUnknownVariableType]
        return None

    def _store(self, step: str, key: str, value: Any) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO step_cache (step, cache_key, output_json) VALUES (?, ?, ?)",
            (step, key, json.dumps(value)),
        )

    # Step cache for steps that run outside a job (audio-to-MIDI, pipeline/midi.py).
    def cached(self, step: str, key: str) -> Any | None:
        return self._cached(step, key)

    def remembered(self, step: str, key: str) -> Any | None:
        return self._remembered(step, key)

    def store(self, step: str, key: str, value: Any) -> None:
        self._store(step, key, value)

    # ------------------------------------------------------------ item steps

    def _run_item(
        self,
        job_id: int,
        item_id: int,
        raw_input: str,
        spec: JobSpec,
        recipe: Recipe,
        wanted: set[Stem],
    ) -> dict[str, str]:
        if raw_input.lower().startswith(("http://", "https://")):
            parsed = parse_input(raw_input)
            if parsed.kind is not InputKind.VIDEO:
                raise ValueError(f"expand playlists before submitting a job: {raw_input}")
            self._step(job_id, item_id, "download")
            source, title = self._download(job_id, item_id, parsed.value)
        else:
            source = Path(raw_input)
            title = source.stem
            if not source.exists():
                raise FileNotFoundError(f"input file not found: {source}")
        self._step(job_id, item_id, "decode")
        mix_sha = self._decode(source)
        self._step(job_id, item_id, "analyse")
        try:
            self.analyse(mix_sha)
        except Exception as exc:  # the analysis is an extra: never lose the stems over it
            self.events.emit("item.analysis_failed", job=job_id, item=item_id, error=str(exc))

        produced: dict[str, dict[Stem, str]] = {}
        for node in recipe.prune(wanted):
            self._step(job_id, item_id, f"separate:{node.id}")
            produced[node.id] = self._run_node(node, mix_sha, produced, spec)

        stems = {stem: produced[recipe.output_ref(stem).node][stem] for stem in wanted}
        self._record_preview(item_id, title, mix_sha, recipe, produced)
        self._step(job_id, item_id, "export")
        outputs = self._export(title, mix_sha, stems, spec)
        if not raw_input.lower().startswith(("http://", "https://")):
            credits = catalogs.read_credits(Path(raw_input))
            if credits is not None:  # Creative Commons audio: keep the attribution
                catalogs.write_credits(spec.output_dir, credits)
        return outputs

    def _record_preview(
        self,
        item_id: int,
        title: str,
        mix_sha: str,
        recipe: Recipe,
        produced: dict[str, dict[Stem, str]],
    ) -> None:
        """Remember the mix and every final stem produced, for the preview mixer."""
        available: dict[str, str] = {}
        for stem in recipe.outputs:
            ref = recipe.output_ref(stem)
            sha = produced.get(ref.node, {}).get(ref.stem)
            if sha:
                available[stem.value] = sha
        preview = {"title": title, "mix": mix_sha, "stems": available}
        self._set_item(item_id, preview_json=json.dumps(preview))

    def preview(self, item_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT preview_json FROM job_items WHERE id = ?", (item_id,)
        ).fetchone()
        return json.loads(row["preview_json"]) if row and row["preview_json"] else None

    def mix_sources(self, item_id: int) -> MixSources | None:
        """Files the mixer needs for an item (store access only; rendering is separate)."""
        preview = self.preview(item_id)
        if preview is None:
            return None
        job = self.conn.execute("SELECT job_id FROM job_items WHERE id = ?", (item_id,)).fetchone()
        return MixSources(
            title=safe_title(preview.get("title") or "track"),
            mix=self.assets.require(preview["mix"]),
            stems={Stem(k): self.assets.require(v) for k, v in preview["stems"].items()},
            spec=self.job_spec(job["job_id"]),
        )

    def _download(self, job_id: int, item_id: int, video_id: str) -> tuple[Path, str]:
        """Download a video's audio once; later runs reuse the cached file."""
        cached = self._cached("download", video_id)
        title = self._remembered("video_title", video_id)
        known = self._remembered("video_meta", video_id)
        if isinstance(known, dict):
            self._set_meta(job_id, item_id, str(known.get("title") or ""), known.get("artist"))  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
        else:
            # Name the item before the (possibly long) download starts.
            try:
                info = youtube.video_info(video_id)
                self._set_meta(job_id, item_id, info.display_title, info.display_artist)
            except youtube.DownloadError:
                pass  # the download below reports the real problem
        if cached and title is not None:
            return self.assets.require(str(cached)), str(title)

        def progress(fraction: float | None) -> None:
            self.events.emit(
                "item.progress", job=job_id, item=item_id, step="download", fraction=fraction
            )

        with tempfile.TemporaryDirectory(dir=self.paths.tmp) as scratch:
            try:
                path, info = youtube.download_audio(
                    video_id, Path(scratch), progress=progress, cancel=self._cancel
                )
            except youtube.DownloadCancelled as exc:
                raise JobCancelled() from exc
            sha = self.assets.put(path, "download", move=True)
        self._store("download", video_id, sha)
        self._store("video_title", video_id, info.title)
        self._store(
            "video_meta", video_id, {"title": info.display_title, "artist": info.display_artist}
        )
        self._set_meta(job_id, item_id, info.display_title, info.display_artist)
        return self.assets.require(sha), info.title

    def _decode(self, source: Path) -> str:
        key = f"{CACHE_VERSION}:{sha256_file(source)}:{io.SAMPLE_RATE}"
        cached = self._cached("decode", key)
        if cached:
            return str(cached)
        with tempfile.TemporaryDirectory(dir=self.paths.tmp) as scratch:
            target = io.decode_to_canonical(source, Path(scratch) / "mix.wav")
            sha = self.assets.put(target, "mix", move=True)
        self._store("decode", key, sha)
        return sha

    def analyse(self, mix_sha: str) -> analysis.Analysis:
        """Tuning, key, tempo and beat grid of a mix, computed once per mix and algorithm."""
        stored = analyses.load(self.conn, mix_sha)
        if stored is not None:
            return stored
        result = analysis.analyse(io.read(self.assets.require(mix_sha)), io.SAMPLE_RATE)
        analyses.save(self.conn, mix_sha, result)
        return result

    def item_mix(self, item_id: int) -> str | None:
        preview = self.preview(item_id)
        return str(preview["mix"]) if preview else None

    def _resolve(self, ref: Ref, produced: dict[str, dict[Stem, str]]) -> str:
        return produced[ref.node][ref.stem]

    def _node_input(self, node: Node, mix_sha: str, produced: dict[str, dict[Stem, str]]) -> str:
        if node.input.startswith(STEM):  # a stem of an earlier node, e.g. the vocals
            return self._resolve(Ref.parse(node.input.removeprefix(STEM)), produced)
        if not node.input.startswith(MINUS):
            return mix_sha
        stem_sha = self._resolve(Ref.parse(node.input.removeprefix(MINUS)), produced)
        key = f"{CACHE_VERSION}:{mix_sha}:{stem_sha}"
        cached = self._cached("minus", key)
        if cached:
            return str(cached)
        mix = io.read(self.assets.require(mix_sha))
        stem = io.read(self.assets.require(stem_sha))
        derived = mixer.without(mix, {Stem.VOCALS: stem}, {Stem.VOCALS}, ResidualMode.KEEP)
        with tempfile.TemporaryDirectory(dir=self.paths.tmp) as scratch:
            path = Path(scratch) / "input.wav"
            io.write_float(derived, path)
            sha = self.assets.put(path, "derived", move=True)
        self._store("minus", key, sha)
        return sha

    def _run_node(
        self, node: Node, mix_sha: str, produced: dict[str, dict[Stem, str]], spec: JobSpec
    ) -> dict[Stem, str]:
        if node.kind == "average":
            assert node.average is not None and node.stem is not None
            shas = [self._resolve(Ref.parse(ref), produced) for ref in node.average]
            key = f"{CACHE_VERSION}:avg:{':'.join(sorted(shas))}"
            cached = self._cached("average", key)
            if cached:
                return {Stem(k): v for k, v in cached.items()}
            mean = np.mean([io.read(self.assets.require(sha)) for sha in shas], axis=0).astype(
                np.float32
            )
            with tempfile.TemporaryDirectory(dir=self.paths.tmp) as scratch:
                path = Path(scratch) / f"{node.stem.value}.wav"
                io.write_float(mean, path)
                result = {node.stem: self.assets.put(path, "stem", move=True)}
            self._store("average", key, {k.value: v for k, v in result.items()})
            return result

        assert node.model is not None
        model = self.catalog.get(node.model)
        input_sha = self._node_input(node, mix_sha, produced)
        key = f"{CACHE_VERSION}:{input_sha}:{model.id}:{model.sha256 or model.filename}"
        cached = self._cached("separate", key)
        if cached:
            return {Stem(k): v for k, v in cached.items()}

        with tempfile.TemporaryDirectory(dir=self.paths.tmp) as scratch:
            request = SeparationRequest(
                model_filename=model.filename,
                model_dir=self.paths.models,
                input_path=self.assets.require(input_sha),
                output_dir=Path(scratch),
                stems=model.stems,  # keep every stem the model makes, for later reuse
            )
            audio_s = _duration(request.input_path)

            def record(attempt: SeparationRequest, seconds: float | None, oom: bool) -> None:
                self.tuning.record(
                    model.id, attempt.device, attempt.precision, attempt.chunk_s, audio_s,
                    seconds, oom,
                )  # fmt: skip

            result = with_ladder(
                self.service, request, use_gpu=self.use_gpu, allow_cpu=spec.allow_cpu_fallback,
                on_retry=lambda message: self.events.emit("separation.retry", message=message),
                start=self.tuning.first_gpu_rung(model.id, GPU_LADDER), record=record,
            )  # fmt: skip
            stored = {
                stem: self.assets.put(path, "stem", move=True)
                for stem, path in result.outputs.items()
            }
        self.events.emit(
            "separation.metrics", model=model.id, seconds=round(result.seconds, 2),
            device=result.device, precision=result.precision, chunk_s=result.chunk_s,
        )  # fmt: skip
        self._store("separate", key, {k.value: v for k, v in stored.items()})
        return stored

    def _export(
        self, name: str, mix_sha: str, stems: dict[Stem, str], spec: JobSpec
    ) -> dict[str, str]:
        title = safe_title(name)
        fmt = spec.output_format.value
        spec.output_dir.mkdir(parents=True, exist_ok=True)
        outputs: dict[str, str] = {}

        def export(name: str, render: Callable[[], io.Audio], parts: list[str]) -> None:
            target = spec.output_dir / f"{title} - {name}.{fmt}"
            key = f"{CACHE_VERSION}:{':'.join(parts)}:{fmt}:{target}"
            row = self.conn.execute(
                "SELECT 1 FROM step_cache WHERE step = 'export' AND cache_key = ?", (key,)
            ).fetchone()
            if row is None or not target.exists():
                io.write(mixer.protect_peaks(render()).audio, target, fmt)
                self._store("export", key, str(target))
            outputs[name] = str(target)

        if spec.mode in (Mode.EXTRACT, Mode.BOTH):
            for stem in spec.stems:
                sha = stems[stem]
                export(
                    stem_label(stem),
                    lambda sha=sha: io.read(self.assets.require(sha)),
                    [sha],
                )
        if spec.mode in (Mode.WITHOUT, Mode.BOTH):
            removed = set(spec.stems)
            label = "without " + ", ".join(stem_label(stem).lower() for stem in spec.stems)

            def render() -> io.Audio:
                mix = io.read(self.assets.require(mix_sha))
                arrays = {stem: io.read(self.assets.require(sha)) for stem, sha in stems.items()}
                return mixer.without(mix, arrays, removed, spec.residual)

            parts = [
                mix_sha,
                spec.residual.value,
                *sorted(f"{k.value}={v}" for k, v in stems.items()),
            ]
            export(label, render, parts)
        return outputs


def preset_models() -> dict[Preset, set[str]]:
    """Models each preset runs to produce every stem."""
    return {p: recipes.load(p).models(set(ALL_STEMS)) for p in Preset}


def resolve_preset(preset: str, tier_is_gpu: bool, tuning: Tuning | None = None) -> Preset:
    """``auto`` picks Balanced on a usable GPU and Fast on CPU-only machines.

    With measured runs, a GPU too slow for Balanced gets Fast (tuning.py).
    """
    if preset == "auto":
        if tuning is not None:
            return tuning.auto_preset(tier_is_gpu, preset_models())
        return Preset.BALANCED if tier_is_gpu else Preset.FAST
    return Preset(preset)


def _duration(path: Path) -> float:
    """Song length in seconds, or 0 when it cannot be read (no speed recorded)."""
    try:
        import soundfile  # pyright: ignore[reportMissingTypeStubs]

        return float(soundfile.info(str(path)).duration)
    except Exception:
        return 0.0
