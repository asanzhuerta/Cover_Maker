import json
import zipfile
from pathlib import Path

import pytest

from cover_maker import diagnostics
from cover_maker.paths import Paths
from cover_maker.store.db import connect


def test_redact_removes_folders_links_and_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USERPROFILE", r"C:\Users\Alice")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\Alice\AppData\Local")
    text = (
        r"failed C:\Users\Alice\Music\Song.flac and C:\Users\Alice\AppData\Local\Cover_Maker\db "
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ Bearer abcdefghijklmnopqrstuvwxyz012345"
    )
    out = diagnostics.redact(text)
    assert "Alice" not in out
    assert r"%USERPROFILE%\Music\Song.flac" in out
    assert r"%LOCALAPPDATA%\Cover_Maker" in out
    assert "dQw4w9WgXcQ" not in out and "https://www.youtube.com/…" in out
    assert "abcdefghijklmnop" not in out


def test_report_is_redacted_and_has_no_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    paths = Paths(tmp_path / "home").ensure()
    conn = connect(paths.db)
    conn.execute("INSERT INTO jobs (spec_json, status, error) VALUES ('{}', 'failed', 'boom')")
    conn.execute(
        "INSERT INTO job_items (job_id, ordinal, input_path, status, error) "
        "VALUES (1, 0, ?, 'failed', ?)",
        (str(tmp_path / "Music" / "Song.flac"), f"input file not found: {tmp_path}"),
    )
    (paths.logs / diagnostics.LOG_FILE).write_text(f"warning at {tmp_path}\n", "utf-8")

    report = diagnostics.build(conn, paths, {"cpu": "Test CPU", "data_dir": str(paths.home)})

    with zipfile.ZipFile(report) as archive:
        names = set(archive.namelist())
        body = {name: archive.read(name).decode("utf-8") for name in names}
    assert names == {"report.json", "engine.log", "README.txt"}
    assert all(str(tmp_path) not in text for text in body.values())
    data = json.loads(body["report.json"])
    assert data["jobs"][0]["items"][0]["input"] == "Song.flac"
    assert data["system"]["cpu"] == "Test CPU"
