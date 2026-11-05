"""Preset tuning from measured runs (M10).

Every separation attempt is recorded with its model, device, precision, chunk,
the song length and the time it took, or that it ran out of memory. Two things
are learnt from that history, per machine:

* **Start rung.** GPU settings of the VRAM ladder (ADR-002) that ran out of
  memory the last :data:`OOM_STREAK` times for a model are skipped, so a 4 GB
  card does not lose a minute on fp16/default chunk before every song. The
  smallest GPU setting is always tried.
* **Auto preset.** On a GPU, ``auto`` normally means Balanced. If Balanced's
  models were measured slower than :data:`SLOW_RTF` times the song length,
  ``auto`` picks Fast instead. Auto never escalates to Max on its own.
"""

from __future__ import annotations

import sqlite3
import statistics
from collections.abc import Iterable, Mapping, Sequence

from ..domain import Preset

OOM_STREAK = 2
WINDOW = 5
SLOW_RTF = 1.5


class Tuning:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def record(
        self, model_id: str, device: str, precision: str, chunk_s: float | None,
        audio_s: float, wall_s: float | None, oom: bool,
    ) -> None:  # fmt: skip
        self.conn.execute(
            "INSERT INTO separation_runs (model_id, device, precision, chunk_s, audio_s, wall_s, oom)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (model_id, device, precision, chunk_s, audio_s, wall_s, int(oom)),
        )

    def first_gpu_rung(self, model_id: str, ladder: Sequence[tuple[str, float | None]]) -> int:
        """Index of the first GPU setting worth trying for ``model_id``."""
        for index, (precision, chunk) in enumerate(ladder):
            rows = self.conn.execute(
                "SELECT oom FROM separation_runs WHERE model_id = ? AND device = 'gpu'"
                " AND precision = ? AND chunk_s IS ? ORDER BY id DESC LIMIT ?",
                (model_id, precision, chunk, OOM_STREAK),
            ).fetchall()
            if len(rows) < OOM_STREAK or not all(r["oom"] for r in rows):
                return index
        return max(len(ladder) - 1, 0)

    def realtime_factor(self, model_id: str, device: str = "gpu") -> float | None:
        """Median seconds of work per second of audio over the latest successful runs."""
        rows = self.conn.execute(
            "SELECT wall_s / audio_s AS rtf FROM separation_runs WHERE model_id = ?"
            " AND device = ? AND oom = 0 AND audio_s > 0 AND wall_s IS NOT NULL"
            " ORDER BY id DESC LIMIT ?",
            (model_id, device, WINDOW),
        ).fetchall()
        return statistics.median(r["rtf"] for r in rows) if rows else None

    def slowest(self, models: Iterable[str], device: str = "gpu") -> float | None:
        known = [f for m in models if (f := self.realtime_factor(m, device)) is not None]
        return max(known) if known else None

    def auto_preset(self, tier_is_gpu: bool, models: Mapping[Preset, set[str]]) -> Preset:
        if not tier_is_gpu:
            return Preset.FAST
        balanced = self.slowest(models.get(Preset.BALANCED, set()))
        if balanced is not None and balanced > SLOW_RTF:
            return Preset.FAST
        return Preset.BALANCED

    def summary(self, models: Mapping[Preset, set[str]]) -> dict[str, float | None]:
        """Measured GPU (or CPU for Fast) speed per preset, for the System page."""
        out: dict[str, float | None] = {}
        for preset, ids in models.items():
            gpu = self.slowest(ids, "gpu")
            out[preset.value] = gpu if gpu is not None else self.slowest(ids, "cpu")
        return out
