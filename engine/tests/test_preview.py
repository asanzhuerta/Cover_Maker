import time
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from cover_maker.api.engine import EngineService
from cover_maker.audio.peaks import compute_peaks

from .conftest import tone
from .test_api import client, fake_hardware, install_all, service, song  # noqa: F401


def test_peaks_shape_and_range(tmp_path: Path) -> None:
    path = tmp_path / "a.wav"
    sf.write(str(path), tone(1.0), 44_100, subtype="FLOAT")

    peaks = compute_peaks(path, 100)

    assert len(peaks) == 100
    values = np.array(peaks)
    assert values[:, 0].min() >= -1 and values[:, 1].max() <= 1
    assert (values[:, 0] <= values[:, 1]).all()


def test_preview_lists_all_stems_and_serves_audio(
    client: TestClient,  # noqa: F811
    service: EngineService,  # noqa: F811
    song: Path,  # noqa: F811
    tmp_path: Path,
) -> None:
    install_all(client, service)
    service.start()
    created = client.post(
        "/jobs",
        json={"inputs": [str(song)], "stems": ["guitar"], "output_dir": str(tmp_path / "out")},
    ).json()
    detail: dict[str, object] = {}
    for _ in range(200):
        detail = client.get(f"/jobs/{created['job_id']}").json()
        if detail["status"] in ("done", "failed"):
            break
        import time

        time.sleep(0.05)
    item_id = detail["item_list"][0]["id"]  # type: ignore[index]

    preview = client.get(f"/items/{item_id}/preview").json()

    assert set(preview["stems"]) == {"vocals", "guitar", "drums", "bass", "piano", "other"}
    audio = client.get(f"/assets/{preview['mix']}")
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/wav"
    peaks = client.get(f"/assets/{preview['stems']['guitar']}/peaks", params={"points": 64}).json()
    assert len(peaks["peaks"]) == 64


def test_assets_reject_unknown_and_malformed_ids(client: TestClient) -> None:  # noqa: F811
    assert client.get("/assets/" + "0" * 64).status_code == 404
    assert client.get("/assets/..%2F..%2Fsecret").status_code in (400, 404)
    assert client.get("/items/999/preview").status_code == 404


def _finished_item(client: TestClient, service: EngineService, song: Path, out: Path) -> int:  # noqa: F811
    install_all(client, service)
    service.start()
    created = client.post(
        "/jobs",
        json={
            "inputs": [str(song)],
            "stems": ["guitar"],
            "mode": "without",
            "output_dir": str(out),
        },
    ).json()
    detail: dict[str, object] = {}
    for _ in range(200):
        detail = client.get(f"/jobs/{created['job_id']}").json()
        if detail["status"] in ("done", "failed"):
            break
        time.sleep(0.05)
    return detail["item_list"][0]["id"]  # type: ignore[index]


def test_render_writes_the_custom_mix_without_overwriting(
    client: TestClient,  # noqa: F811
    service: EngineService,  # noqa: F811
    song: Path,  # noqa: F811
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    item_id = _finished_item(client, service, song, out)
    preview = client.get(f"/items/{item_id}/preview").json()
    title = preview["title"]
    assert title == song.stem

    first = client.post(
        f"/items/{item_id}/render", json={"gains": {"guitar": 0.0}, "residual": "keep"}
    )
    second = client.post(f"/items/{item_id}/render", json={"output_format": "flac"})
    third = client.post(f"/items/{item_id}/render", json={})

    assert first.status_code == 200, first.text
    assert Path(first.json()["path"]) == out / f"{title} - custom mix.wav"
    assert Path(second.json()["path"]) == out / f"{title} - custom mix.flac"
    assert Path(third.json()["path"]) == out / f"{title} - custom mix (2).wav"
    # Muting guitar with keep is exactly the regular "without guitar" export.
    exported, _ = sf.read(str(next(out.glob("* - without guitar.wav"))))
    rendered, _ = sf.read(first.json()["path"])
    np.testing.assert_allclose(rendered, exported, atol=1e-4)


def test_render_rejects_bad_requests(client: TestClient) -> None:  # noqa: F811
    assert client.post("/items/999/render", json={}).status_code == 404
    assert client.post("/items/1/render", json={"gains": {"guitar": 9}}).status_code in (400, 422)
    assert client.post("/items/1/render", json={"gains": {"kazoo": 1}}).status_code in (400, 422)
