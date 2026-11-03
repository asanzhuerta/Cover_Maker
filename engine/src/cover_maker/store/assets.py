"""Content-addressed file store: every file is kept once, named by its SHA-256."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path

CHUNK = 1 << 20


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


class AssetStore:
    def __init__(self, root: Path, conn: sqlite3.Connection) -> None:
        self.root = root
        self.conn = conn

    def path_for(self, sha256: str) -> Path | None:
        row = self.conn.execute(
            "SELECT rel_path FROM assets WHERE sha256 = ?", (sha256,)
        ).fetchone()
        if row is None:
            return None
        path = self.root / row["rel_path"]
        return path if path.exists() else None

    def put(self, source: Path, kind: str, *, move: bool = False) -> str:
        """Store a file and return its hash. Identical content is stored once."""
        sha256 = sha256_file(source)
        if self.path_for(sha256) is not None:
            if move:
                source.unlink(missing_ok=True)
            return sha256
        rel = Path(sha256[:2]) / f"{sha256}{source.suffix.lower()}"
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if move:
            shutil.move(str(source), target)
        else:
            shutil.copy2(source, target)
        self.conn.execute(
            "INSERT OR REPLACE INTO assets (sha256, rel_path, kind, bytes) VALUES (?, ?, ?, ?)",
            (sha256, rel.as_posix(), kind, target.stat().st_size),
        )
        return sha256

    def require(self, sha256: str) -> Path:
        path = self.path_for(sha256)
        if path is None:
            raise FileNotFoundError(f"asset {sha256} is missing from the library")
        return path
