import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from cover_maker.api.app import create_app
from cover_maker.api.security import AccessPolicy

TOKEN = "t" * 43
HOST = "127.0.0.1:51234"


@pytest.fixture
def client() -> TestClient:
    policy = AccessPolicy(token=TOKEN, host=HOST)
    return TestClient(create_app(policy), base_url=f"http://{HOST}")


def auth(extra: dict[str, str] | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}", **(extra or {})}


def test_health_with_token(client: TestClient) -> None:
    response = client.get("/health", headers=auth())

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_missing_token_is_rejected(client: TestClient) -> None:
    assert client.get("/health").status_code == 401


def test_wrong_token_is_rejected(client: TestClient) -> None:
    response = client.get("/health", headers={"Authorization": "Bearer nope"})

    assert response.status_code == 401


def test_wrong_host_is_rejected(client: TestClient) -> None:
    response = client.get("/health", headers=auth({"Host": "evil.example:51234"}))

    assert response.status_code == 403


def test_foreign_origin_is_rejected(client: TestClient) -> None:
    response = client.get("/health", headers=auth({"Origin": "https://evil.example"}))

    assert response.status_code == 403


def test_tauri_origin_gets_cors_header(client: TestClient) -> None:
    response = client.get("/health", headers=auth({"Origin": "http://tauri.localhost"}))

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://tauri.localhost"


def test_preflight_allowed_without_token(client: TestClient) -> None:
    response = client.options("/health", headers={"Origin": "http://tauri.localhost"})

    assert response.status_code == 204


def test_websocket_requires_token_message(client: TestClient) -> None:
    with client.websocket_connect("/events", headers={"host": HOST}) as ws:
        ws.send_json({"token": TOKEN})
        first = ws.receive_json()

    assert first["type"] == "hello"


def test_websocket_bad_token_closes(client: TestClient) -> None:
    with client.websocket_connect("/events", headers={"host": HOST}) as ws:
        ws.send_json({"token": "bad"})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()

    assert closed.value.code == 4401
