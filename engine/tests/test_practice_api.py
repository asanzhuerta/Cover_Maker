"""Practice API (M14): stored analysis and section markers."""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from cover_maker.api.engine import EngineService
from cover_maker.store import analyses

from .test_api import client, fake_hardware, install_all, service, song  # noqa: F401


def _done_item(client: TestClient, service: EngineService, song: Path, out: Path) -> int:  # noqa: F811
    install_all(client, service)
    service.start()
    created = client.post(
        "/jobs", json={"inputs": [str(song)], "stems": ["guitar"], "output_dir": str(out)}
    ).json()
    detail: dict[str, object] = {}
    for _ in range(1200):
        detail = client.get(f"/jobs/{created['job_id']}").json()
        if detail["status"] in ("done", "failed"):
            break
        time.sleep(0.05)
    assert detail["status"] == "done"
    return int(detail["item_list"][0]["id"])  # type: ignore[index]


def test_job_stores_the_analysis_once_and_serves_it(
    client: TestClient,  # noqa: F811
    service: EngineService,  # noqa: F811
    song: Path,  # noqa: F811
    tmp_path: Path,
) -> None:
    item_id = _done_item(client, service, song, tmp_path / "out")

    first = client.get(f"/items/{item_id}/analysis")

    assert first.status_code == 200
    body = first.json()
    assert body["mode"] in ("major", "minor")
    assert -50 <= body["tuning_cents"] < 50
    assert body["markers"] == []
    rows = service.conn.execute("SELECT COUNT(*) FROM analyses WHERE mix_sha = ?", (body["mix"],))
    assert rows.fetchone()[0] == 1
    # Asking again reads the stored row; nothing is recomputed or duplicated.
    assert client.get(f"/items/{item_id}/analysis").json() == body
    stored = analyses.load(service.conn, body["mix"])
    assert stored is not None and stored.bpm == body["bpm"]


def test_analysis_is_computed_on_demand_for_older_items(
    client: TestClient,  # noqa: F811
    service: EngineService,  # noqa: F811
    song: Path,  # noqa: F811
    tmp_path: Path,
) -> None:
    item_id = _done_item(client, service, song, tmp_path / "out")
    service.conn.execute("DELETE FROM analyses")

    body = client.get(f"/items/{item_id}/analysis").json()

    assert analyses.load(service.conn, body["mix"]) is not None


def test_markers_are_saved_sorted_and_validated(
    client: TestClient,  # noqa: F811
    service: EngineService,  # noqa: F811
    song: Path,  # noqa: F811
    tmp_path: Path,
) -> None:
    item_id = _done_item(client, service, song, tmp_path / "out")

    saved = client.put(
        f"/items/{item_id}/markers",
        json={"markers": [{"name": "Chorus", "time": 1.5}, {"name": " Verse ", "time": 0.2}]},
    )

    assert saved.json() == [{"name": "Verse", "time": 0.2}, {"name": "Chorus", "time": 1.5}]
    assert client.get(f"/items/{item_id}/analysis").json()["markers"] == saved.json()
    bad = client.put(f"/items/{item_id}/markers", json={"markers": [{"name": "", "time": -1}]})
    assert bad.status_code in (400, 422)
    assert client.put("/items/999/markers", json={"markers": []}).status_code == 404
    assert client.get("/items/999/analysis").status_code == 404
