"""Request and response models of the local API (source of the OpenAPI schema)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from ..daw.model import DawFormat
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
    recommended_models: list[str] = Field(
        default_factory=list[str],
        description="Models the recommended preset runs to produce every stem.",
    )
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


class ExampleOut(BaseModel):
    title: str
    artist: str
    licence_name: str
    licence_url: str
    page_url: str
    changes: str
    duration_s: float
    size_bytes: int


class ExampleAdded(BaseModel):
    path: str = Field(description="The example's copy in the library, ready to use as a job input.")
    output_dir: str = Field(
        description="Suggested folder for its stems when the user has not chosen one yet."
    )


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


class MarkerIn(BaseModel):
    name: str = Field(min_length=1, max_length=40, description="Section name, e.g. Verse 1.")
    time: float = Field(ge=0, description="Seconds from the start of the song.")


class MarkersIn(BaseModel):
    markers: list[MarkerIn] = Field(max_length=200)


class AnalysisOut(BaseModel):
    item_id: int
    mix: str = Field(description="Asset id (SHA-256) of the analysed mix.")
    tuning_cents: float = Field(description="Offset of the recording from A440, in cents.")
    key: str = Field(description="Tonic pitch class, e.g. C, F#, Eb.")
    mode: str = Field(description="major or minor.")
    key_confidence: float = Field(description="Best key score minus the runner-up (0 = ambiguous).")
    bpm: float = Field(description="Tempo in beats per minute (0 when no beat was found).")
    beats: list[float] = Field(description="Beat times in seconds.")
    downbeats: list[float] = Field(description="Bar starts in seconds (4/4 assumed).")
    markers: list[MarkerIn] = Field(description="Named section markers, sorted by time.")


class SessionTrackIn(BaseModel):
    gain: float = Field(1.0, ge=0, le=4, description="Linear fader gain (1 = 0 dB).")
    pan: float = Field(0.0, ge=-1, le=1, description="Stereo balance from -1 (left) to 1 (right).")
    muted: bool = Field(False, description="Muted track (after mute and solo in the mixer).")


class SessionRequest(BaseModel):
    tracks: dict[Stem, SessionTrackIn] = Field(
        default_factory=dict[Stem, SessionTrackIn],
        description="Mixer settings per stem. Missing stems are at 0 dB, centred and audible.",
    )
    residual: ResidualMode = Field(
        ResidualMode.KEEP,
        description="keep: the Residual track plays; drop: it is muted.",
    )
    formats: list[DawFormat] = Field(
        default_factory=lambda: list(DawFormat),
        min_length=1,
        description="Project files to write next to the stems (all by default).",
    )


class SessionOut(BaseModel):
    folder: str = Field(description="New folder with the audio files and the project files.")
    projects: dict[DawFormat, str] = Field(description="Path of each project file written.")
    tracks: list[str] = Field(description="Track names, in project order.")


class PeaksOut(BaseModel):
    asset: str
    points: int
    peaks: list[list[float]] = Field(description="[min, max] per point of the mono mix-down.")


class RenderRequest(BaseModel):
    gains: dict[Stem, float] = Field(
        default_factory=dict[Stem, float],
        description="Linear gain per stem (0 = muted, 1 = unchanged, max 4). Missing stems stay at 1.",
    )
    pans: dict[Stem, float] = Field(
        default_factory=dict[Stem, float],
        description="Stereo balance per stem from -1 (left) to 1 (right). Missing stems stay centred.",
    )
    residual: ResidualMode = Field(
        ResidualMode.KEEP, description="keep: add back what no stem captured; drop: stems only."
    )
    output_format: OutputFormat | None = Field(None, description="Defaults to the job's format.")
    tempo: float = Field(1.0, ge=0.5, le=1.5, description="Tempo factor (1 = original speed).")
    semitones: float = Field(0.0, ge=-12, le=12, description="Pitch shift in semitones.")
    cents: float = Field(0.0, ge=-50, le=50, description="Fine pitch shift in cents.")
    click_gain: float = Field(
        0.0, ge=0, le=4, description="Linear gain of the click stem in the mix (0 = no click)."
    )
    with_stems: bool = Field(
        False, description="Also write every stem (and the click) with the same tempo and pitch."
    )

    @field_validator("gains")
    @classmethod
    def _bounded(cls, value: dict[Stem, float]) -> dict[Stem, float]:
        if any(not 0.0 <= gain <= 4.0 for gain in value.values()):
            raise ValueError("gains must be between 0 and 4")
        return value

    @field_validator("pans")
    @classmethod
    def _balanced(cls, value: dict[Stem, float]) -> dict[Stem, float]:
        if any(not -1.0 <= pan <= 1.0 for pan in value.values()):
            raise ValueError("pans must be between -1 and 1")
        return value


class RenderOut(BaseModel):
    path: str
    peak_dbfs: float = Field(description="Peak before protection (may be above 0 dBFS).")
    gain_db: float = Field(description="Gain applied to avoid clipping (0 or negative).")
