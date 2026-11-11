"""FastAPI application for the local engine API.

All endpoints are ``async`` and hand database work to one worker thread at a
time (``_db``), so the API's SQLite connection is never used concurrently.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

from .. import __version__, diagnostics
from ..audio import io as audio_io
from ..audio.analysis import Analysis
from ..audio.analysis import analyse as analyse_audio
from ..audio.io import ffmpeg_path
from ..audio.peaks import compute_peaks
from ..audio.practice import Practice
from ..daw import export as daw_export
from ..domain import JobSpec
from ..pipeline.runner import (
    BeatGrid,
    RightsNotConfirmed,
    preset_models,
    render_custom_mix,
    resolve_preset,
    stems_to_separate,
)
from ..separation import recipes
from ..separation.hardware import Tier
from ..separation.installer import InstallError, install, separation_available
from ..separation.tuning import Tuning
from ..sources import catalogs, example
from ..sources.expand import expand_inputs
from ..sources.links import InputKind, UnsupportedInput, parse_input
from ..sources.youtube import DownloadError
from ..store import analyses, storage
from . import schemas
from .engine import EngineService
from .security import AccessMiddleware, AccessPolicy

# Free space kept on top of a model's size when it is downloaded.
MODEL_SPACE_MARGIN = 256 * 2**20

HEARTBEAT_SECONDS = 15.0
T = TypeVar("T")


class ApiProblem(Exception):
    def __init__(
        self, status: int, code: str, detail: str, models: list[str] | None = None
    ) -> None:
        super().__init__(detail)
        self.status, self.code, self.detail, self.models = status, code, detail, models or []


def create_app(policy: AccessPolicy, service: EngineService | None = None) -> FastAPI:
    app = FastAPI(title="Cover_Maker engine", version=__version__, docs_url=None, redoc_url=None)
    lock = threading.Lock()

    async def _db(fn: Callable[[], T]) -> T:
        def locked() -> T:
            with lock:
                return fn()

        return await asyncio.to_thread(locked)

    def engine() -> EngineService:
        if service is None:
            raise HTTPException(503, "engine service not configured")
        return service

    @app.exception_handler(ApiProblem)
    async def problem(_: Any, exc: ApiProblem) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        body = schemas.ApiError(detail=exc.detail, code=exc.code, models=exc.models)
        return JSONResponse(body.model_dump(), status_code=exc.status)

    # ------------------------------------------------------------ system

    @app.get("/health", response_model=schemas.Health)
    async def health() -> schemas.Health:  # pyright: ignore[reportUnusedFunction]
        return schemas.Health(status="ok", version=__version__)

    @app.get("/system", response_model=schemas.SystemOut)
    async def system(refresh: bool = False) -> schemas.SystemOut:  # pyright: ignore[reportUnusedFunction]
        svc = engine()
        hw = await asyncio.to_thread(svc.hardware, refresh)
        gpu = schemas.GpuOut(**hw.gpu.__dict__) if hw.gpu else None
        tuning = Tuning(svc.conn)
        recommended, speed = await _db(
            lambda: (
                resolve_preset("auto", hw.tier is not Tier.CPU, tuning),
                tuning.summary(preset_models()),
            )
        )
        return schemas.SystemOut(
            version=__version__, data_dir=str(svc.paths.home), cpu=hw.cpu_name,
            physical_cores=hw.physical_cores, ram_gb=hw.ram_gb, gpu=gpu, tier=hw.tier.value,
            recommended_preset=recommended.value,
            recommended_models=sorted(preset_models()[recommended]), measured_speed=speed,
            free_disk_gb=hw.free_disk_gb, on_battery=hw.on_battery, daws=hw.daws,
            ffmpeg=ffmpeg_path() is not None,
            separation_available=svc.demo or separation_available(), demo=svc.demo,
        )  # fmt: skip

    @app.post("/diagnostics", response_model=schemas.DiagnosticsOut)
    async def create_diagnostics() -> schemas.DiagnosticsOut:  # pyright: ignore[reportUnusedFunction]
        """Write a redacted diagnostic zip into the logs folder."""
        svc = engine()
        info = (await system()).model_dump()
        path = await _db(lambda: diagnostics.build(svc.conn, svc.paths, info))
        return schemas.DiagnosticsOut(path=str(path))

    # ------------------------------------------------------------ models

    def _model_out(model_id: str) -> schemas.ModelOut:
        svc = engine()
        model = svc.catalog.get(model_id)
        return schemas.ModelOut(
            id=model.id, name=model.name, stems=sorted(model.produces), size_mb=model.size_mb,
            vram_mb_fp16=model.vram_mb_fp16, licence_class=model.licence_class.value,
            licence=model.licence, licence_url=model.licence_url,
            verified_on=model.verified_on, source=model.source, notice=model.notice(),
            recommended_for=model.recommended_for, installed=svc.installs.is_installed(model),
        )  # fmt: skip

    @app.get("/models", response_model=list[schemas.ModelOut])
    async def models() -> list[schemas.ModelOut]:  # pyright: ignore[reportUnusedFunction]
        return await _db(lambda: [_model_out(m) for m in engine().catalog.models])

    @app.post("/models/{model_id}/install", status_code=202, response_model=schemas.ModelOut)
    async def install_model(model_id: str, body: schemas.InstallRequest) -> schemas.ModelOut:  # pyright: ignore[reportUnusedFunction]
        svc = engine()
        if model_id not in svc.catalog.models:
            raise ApiProblem(404, "unknown_model", f"unknown model {model_id}")
        if not body.accept_licence:
            raise ApiProblem(400, "licence_not_accepted", "the licence notice must be accepted")
        model = svc.catalog.get(model_id)
        if not svc.demo and not svc.installs.is_installed(model):
            needed = model.size_mb * 2**20 + MODEL_SPACE_MARGIN
            free = shutil.disk_usage(svc.paths.models.parent).free
            if free < needed:
                raise ApiProblem(
                    507, "not_enough_space",
                    f"the model needs {model.size_mb} MB and {free // 2**20} MB are free",
                )  # fmt: skip

        def run() -> None:
            svc.bus.emit("model.install.started", model=model_id)
            try:
                if svc.demo:
                    with lock:
                        svc.installs.record(model, None)
                else:
                    install(
                        model, svc.paths.models, svc.installs, accepted=True,
                        progress=lambda fraction: svc.bus.emit(
                            "model.install.progress", model=model_id, progress=round(fraction, 3)
                        ),
                    )  # fmt: skip
                svc.bus.emit("model.install.done", model=model_id)
            except InstallError as exc:
                svc.bus.emit("model.install.failed", model=model_id, error=str(exc), code=exc.code)

        threading.Thread(target=run, daemon=True).start()
        return await _db(lambda: _model_out(model_id))

    # ------------------------------------------------------------ jobs

    def _job_out(row: Any) -> schemas.JobOut:
        spec = JobSpec.model_validate_json(row["spec_json"])
        return schemas.JobOut(
            id=row["id"], status=row["status"], error=row["error"], created_at=row["created_at"],
            updated_at=row["updated_at"], items=row["items"] or 0, done=row["done"] or 0,
            failed=row["failed"] or 0, stems=spec.stems, mode=spec.mode, preset=spec.preset.value,
            output_dir=str(spec.output_dir),
        )  # fmt: skip

    def _job_detail(job_id: int) -> schemas.JobDetail:
        svc = engine()
        row = next((r for r in svc.jobs.jobs(10_000) if r["id"] == job_id), None)
        if row is None:
            raise ApiProblem(404, "unknown_job", f"job {job_id} does not exist")
        items = [
            schemas.ItemOut(
                id=i["id"],
                ordinal=i["ordinal"],
                input=i["input_path"],
                title=i["title"],
                artist=i["artist"],
                status=i["status"],
                current_step=i["current_step"],
                outputs=json.loads(i["outputs_json"] or "{}"),
                error=i["error"],
            )
            for i in svc.jobs.items(job_id)
        ]
        return schemas.JobDetail(**_job_out(row).model_dump(), item_list=items)

    @app.get("/jobs", response_model=list[schemas.JobOut])
    async def list_jobs(limit: int = 50) -> list[schemas.JobOut]:  # pyright: ignore[reportUnusedFunction]
        return await _db(lambda: [_job_out(r) for r in engine().jobs.jobs(limit)])

    @app.get("/jobs/{job_id}", response_model=schemas.JobDetail)
    async def get_job(job_id: int) -> schemas.JobDetail:  # pyright: ignore[reportUnusedFunction]
        return await _db(lambda: _job_detail(job_id))

    @app.post(
        "/jobs", status_code=201, response_model=schemas.JobCreated,
        responses={400: {"model": schemas.ApiError}, 409: {"model": schemas.ApiError}},
    )  # fmt: skip
    async def create_job(body: schemas.JobRequest) -> schemas.JobCreated:  # pyright: ignore[reportUnusedFunction]
        svc = engine()
        try:
            expanded, online = await asyncio.to_thread(expand_inputs, body.inputs)
        except (UnsupportedInput, FileNotFoundError) as exc:
            raise ApiProblem(400, "bad_input", str(exc)) from exc
        except DownloadError as exc:
            raise ApiProblem(400, "playlist_unavailable", str(exc)) from exc
        if not expanded:
            raise ApiProblem(400, "no_audio", "no audio files were found in the inputs")
        if online and not body.rights_confirmed:
            raise ApiProblem(400, "rights_required", str(RightsNotConfirmed()))
        hw = await asyncio.to_thread(svc.hardware)
        preset = await _db(
            lambda: resolve_preset(body.preset, hw.tier is not Tier.CPU, Tuning(svc.conn))
        )
        spec = JobSpec(
            inputs=expanded, stems=body.stems, mode=body.mode, residual=body.residual,
            preset=preset, output_dir=body.output_dir,
            output_format=body.output_format, allow_cpu_fallback=body.allow_cpu_fallback,
            rights_confirmed=body.rights_confirmed,
        )  # fmt: skip

        def submit() -> int:
            needed = recipes.load(spec.preset).models(stems_to_separate(spec))
            missing = [
                m for m in sorted(needed) if not svc.installs.is_installed(svc.catalog.get(m))
            ]
            if missing:
                raise ApiProblem(
                    409, "model_not_installed", "install the required models first", missing
                )
            return svc.submit(spec)

        job_id = await _db(submit)
        return schemas.JobCreated(job_id=job_id, items=len(expanded), online_items=online)

    @app.post("/jobs/{job_id}/cancel", status_code=202)
    async def cancel_job(job_id: int) -> dict[str, int]:  # pyright: ignore[reportUnusedFunction]
        engine().cancel()
        return {"job_id": job_id}

    @app.post("/jobs/{job_id}/pause", status_code=202)
    async def pause_job(job_id: int) -> dict[str, int]:  # pyright: ignore[reportUnusedFunction]
        engine().pause()
        return {"job_id": job_id}

    @app.post("/jobs/{job_id}/resume", status_code=202)
    async def resume_job(job_id: int) -> dict[str, int]:  # pyright: ignore[reportUnusedFunction]
        engine().resume(job_id)
        return {"job_id": job_id}

    @app.post("/jobs/{job_id}/retry", response_model=schemas.Count)
    async def retry_job(job_id: int) -> schemas.Count:  # pyright: ignore[reportUnusedFunction]
        return schemas.Count(count=await _db(lambda: engine().retry(job_id)))

    @app.delete("/jobs/{job_id}", status_code=204)
    async def delete_job(job_id: int) -> None:  # pyright: ignore[reportUnusedFunction]
        """Remove a finished job from the history (its exported files stay)."""

        def run() -> None:
            conn = engine().conn
            row = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                raise ApiProblem(404, "unknown_job", f"job {job_id} does not exist")
            if row["status"] in ("pending", "running"):
                raise ApiProblem(409, "job_active", "pause or cancel the job first")
            conn.execute("DELETE FROM job_items WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

        await _db(run)

    # ------------------------------------------------------------ storage

    @app.get("/storage", response_model=schemas.StorageOut)
    async def storage_usage() -> schemas.StorageOut:  # pyright: ignore[reportUnusedFunction]
        svc = engine()
        result = await _db(lambda: storage.usage(svc.conn, svc.paths))
        return schemas.StorageOut(**result.__dict__)

    @app.post("/storage/cleanup", response_model=schemas.CleanupOut)
    async def storage_cleanup() -> schemas.CleanupOut:  # pyright: ignore[reportUnusedFunction]
        svc = engine()
        if svc.busy:
            raise ApiProblem(409, "job_active", "wait until the queue is idle")
        return schemas.CleanupOut(
            freed_bytes=await _db(lambda: storage.clean_up(svc.conn, svc.paths))
        )

    @app.get("/storage/temporary", response_model=schemas.TemporaryOut)
    async def storage_temporary() -> schemas.TemporaryOut:  # pyright: ignore[reportUnusedFunction]
        svc = engine()
        entries = await asyncio.to_thread(storage.temporary, svc.paths)
        return schemas.TemporaryOut(
            folder=str(svc.paths.tmp),
            total_bytes=sum(e.bytes for e in entries),
            entries=[schemas.TempEntryOut(**e.__dict__) for e in entries],
        )

    @app.post("/storage/temporary/clear", response_model=schemas.CleanupOut)
    async def storage_temporary_clear() -> schemas.CleanupOut:  # pyright: ignore[reportUnusedFunction]
        svc = engine()
        if svc.busy:
            raise ApiProblem(409, "job_active", "wait until the queue is idle")
        return schemas.CleanupOut(
            freed_bytes=await asyncio.to_thread(storage.clear_temporary, svc.paths)
        )

    # ------------------------------------------------------------ catalogues

    def _entry_out(entry: catalogs.CatalogEntry) -> schemas.CatalogEntryOut:
        return schemas.CatalogEntryOut(
            source=entry.source, id=entry.id, title=entry.title, artist=entry.artist,
            licence_name=entry.licence_name, licence_url=entry.licence_url,
            page_url=entry.page_url, restrictions=entry.restrictions,
            files=[schemas.CatalogFileOut(**f.__dict__) for f in entry.files],
        )  # fmt: skip

    @app.get("/catalog/search", response_model=list[schemas.CatalogEntryOut])
    async def catalog_search(source: str, q: str) -> list[schemas.CatalogEntryOut]:  # pyright: ignore[reportUnusedFunction]
        if source not in catalogs.SOURCES:
            raise ApiProblem(400, "bad_input", f"unknown catalogue: {source}")
        try:
            entries = await asyncio.to_thread(catalogs.search, source, q)
        except catalogs.CatalogError as exc:
            raise ApiProblem(502, "catalog_unavailable", str(exc)) from exc
        return [_entry_out(e) for e in entries]

    @app.get("/catalog/archive/{identifier}/files", response_model=list[schemas.CatalogFileOut])
    async def catalog_archive_files(identifier: str) -> list[schemas.CatalogFileOut]:  # pyright: ignore[reportUnusedFunction]
        try:
            files = await asyncio.to_thread(catalogs.archive_files, identifier)
        except catalogs.CatalogError as exc:
            raise ApiProblem(502, "catalog_unavailable", str(exc)) from exc
        return [schemas.CatalogFileOut(**f.__dict__) for f in files]

    @app.post("/catalog/attach", response_model=schemas.CatalogAttachOut)
    async def catalog_attach(body: schemas.CatalogAttachRequest) -> schemas.CatalogAttachOut:  # pyright: ignore[reportUnusedFunction]
        """Add a file downloaded on the catalogue's site, keeping its credits."""
        if body.source not in catalogs.SOURCES:
            raise ApiProblem(400, "bad_input", f"unknown catalogue: {body.source}")
        svc = engine()
        credits = catalogs.Credits(
            title=body.title, artist=body.artist, licence_name=body.licence_name,
            licence_url=body.licence_url, page_url=body.page_url, source=body.source,
        )  # fmt: skip
        target_dir = svc.paths.home / "library" / "cc" / body.source
        try:
            path = await asyncio.to_thread(catalogs.attach, body.path, credits, target_dir)
        except catalogs.CatalogError as exc:
            raise ApiProblem(400, "bad_input", str(exc)) from exc
        return schemas.CatalogAttachOut(path=str(path))

    @app.post("/catalog/download", status_code=202)
    async def catalog_download(body: schemas.CatalogDownloadRequest) -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """Download a CC track into the library's `cc` folder, in the background."""
        if not catalogs.allowed_download(body.file.url):
            raise ApiProblem(400, "bad_input", "the app downloads only from the Internet Archive")
        if not catalogs.is_open_licence(body.licence_url):
            raise ApiProblem(400, "bad_input", "not a Creative Commons or public-domain licence")
        svc = engine()
        file = catalogs.CatalogFile(**body.file.model_dump())
        credits = catalogs.Credits(
            title=body.title, artist=body.artist, licence_name=body.licence_name,
            licence_url=body.licence_url, page_url=body.page_url, source=body.source,
        )  # fmt: skip
        target_dir = svc.paths.home / "library" / "cc" / body.source

        def run() -> None:
            svc.bus.emit("catalog.download.started", url=file.url)
            try:
                path = catalogs.download(file, credits, target_dir)
                svc.bus.emit("catalog.download.done", url=file.url, path=str(path))
            except catalogs.CatalogError as exc:
                svc.bus.emit("catalog.download.failed", url=file.url, error=str(exc))

        threading.Thread(target=run, daemon=True).start()
        return {"status": "started"}

    # ------------------------------------------------------------ example song

    @app.get("/example", response_model=schemas.ExampleOut)
    async def example_info() -> schemas.ExampleOut:  # pyright: ignore[reportUnusedFunction]
        """The Creative Commons example clip offered on first run."""
        clip = await asyncio.to_thread(example.load)
        credits = clip.credits
        return schemas.ExampleOut(
            title=credits.title, artist=credits.artist, licence_name=credits.licence_name,
            licence_url=credits.licence_url, page_url=credits.page_url, changes=credits.changes,
            duration_s=clip.duration_s, size_bytes=clip.size_bytes,
        )  # fmt: skip

    @app.post("/example", response_model=schemas.ExampleAdded)
    async def example_add() -> schemas.ExampleAdded:  # pyright: ignore[reportUnusedFunction]
        """Copy the example clip into the library, with its credits for the export."""
        library = engine().paths.home / "library"
        path = await asyncio.to_thread(example.add, library)
        return schemas.ExampleAdded(path=str(path), output_dir=str(library / "example" / "stems"))

    # ------------------------------------------------------------ library

    def _collection_out(row: Any) -> schemas.CollectionOut:
        return schemas.CollectionOut(
            id=row["id"], kind=row["kind"], source=row["source"], title=row["title"],
            items=row["items"], synced_at=row["synced_at"],
        )  # fmt: skip

    @app.get("/library", response_model=list[schemas.CollectionOut])
    async def collections() -> list[schemas.CollectionOut]:  # pyright: ignore[reportUnusedFunction]
        return await _db(lambda: [_collection_out(r) for r in engine().library.collections()])

    @app.post("/library/folders", status_code=201, response_model=schemas.Created)
    async def add_folder(body: schemas.FolderRequest) -> schemas.Created:  # pyright: ignore[reportUnusedFunction]
        if not body.path.is_dir():
            raise ApiProblem(400, "bad_input", f"not a folder: {body.path}")
        return schemas.Created(id=await _db(lambda: engine().library.add_folder(body.path)))

    @app.post("/library/playlists", status_code=201, response_model=schemas.Created)
    async def add_playlist(body: schemas.PlaylistRequest) -> schemas.Created:  # pyright: ignore[reportUnusedFunction]
        try:
            parsed = parse_input(body.link, prefer_playlist=True)
        except UnsupportedInput as exc:
            raise ApiProblem(400, "bad_input", str(exc)) from exc
        if parsed.kind is not InputKind.PLAYLIST:
            raise ApiProblem(400, "bad_input", "that link is not a playlist")
        return schemas.Created(
            id=await _db(lambda: engine().library.add_video_playlist(parsed.value))
        )

    @app.post("/library/imports", status_code=201, response_model=list[schemas.Created])
    async def import_playlist(body: schemas.ImportRequest) -> list[schemas.Created]:  # pyright: ignore[reportUnusedFunction]
        if not body.file.is_file():
            raise ApiProblem(400, "bad_input", f"file not found: {body.file}")
        ids = await _db(lambda: engine().library.import_playlist_file(body.file, body.search))
        return [schemas.Created(id=i) for i in ids]

    @app.delete("/library/{collection_id}", status_code=204)
    async def delete_collection(collection_id: int) -> None:  # pyright: ignore[reportUnusedFunction]
        """Forget a collection (the audio files themselves are not touched)."""

        def run() -> None:
            conn = engine().conn
            conn.execute("DELETE FROM collection_items WHERE collection_id = ?", (collection_id,))
            if conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,)).rowcount == 0:
                raise ApiProblem(
                    404, "unknown_collection", f"collection {collection_id} does not exist"
                )

        await _db(run)

    @app.get("/library/{collection_id}/state", response_model=list[schemas.CollectionItemState])
    async def collection_state(collection_id: int) -> list[schemas.CollectionItemState]:  # pyright: ignore[reportUnusedFunction]
        """For each item already separated, the files of its latest finished job."""

        def run() -> list[schemas.CollectionItemState]:
            conn = engine().conn
            rows = conn.execute(
                "SELECT ci.id AS item_id, ji.outputs_json FROM collection_items ci "
                "JOIN job_items ji ON ji.input_path = ci.input AND ji.status = 'done' "
                "WHERE ci.collection_id = ? ORDER BY ji.id",
                (collection_id,),
            ).fetchall()
            latest = {int(r["item_id"]): json.loads(r["outputs_json"] or "{}") for r in rows}
            return [schemas.CollectionItemState(item_id=k, outputs=v) for k, v in latest.items()]

        return await _db(run)

    @app.post("/library/{collection_id}/sync", response_model=schemas.SyncOut)
    async def sync(collection_id: int) -> schemas.SyncOut:  # pyright: ignore[reportUnusedFunction]
        def run() -> schemas.SyncOut:
            try:
                result = engine().library.sync(collection_id)
            except KeyError as exc:
                raise ApiProblem(404, "unknown_collection", str(exc)) from exc
            except (FileNotFoundError, DownloadError) as exc:
                raise ApiProblem(400, "sync_failed", str(exc)) from exc
            return schemas.SyncOut(**result.__dict__)

        return await _db(run)

    @app.get("/library/{collection_id}/items", response_model=list[schemas.CollectionItemOut])
    async def collection_items(collection_id: int) -> list[schemas.CollectionItemOut]:  # pyright: ignore[reportUnusedFunction]
        def run() -> list[schemas.CollectionItemOut]:
            return [
                schemas.CollectionItemOut(
                    id=r["id"],
                    position=r["position"],
                    title=r["title"],
                    artist=r["artist"],
                    duration_s=r["duration_s"],
                    input=r["input"],
                    score=r["score"],
                    status=r["status"],
                    manual=bool(r["manual"]),
                )
                for r in engine().library.items(collection_id)
            ]

        return await _db(run)

    # ------------------------------------------------------------ preview audio

    @app.get("/items/{item_id}/preview", response_model=schemas.PreviewOut)
    async def preview(item_id: int) -> schemas.PreviewOut:  # pyright: ignore[reportUnusedFunction]
        def run() -> schemas.PreviewOut:
            data = engine().jobs.preview(item_id)
            if data is None:
                raise ApiProblem(404, "no_preview", f"item {item_id} has no stems to preview yet")
            return schemas.PreviewOut(
                item_id=item_id, title=data.get("title", ""), mix=data["mix"], stems=data["stems"]
            )

        return await _db(run)

    @app.post("/items/{item_id}/render", response_model=schemas.RenderOut)
    async def render(item_id: int, body: schemas.RenderRequest) -> schemas.RenderOut:  # pyright: ignore[reportUnusedFunction]
        sources = await _db(lambda: engine().jobs.mix_sources(item_id))
        if sources is None:
            raise ApiProblem(404, "no_preview", f"item {item_id} has no stems to mix yet")
        fmt = body.output_format.value if body.output_format else None
        grid: BeatGrid | None = None
        if body.click_gain > 0 or body.with_stems:
            mix = await _db(lambda: _item_mix(item_id))
            stored = await _db(lambda: analyses.load(engine().conn, mix))
            if stored is not None and stored.beats:
                grid = BeatGrid(beats=stored.beats, downbeats=stored.downbeats)
        settings = Practice(tempo=body.tempo, semitones=body.semitones, cents=body.cents)
        try:
            # Rendering only reads library files, so it runs outside the store lock.
            target, result = await asyncio.to_thread(
                lambda: render_custom_mix(
                    sources,
                    body.gains,
                    body.residual,
                    fmt,
                    body.pans,
                    practice_settings=settings,
                    click_gain=body.click_gain,
                    grid=grid,
                    with_stems=body.with_stems,
                )
            )
        except (RuntimeError, OSError) as exc:
            raise ApiProblem(500, "render_failed", str(exc)) from exc
        return schemas.RenderOut(
            path=str(target), peak_dbfs=max(result.peak_dbfs, -200.0), gain_db=result.gain_db
        )

    # ------------------------------------------------------------ practice (M14)

    def _analysis_out(item_id: int, mix: str, result: Analysis) -> schemas.AnalysisOut:
        markers = analyses.load_markers(engine().conn, mix)
        return schemas.AnalysisOut(
            item_id=item_id,
            mix=mix,
            tuning_cents=result.tuning_cents,
            key=result.key,
            mode=result.mode,
            key_confidence=result.key_confidence,
            bpm=result.bpm,
            beats=result.beats,
            downbeats=result.downbeats,
            markers=[schemas.MarkerIn(name=m.name, time=m.time) for m in markers],
        )

    def _item_mix(item_id: int) -> str:
        mix = engine().jobs.item_mix(item_id)
        if mix is None:
            raise ApiProblem(404, "no_preview", f"item {item_id} has no analysed mix yet")
        return mix

    async def _ensure_analysis(mix: str) -> Analysis:
        """The stored analysis of a mix; computed now for items separated before M14."""
        stored = await _db(lambda: analyses.load(engine().conn, mix))
        if stored is not None:
            return stored
        path = await _db(lambda: engine().jobs.assets.require(mix))
        try:
            result = await asyncio.to_thread(
                lambda: analyse_audio(audio_io.read(path), audio_io.SAMPLE_RATE)
            )
        except (RuntimeError, OSError, ValueError) as exc:
            raise ApiProblem(500, "analysis_failed", str(exc)) from exc
        await _db(lambda: analyses.save(engine().conn, mix, result))
        return result

    @app.get("/items/{item_id}/analysis", response_model=schemas.AnalysisOut)
    async def item_analysis(item_id: int) -> schemas.AnalysisOut:  # pyright: ignore[reportUnusedFunction]
        """Tuning, key, tempo and beat grid; computed now for items separated before M14."""
        mix = await _db(lambda: _item_mix(item_id))
        final = await _ensure_analysis(mix)
        return await _db(lambda: _analysis_out(item_id, mix, final))

    @app.put("/items/{item_id}/markers", response_model=list[schemas.MarkerIn])
    async def item_markers(item_id: int, body: schemas.MarkersIn) -> list[schemas.MarkerIn]:  # pyright: ignore[reportUnusedFunction]
        def run() -> list[schemas.MarkerIn]:
            mix = _item_mix(item_id)
            saved = analyses.save_markers(
                engine().conn,
                mix,
                [analyses.Marker(name=m.name.strip(), time=m.time) for m in body.markers],
            )
            return [schemas.MarkerIn(name=m.name, time=m.time) for m in saved]

        return await _db(run)

    # ------------------------------------------------------------ DAW session

    @app.post("/items/{item_id}/session", response_model=schemas.SessionOut)
    async def item_session(item_id: int, body: schemas.SessionRequest) -> schemas.SessionOut:  # pyright: ignore[reportUnusedFunction]
        """Write a DAW session: every stem on its own track at 0, with the tempo map,
        section markers and key (REAPER, DAWproject and a MIDI tempo map)."""
        sources = await _db(lambda: engine().jobs.mix_sources(item_id))
        if sources is None:
            raise ApiProblem(404, "no_preview", f"item {item_id} has no stems to export yet")
        mix = await _db(lambda: _item_mix(item_id))
        analysis = await _ensure_analysis(mix)
        markers = await _db(lambda: analyses.load_markers(engine().conn, mix))
        settings = {
            stem: daw_export.TrackSettings(gain=track.gain, pan=track.pan, muted=track.muted)
            for stem, track in body.tracks.items()
        }
        try:
            # Writing only reads library files, so it runs outside the store lock.
            files = await asyncio.to_thread(
                lambda: daw_export.export_session(
                    sources, settings, body.residual, analysis, markers, set(body.formats)
                )
            )
        except (RuntimeError, OSError, ValueError) as exc:
            raise ApiProblem(500, "session_failed", str(exc)) from exc
        return schemas.SessionOut(
            folder=str(files.folder),
            projects={fmt: str(path) for fmt, path in files.projects.items()},
            tracks=files.tracks,
        )

    def _asset_path(sha: str) -> Path:
        # Only files registered in the library can be served (no arbitrary paths).
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ApiProblem(400, "bad_input", "invalid asset id")
        path = engine().jobs.assets.path_for(sha)
        if path is None:
            raise ApiProblem(404, "unknown_asset", f"asset {sha} does not exist")
        return path

    @app.get("/assets/{sha}", response_class=FileResponse)
    async def asset(sha: str) -> FileResponse:  # pyright: ignore[reportUnusedFunction]
        path = await _db(lambda: _asset_path(sha))
        return FileResponse(path, media_type="audio/wav")

    @app.get("/assets/{sha}/peaks", response_model=schemas.PeaksOut)
    async def peaks(sha: str, points: int = 1200) -> schemas.PeaksOut:  # pyright: ignore[reportUnusedFunction]
        points = max(50, min(points, 10_000))
        path = await _db(lambda: _asset_path(sha))
        key = f"{sha}:{points}"

        def cached() -> object | None:
            row = (
                engine()
                .conn.execute(
                    "SELECT output_json FROM step_cache WHERE step = 'peaks' AND cache_key = ?",
                    (key,),
                )
                .fetchone()
            )
            return json.loads(row["output_json"]) if row else None

        values = await _db(cached)
        if values is None:
            values = await asyncio.to_thread(compute_peaks, path, points)
            await _db(
                lambda: engine().conn.execute(
                    "INSERT OR REPLACE INTO step_cache (step, cache_key, output_json) VALUES ('peaks', ?, ?)",
                    (key, json.dumps(values)),
                )
            )
        return schemas.PeaksOut(asset=sha, points=points, peaks=values)  # pyright: ignore[reportArgumentType]

    @app.put("/library/items/{item_id}/match", status_code=204)
    async def set_match(item_id: int, body: schemas.MatchRequest) -> None:  # pyright: ignore[reportUnusedFunction]
        if body.path is not None and not Path(body.path).is_file():
            raise ApiProblem(400, "bad_input", f"file not found: {body.path}")
        await _db(lambda: engine().library.set_match(item_id, body.path))

    # ------------------------------------------------------------ events

    @app.websocket("/events")
    async def events(websocket: WebSocket) -> None:  # pyright: ignore[reportUnusedFunction]
        await websocket.accept()
        try:
            hello: Any = json.loads(await asyncio.wait_for(websocket.receive_text(), timeout=5))
        except (TimeoutError, json.JSONDecodeError, WebSocketDisconnect):
            await websocket.close(code=4401)
            return
        if not (isinstance(hello, dict) and policy.token_ok(hello.get("token"))):  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
            await websocket.close(code=4401)
            return
        since = hello.get("since")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        await websocket.send_json({"seq": 0, "type": "hello", "version": __version__})
        if service is None:
            await websocket.close()
            return
        subscriber, missed = service.events.subscribe(
            asyncio.get_running_loop(), since if isinstance(since, int) else None
        )
        try:
            for event in missed:
                await websocket.send_json(event)
            while True:
                try:
                    event = await asyncio.wait_for(subscriber.queue.get(), HEARTBEAT_SECONDS)
                except TimeoutError:
                    await websocket.send_json({"seq": 0, "type": "heartbeat"})
                    continue
                await websocket.send_json(event)
        except (WebSocketDisconnect, RuntimeError):
            return
        finally:
            service.events.unsubscribe(subscriber)

    app.add_middleware(AccessMiddleware, policy=policy)
    return app
