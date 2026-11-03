from collections.abc import Iterator
from pathlib import Path

import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from cover_maker.api.app import create_app
from cover_maker.api.engine import EngineService
from cover_maker.api.security import AccessPolicy
from cover_maker.paths import Paths
from cover_maker.separation.backends.fake import FakeBackend
from cover_maker.separation.hardware import Gpu, Hardware
from cover_maker.separation.service import InProcessService

from .conftest import tone

TOKEN = "k" * 43
HOST = "127.0.0.1:50000"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def fake_hardware(_: Path) -> Hardware:
    gpu = Gpu("NVIDIA GeForce RTX 3050 Laptop GPU", 4096, 3500, 8.6, "596.21")
    return Hardware("Test CPU", 6, 12, 16.0, gpu, False, 100.0)


@pytest.fixture
def service(tmp_path: Path) -> Iterator[EngineService]:
    svc = EngineService(
        Paths(tmp_path / "home"),
        separation=InProcessService(FakeBackend()),
        hardware_probe=fake_hardware,
        demo=True,
    )
    yield svc
    svc.stop()


@pytest.fixture
def client(service: EngineService) -> TestClient:
    app = create_app(AccessPolicy(token=TOKEN, host=HOST), service)
    return TestClient(app, base_url=f"http://{HOST}", headers=AUTH)


@pytest.fixture
def song(tmp_path: Path) -> Path:
    path = tmp_path / "in" / "Track.wav"
    path.parent.mkdir()
    sf.write(str(path), tone(), 44_100, subtype="FLOAT")
    return path


def install_all(client: TestClient, service: EngineService) -> None:
    for model_id in service.catalog.models:
        assert (
            client.post(f"/models/{model_id}/install", json={"accept_licence": True}).status_code
            == 202
        )


def test_system_reports_tier_and_preset(client: TestClient) -> None:
    body = client.get("/system").json()

    assert body["tier"] == "4gb"
    assert body["recommended_preset"] == "balanced"
    assert body["demo"] is True


def test_models_need_licence_acceptance(client: TestClient) -> None:
    response = client.post("/models/bs-roformer-sw/install", json={"accept_licence": False})

    assert response.status_code == 400
    assert response.json()["code"] == "licence_not_accepted"


def test_job_requires_installed_models(client: TestClient, song: Path, tmp_path: Path) -> None:
    response = client.post(
        "/jobs",
        json={"inputs": [str(song)], "stems": ["vocals"], "output_dir": str(tmp_path / "out")},
    )

    assert response.status_code == 409
    assert response.json()["models"] == ["bs-roformer-sw"]


def test_online_job_requires_rights(
    client: TestClient, service: EngineService, tmp_path: Path
) -> None:
    install_all(client, service)

    response = client.post(
        "/jobs",
        json={
            "inputs": ["https://youtu.be/dQw4w9WgXcQ"],
            "stems": ["vocals"],
            "output_dir": str(tmp_path),
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "rights_required"


def test_job_runs_and_streams_events(
    client: TestClient, service: EngineService, song: Path, tmp_path: Path
) -> None:
    install_all(client, service)
    service.start()

    with client.websocket_connect("/events", headers={"host": HOST}) as ws:
        ws.send_json({"token": TOKEN})
        assert ws.receive_json()["type"] == "hello"
        created = client.post(
            "/jobs",
            json={
                "inputs": [str(song)],
                "stems": ["guitar"],
                "mode": "without",
                "output_dir": str(tmp_path / "out"),
            },
        )
        assert created.status_code == 201
        job_id = created.json()["job_id"]
        types: list[str] = []
        while "job.finished" not in types:
            types.append(ws.receive_json()["type"])

    assert "item.done" in types
    detail = client.get(f"/jobs/{job_id}").json()
    assert detail["status"] == "done"
    assert detail["item_list"][0]["outputs"]
    assert (tmp_path / "out" / "Track - without guitar.wav").exists()
    assert client.get("/jobs").json()[0]["id"] == job_id


def test_events_replay_after_reconnect(client: TestClient, service: EngineService) -> None:
    service.bus.emit("custom", value=1)
    service.bus.emit("custom", value=2)

    with client.websocket_connect("/events", headers={"host": HOST}) as ws:
        ws.send_json({"token": TOKEN, "since": 1})
        assert ws.receive_json()["type"] == "hello"
        replayed = ws.receive_json()

    assert replayed["value"] == 2


def test_library_folder_flow(client: TestClient, song: Path) -> None:
    created = client.post("/library/folders", json={"path": str(song.parent)})
    collection = created.json()["id"]

    sync = client.post(f"/library/{collection}/sync").json()
    items = client.get(f"/library/{collection}/items").json()

    assert sync["added"] == 1
    assert items[0]["input"] == str(song)
    assert client.get("/library").json()[0]["items"] == 1


def test_match_correction(client: TestClient, song: Path, tmp_path: Path) -> None:
    playlist = tmp_path / "list.m3u"
    playlist.write_text("#EXTINF:1,Nobody - Missing\nx\n", "utf-8")
    [created] = client.post(
        "/library/imports", json={"file": str(playlist), "search": [str(song.parent)]}
    ).json()
    client.post(f"/library/{created['id']}/sync")
    item = client.get(f"/library/{created['id']}/items").json()[0]

    assert (
        client.put(f"/library/items/{item['id']}/match", json={"path": str(song)}).status_code
        == 204
    )
    assert client.get(f"/library/{created['id']}/items").json()[0]["status"] == "ready"


def test_openapi_lists_endpoints(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert {"/jobs", "/models", "/system", "/library"} <= set(paths)


def test_openapi_offers_every_export_mode(client: TestClient) -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]

    assert schemas["Mode"]["enum"] == ["extract", "without", "both"]
