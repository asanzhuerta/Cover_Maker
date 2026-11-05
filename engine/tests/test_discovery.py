"""DAW discovery file and client tokens (ADR-008)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cover_maker.api import discovery
from cover_maker.api.app import create_app
from cover_maker.api.security import AccessPolicy

TOKEN = "s" * 64
CLIENT = "c" * 64
HOST = "127.0.0.1:51235"


def test_write_read_and_remove(tmp_path: Path) -> None:
    info = discovery.Discovery(port=51235, token=CLIENT, pid=4242, version="1.0.0")

    target = discovery.write(tmp_path, info)

    assert target == tmp_path / "run" / "engine.json"
    assert json.loads(target.read_text(encoding="utf-8"))["schema"] == discovery.SCHEMA
    assert discovery.read(tmp_path) == info
    assert not list((tmp_path / "run").glob("*.tmp"))
    discovery.remove(tmp_path, pid=4242)
    assert discovery.read(tmp_path) is None


def test_remove_keeps_a_newer_engines_file(tmp_path: Path) -> None:
    discovery.write(tmp_path, discovery.Discovery(port=1, token=CLIENT, pid=2, version="x"))

    discovery.remove(tmp_path, pid=1)

    assert discovery.read(tmp_path) is not None


def test_malformed_file_reads_as_missing(tmp_path: Path) -> None:
    (tmp_path / "run").mkdir()
    (tmp_path / "run" / "engine.json").write_text("{not json", encoding="utf-8")

    assert discovery.read(tmp_path) is None


@pytest.mark.parametrize(("value", "expected"), [("0", False), ("off", False), ("1", True)])
def test_access_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    monkeypatch.setenv(discovery.ACCESS_ENV, value)

    assert discovery.enabled() is expected


def test_client_token_is_distinct_and_random() -> None:
    first, second = discovery.new_client_token(), discovery.new_client_token()

    assert len(first) == 64 and first != second


def test_client_token_is_accepted_but_host_still_checked() -> None:
    policy = AccessPolicy(token=TOKEN, host=HOST, client_tokens=frozenset({CLIENT}))
    client = TestClient(create_app(policy), base_url=f"http://{HOST}")
    auth = {"Authorization": f"Bearer {CLIENT}"}

    assert client.get("/health", headers=auth).status_code == 200
    assert client.get("/health", headers={**auth, "Host": "evil.example"}).status_code == 403
    origin = {**auth, "Origin": "https://evil.example"}
    assert client.get("/health", headers=origin).status_code == 403
    wrong = {"Authorization": f"Bearer {'x' * 64}"}
    assert client.get("/health", headers=wrong).status_code == 401


def test_no_client_tokens_by_default() -> None:
    policy = AccessPolicy(token=TOKEN, host=HOST)

    assert not policy.token_ok(CLIENT)
    assert policy.token_ok(TOKEN)
