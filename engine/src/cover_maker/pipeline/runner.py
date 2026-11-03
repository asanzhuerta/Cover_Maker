"""Job runner: turns a :class:`JobSpec` into exported stems, step by step.

Steps per input: hash → decode → separation nodes → render/export. Every step
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
from pathlib import Path
from typing import Any

import numpy as np

from ..audio import io, mixer
from ..domain import ALL_STEMS, JobSpec, Mode, Preset, ResidualMode, Stem
from ..paths import Paths
from ..separation import recipes
from ..separation.catalog import Catalog, Installs, ModelSpec
from ..separation.recipes import MINUS, Node, Recipe, Ref
from ..separation.service import SeparationService, with_ladder
from ..separation.types import Cancelled, SeparationRequest
from ..sources import youtube
from ..sources.links import InputKind, parse_input
from ..store.assets import AssetStore, sha256_file
from .events import EventBus

CACHE_VERSION = "1"
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


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


def safe_title(name: str) -> str:
    cleaned = _UNSAFE.sub(" ", name).strip(" .")
    return re.sub(r"\s+", " ", cleaned)[:120] or "track"


def stems_to_separate(spec: JobSpec) -> set[Stem]:
    """Stems the models must produce for this job."""
    selected = set(spec.stems)
    if spec.mode is Mode.WITHOUT and spec.residual is ResidualMode.DROP:
        return set(ALL_STEMS)  # the remaining stems are summed
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
            self.conn.execute(
                "INSERT INTO job_items (job_id, ordinal, input_path) VALUES (?, ?, ?)",
                (job_id, ordinal, str(path)),
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
        assignments = ", ".join(f"{name} = ?" for name in fields)
        self.conn.execute(
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

    def _step(self, job_id: int, item_id: int, step: str) -> None:
        if self._cancel.is_set():
            raise JobCancelled()
        self._set_item(item_id, current_step=step)
        self.events.emit("item.step", job=job_id, item=item_id, step=step)

    # ------------------------------------------------------------ cache

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

        produced: dict[str, dict[Stem, str]] = {}
        for node in recipe.prune(wanted):
            self._step(job_id, item_id, f"separate:{node.id}")
            produced[node.id] = self._run_node(node, mix_sha, produced, spec)

        stems = {stem: produced[recipe.output_ref(stem).node][stem] for stem in wanted}
        self._record_preview(item_id, mix_sha, recipe, produced)
        self._step(job_id, item_id, "export")
        return self._export(title, mix_sha, stems, spec)

    def _record_preview(
        self, item_id: int, mix_sha: str, recipe: Recipe, produced: dict[str, dict[Stem, str]]
    ) -> None:
        """Remember the mix and every final stem produced, for the preview mixer."""
        available: dict[str, str] = {}
        for stem in recipe.outputs:
            ref = recipe.output_ref(stem)
            sha = produced.get(ref.node, {}).get(ref.stem)
            if sha:
                available[stem.value] = sha
        self._set_item(item_id, preview_json=json.dumps({"mix": mix_sha, "stems": available}))

    def _download(self, job_id: int, item_id: int, video_id: str) -> tuple[Path, str]:
        """Download a video's audio once; later runs reuse the cached file."""
        cached = self._cached("download", video_id)
        meta = self.conn.execute(
            "SELECT output_json FROM step_cache WHERE step = 'video_title' AND cache_key = ?",
            (video_id,),
        ).fetchone()
        if cached and meta:
            return self.assets.require(str(cached)), json.loads(meta["output_json"])

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

    def _resolve(self, ref: Ref, produced: dict[str, dict[Stem, str]]) -> str:
        return produced[ref.node][ref.stem]

    def _node_input(self, node: Node, mix_sha: str, produced: dict[str, dict[Stem, str]]) -> str:
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
            result = with_ladder(
                self.service, request, use_gpu=self.use_gpu, allow_cpu=spec.allow_cpu_fallback,
                on_retry=lambda message: self.events.emit("separation.retry", message=message),
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

        if spec.mode is Mode.EXTRACT:
            for stem in spec.stems:
                sha = stems[stem]
                export(
                    stem.value.capitalize(),
                    lambda sha=sha: io.read(self.assets.require(sha)),
                    [sha],
                )
        else:
            removed = set(spec.stems)
            label = "without " + ", ".join(stem.value for stem in spec.stems)

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


def resolve_preset(preset: str, tier_is_gpu: bool) -> Preset:
    """``auto`` picks Balanced on a usable GPU and Fast on CPU-only machines."""
    if preset == "auto":
        return Preset.BALANCED if tier_is_gpu else Preset.FAST
    return Preset(preset)
