"""Request and response models of the local API (source of the OpenAPI schema)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from ..domain import Mode, OutputFormat, ResidualMode, Stem


class Health(BaseModel):
    status: str
    version: str


class GpuOut(BaseModel):
    name: str
    total_mb: int
    free_mb: int
    compute_capability: float
    driver: str


class SystemOut(BaseModel):
    version: str
    data_dir: str
    cpu: str
    physical_cores: int
    ram_gb: float
    gpu: GpuOut | None
    tier: str
    recommended_preset: str
    measured_speed: dict[str, float | None] = Field(
        default_factory=dict,
        description="Seconds of work per second of audio measured for each preset (None: no runs yet).",
    )
    free_disk_gb: float
    on_battery: bool | None
    daws: list[str]
    ffmpeg: bool
    separation_available: bool
    demo: bool


class ModelOut(BaseModel):
    id: str
    name: str
    stems: list[Stem]
    size_mb: int
    vram_mb_fp16: int
    licence_class: str
    licence: str
    licence_url: str
    verified_on: date
    source: str
    notice: str
    recommended_for: list[str]
    installed: bool


class InstallRequest(BaseModel):
    accept_licence: bool = Field(description="The user accepted the model's licence notice.")


class JobRequest(BaseModel):
    inputs: list[str] = Field(min_length=1, description="Files, folders, or pasted video links.")
    stems: list[Stem] = Field(min_length=1)
    mode: Mode = Mode.EXTRACT
    residual: ResidualMode = ResidualMode.KEEP
    preset: str = Field("auto", description="auto, fast, balanced or max.")
    output_dir: Path
    output_format: OutputFormat = OutputFormat.WAV
    allow_cpu_fallback: bool = False
    rights_confirmed: bool = False


class JobCreated(BaseModel):
    job_id: int
    items: int
    online_items: int


class ItemOut(BaseModel):
    id: int
    ordinal: int
    input: str
    title: str | None = None
    artist: str | None = None
    status: str
    current_step: str | None
    outputs: dict[str, str]
    error: str | None


class JobOut(BaseModel):
    id: int
    status: str
    error: str | None
    created_at: str
    updated_at: str
    items: int
    done: int
    failed: int
    stems: list[Stem]
    mode: Mode
    preset: str
    output_dir: str


class JobDetail(JobOut):
    item_list: list[ItemOut]


class Count(BaseModel):
    count: int


class ApiError(BaseModel):
    detail: str
    code: str
    models: list[str] = []


class FolderRequest(BaseModel):
    path: Path


class PlaylistRequest(BaseModel):
    link: str


class ImportRequest(BaseModel):
    file: Path
    search: list[Path] = Field(min_length=1)


class CollectionOut(BaseModel):
    id: int
    kind: str
    source: str
    title: str
    items: int
    synced_at: str | None


class CollectionItemOut(BaseModel):
    id: int
    position: int
    title: str
    artist: str | None
    duration_s: float | None
    input: str | None
    score: float | None
    status: str
    manual: bool


class CollectionItemState(BaseModel):
    """Stems already exported for a collection item (latest finished job)."""

    item_id: int
    outputs: dict[str, str]


class DiagnosticsOut(BaseModel):
    path: str = Field(description="The zip written into the logs folder.")


class StorageOut(BaseModel):
    library_bytes: int
    library_files: int
    reclaimable_bytes: int = Field(description="Cached files no preview needs.")
    reclaimable_files: int
    models_bytes: int
    tmp_bytes: int


class CleanupOut(BaseModel):
    freed_bytes: int


class TempEntryOut(BaseModel):
    name: str = Field(description="Folder or file name inside the temp folder.")
    bytes: int
    files: int
    modified: datetime


class TemporaryOut(BaseModel):
    folder: str = Field(description="The temp folder; clearing it deletes every entry.")
    total_bytes: int
    entries: list[TempEntryOut]


class CatalogFileOut(BaseModel):
    name: str
    url: str
    title: str
    size_bytes: int | None


class CatalogEntryOut(BaseModel):
    source: str
    id: str
    title: str
    artist: str
    licence_name: str
    licence_url: str
    page_url: str
    restrictions: list[str] = Field(description="NC (non-commercial) and/or ND (no derivatives).")
    files: list[CatalogFileOut]


class CatalogAttachRequest(BaseModel):
    source: str
    path: Path = Field(description="Audio file the user downloaded from the catalogue's site.")
    title: str
    artist: str
    licence_name: str
    licence_url: str
    page_url: str


class CatalogAttachOut(BaseModel):
    path: str


class CatalogDownloadRequest(BaseModel):
    source: str
    file: CatalogFileOut
    title: str
    artist: str
    licence_name: str
    licence_url: str
    page_url: str


class SyncOut(BaseModel):
    collection_id: int
    added: int
    removed: int
    unchanged: int
    ready: list[str]
    needs_review: int
    unavailable: int


class MatchRequest(BaseModel):
    path: Path | None = Field(None, description="File to use, or null to mark unavailable.")


class Created(BaseModel):
    id: int


class PreviewOut(BaseModel):
    item_id: int
    title: str = Field("", description="Track title used for rendered file names.")
    mix: str = Field(description="Asset id (SHA-256) of the decoded mix.")
    stems: dict[str, str] = Field(description="Stem id -> asset id of every produced stem.")


class PeaksOut(BaseModel):
    asset: str
    points: int
    peaks: list[list[float]] = Field(description="[min, max] per point of the mono mix-down.")


class RenderRequest(BaseModel):
    gains: dict[Stem, float] = Field(
        default_factory=dict[Stem, float],
        description="Linear gain per stem (0 = muted, 1 = unchanged, max 4). Missing stems stay at 1.",
    )
    residual: ResidualMode = Field(
        ResidualMode.KEEP, description="keep: add back what no stem captured; drop: stems only."
    )
    output_format: OutputFormat | None = Field(None, description="Defaults to the job's format.")

    @field_validator("gains")
    @classmethod
    def _bounded(cls, value: dict[Stem, float]) -> dict[Stem, float]:
        if any(not 0.0 <= gain <= 4.0 for gain in value.values()):
            raise ValueError("gains must be between 0 and 4")
        return value


class RenderOut(BaseModel):
    path: str
    peak_dbfs: float = Field(description="Peak before protection (may be above 0 dBFS).")
    gain_db: float = Field(description="Gain applied to avoid clipping (0 or negative).")
