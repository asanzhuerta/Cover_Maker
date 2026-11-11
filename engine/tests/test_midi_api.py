"""Audio-to-MIDI API (FR-MIDI-01): files per stem, cache and errors."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cover_maker.api.engine import EngineService
from cover_maker.pipeline import midi as midi_step

from .test_api import client, fake_hardware, install_all, service, song  # noqa: F401
from .test_practice_api import _done_item  # pyright: ignore[reportPrivateUsage]


def test_midi_files_are_named_like_the_stems_and_reused(
    client: TestClient,  # noqa: F811
    service: EngineService,  # noqa: F811
    song: Path,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = tmp_path / "out"
    item_id = _done_item(client, service, song, out)
    events: list[dict[str, Any]] = []
    service.bus.subscribe(events.append)
    calls: list[str] = []
    real_convert = midi_step.convert

    def counting(task: midi_step.MidiTask, plan: midi_step.MidiPlan, **kwargs: Any) -> Any:
        calls.append(task.stem)
        return real_convert(task, plan, **kwargs)

    monkeypatch.setattr(midi_step, "convert", counting)

    first = client.post(f"/items/{item_id}/midi", json={"stems": ["guitar", "drums"]})

    assert first.status_code == 200, first.text
    body = first.json()
    assert [f["stem"] for f in body["files"]] == ["guitar", "drums"]
    stem_exports = {p.stem.rsplit(" - ", 1)[0] for p in out.glob("*.wav")}
    for file in body["files"]:
        path = Path(file["path"])
        assert path.parent == out and path.suffix == ".mid"
        assert path.name.endswith(f" - {file['stem'].capitalize()}.mid")
        assert path.stem.rsplit(" - ", 1)[0] in stem_exports  # same song title as the stems
        assert path.read_bytes()[:4] == b"MThd"
        assert file["cached"] is False
    assert body["bpm"] > 0
    progress = [e for e in events if e["type"] == "midi.progress"]
    assert {e["stem"] for e in progress} == {"guitar", "drums"}
    assert all(e["item"] == item_id and e["total"] == 2 for e in progress)

    # The same request again reuses both files: nothing is transcribed twice.
    Path(body["files"][0]["path"]).unlink()
    again = client.post(f"/items/{item_id}/midi", json={"stems": ["drums", "guitar"]}).json()

    assert calls == ["guitar", "drums"]
    assert all(f["cached"] for f in again["files"])
    assert Path(body["files"][0]["path"]).exists()  # exported again from the library


def test_midi_without_a_beat_grid_uses_120_bpm(
    client: TestClient,  # noqa: F811
    service: EngineService,  # noqa: F811
    song: Path,  # noqa: F811
    tmp_path: Path,
) -> None:
    item_id = _done_item(client, service, song, tmp_path / "out")
    service.conn.execute("UPDATE analyses SET bpm = 0, beats_json = '[]', downbeats_json = '[]'")

    body = client.post(f"/items/{item_id}/midi", json={"stems": ["guitar"]}).json()

    assert body["bpm"] == 120.0 and body["tempo_from_analysis"] is False


def test_midi_errors(
    client: TestClient,  # noqa: F811
    service: EngineService,  # noqa: F811
    song: Path,  # noqa: F811
    tmp_path: Path,
) -> None:
    item_id = _done_item(client, service, song, tmp_path / "out")

    missing = client.post(f"/items/{item_id}/midi", json={"stems": ["lead_harp"]})
    assert missing.status_code == 400 and missing.json()["code"] == "stem_not_available"
    assert client.post(f"/items/{item_id}/midi", json={"stems": []}).status_code == 422
    assert client.post("/items/9999/midi", json={"stems": ["guitar"]}).status_code == 404
