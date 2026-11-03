from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from cover_maker.paths import Paths
from cover_maker.pipeline.runner import JobRunner
from cover_maker.separation.backends.fake import FakeBackend
from cover_maker.separation.catalog import Catalog, Installs
from cover_maker.separation.service import InProcessService
from cover_maker.store.db import connect


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    return Paths(tmp_path / "home").ensure()


def tone(seconds: float = 1.0, rate: int = 44_100, freq: float = 220.0) -> np.ndarray:
    t = np.arange(int(seconds * rate)) / rate
    mono = 0.4 * np.sin(2 * np.pi * freq * t)
    return np.stack([mono, 0.8 * mono], axis=1).astype(np.float32)


@pytest.fixture
def song(tmp_path: Path) -> Path:
    path = tmp_path / "input" / "My Song.wav"
    path.parent.mkdir(parents=True)
    sf.write(str(path), tone(), 44_100, subtype="FLOAT")
    return path


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def runner(paths: Paths, backend: FakeBackend) -> Iterator[JobRunner]:
    conn = connect(paths.db)
    catalog = Catalog.load()
    installs = Installs(conn)
    for model in catalog.models.values():
        installs.record(model, None)
    yield JobRunner(paths, conn, catalog, InProcessService(backend), use_gpu=True)
    conn.close()
