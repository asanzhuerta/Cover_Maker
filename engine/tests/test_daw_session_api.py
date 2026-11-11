"""DAW session API: POST /items/{id}/session writes the session folder."""

import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from cover_maker.api.engine import EngineService

from .test_api import client, fake_hardware, install_all, service, song  # noqa: F401
from .test_practice_api import _done_item


def test_session_export_writes_every_format_with_mixer_settings(
    client: TestClient,  # noqa: F811
    service: EngineService,  # noqa: F811
    song: Path,  # noqa: F811
    tmp_path: Path,
) -> None:
    item_id = _done_item(client, service, song, tmp_path / "out")
    client.put(f"/items/{item_id}/markers", json={"markers": [{"name": "Verse", "time": 0.25}]})

    response = client.post(
        f"/items/{item_id}/session",
        json={"tracks": {"guitar": {"gain": 0.5, "pan": -1, "muted": True}}, "residual": "drop"},
    )

    assert response.status_code == 200
    body = response.json()
    folder = Path(body["folder"])
    assert folder.parent == tmp_path / "out"
    assert folder.name.endswith(" - DAW session")
    assert set(body["projects"]) == {"reaper", "dawproject", "midi"}
    assert all(Path(path).is_file() for path in body["projects"].values())
    assert "Guitar" in body["tracks"]
    assert body["tracks"][-2:] == ["Residual", "Original mix"]
    rpp = Path(body["projects"]["reaper"]).read_text("utf-8")
    guitar = next(t for t in rpp.split("  <TRACK")[1:] if 'NAME "Guitar"' in t)
    assert "VOLPAN 0.5 -1 -1 -1 1" in guitar and "MUTESOLO 1 0 0" in guitar
    assert '"Verse"' in rpp
    with zipfile.ZipFile(body["projects"]["dawproject"]) as archive:
        assert '<Marker time="0.25" name="Verse" />' in archive.read("project.xml").decode()


def test_session_export_can_write_one_format(
    client: TestClient,  # noqa: F811
    service: EngineService,  # noqa: F811
    song: Path,  # noqa: F811
    tmp_path: Path,
) -> None:
    item_id = _done_item(client, service, song, tmp_path / "out")

    body = client.post(f"/items/{item_id}/session", json={"formats": ["dawproject"]}).json()

    assert list(body["projects"]) == ["dawproject"]
    assert not any(Path(body["folder"]).glob("*.RPP"))


def test_session_export_validates_and_needs_stems(client: TestClient) -> None:  # noqa: F811
    assert client.post("/items/999/session", json={}).status_code == 404
    bad_gain = client.post("/items/1/session", json={"tracks": {"vocals": {"gain": 9}}})
    assert bad_gain.status_code == 422
    assert client.post("/items/1/session", json={"formats": []}).status_code == 422
