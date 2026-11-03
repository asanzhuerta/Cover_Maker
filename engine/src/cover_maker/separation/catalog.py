"""Model catalogue and licence acceptance."""

from __future__ import annotations

import hashlib
import sqlite3
from enum import StrEnum
from importlib import resources
from pathlib import Path

import yaml
from pydantic import BaseModel

from ..domain import Stem


class LicenceClass(StrEnum):
    PERMISSIVE = "permissive"
    DISPUTED = "disputed"
    NONE = "none"
    NON_COMMERCIAL = "non-commercial"
    COPYLEFT = "copyleft"


class ModelSpec(BaseModel):
    id: str
    name: str
    filename: str
    architecture: str
    stems: dict[str, Stem]
    size_mb: int
    vram_mb_fp16: int
    sha256: str | None = None
    licence_class: LicenceClass
    licence: str
    source: str
    recommended_for: list[str] = []

    @property
    def produces(self) -> set[Stem]:
        return set(self.stems.values())

    def notice(self) -> str:
        """Exact text the user accepts before download (hashed into the install record)."""
        return (
            f"{self.name} ({self.filename})\n"
            f"Licence class: {self.licence_class.value}\n"
            f"Licence: {self.licence}\n"
            f"Source: {self.source}\n"
            "Cover_Maker does not host or distribute these weights. You are responsible "
            "for complying with their licence and terms."
        )

    def notice_sha256(self) -> str:
        return hashlib.sha256(self.notice().encode("utf-8")).hexdigest()


class Catalog:
    def __init__(self, models: list[ModelSpec]) -> None:
        self.models = {model.id: model for model in models}

    @classmethod
    def load(cls, path: Path | None = None) -> Catalog:
        if path is None:
            text = resources.files("cover_maker").joinpath("data/catalog.yaml").read_text("utf-8")
        else:
            text = path.read_text("utf-8")
        raw = yaml.safe_load(text)
        return cls([ModelSpec.model_validate(item) for item in raw["models"]])

    def get(self, model_id: str) -> ModelSpec:
        try:
            return self.models[model_id]
        except KeyError:
            known = ", ".join(sorted(self.models))
            raise KeyError(f"unknown model '{model_id}' (known: {known})") from None


class Installs:
    """Which models the user installed, and the licence notice they accepted."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def is_installed(self, model: ModelSpec) -> bool:
        row = self.conn.execute(
            "SELECT licence_sha256 FROM model_installs WHERE model_id = ?", (model.id,)
        ).fetchone()
        return row is not None and row["licence_sha256"] == model.notice_sha256()

    def record(self, model: ModelSpec, sha256: str | None) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO model_installs (model_id, filename, sha256, licence_sha256) "
            "VALUES (?, ?, ?, ?)",
            (model.id, model.filename, sha256, model.notice_sha256()),
        )

    def remove(self, model_id: str) -> None:
        self.conn.execute("DELETE FROM model_installs WHERE model_id = ?", (model_id,))
