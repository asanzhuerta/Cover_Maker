"""Diagnostic report: a zip the user can attach to a bug report.

It holds versions, hardware, the runtime state, installed models, recent jobs
and the engine log. Personal data is redacted before it is written: the
user's folders become placeholders, links keep only their site and tokens are
removed. Audio and model files are never included.
"""

from __future__ import annotations

import json
import os
import platform
import re
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from . import __version__
from .paths import Paths

LOG_FILE = "engine.log"
MAX_LOG_BYTES = 512 * 1024
_URL = re.compile(r"(https?://[^/\s\"']+)[^\s\"']*")
_BEARER = re.compile(r"(?i)(bearer\s+|token[\"'=:\s]+)[A-Za-z0-9_\-.]{16,}")


def _placeholders() -> list[tuple[str, str]]:
    """User-specific folders and their placeholder, longest first."""
    pairs: list[tuple[str, str]] = []
    for env, label in (("LOCALAPPDATA", "%LOCALAPPDATA%"), ("APPDATA", "%APPDATA%"),
                       ("USERPROFILE", "%USERPROFILE%"), ("TEMP", "%TEMP%")):  # fmt: skip
        value = os.environ.get(env)
        if value:
            pairs.append((value, label))
    pairs.append((str(Path.home()), "%USERPROFILE%"))
    return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


def redact(text: str) -> str:
    """Remove personal folders, link paths and tokens from a text."""
    for value, label in _placeholders():
        for variant in {value, value.replace("\\", "/"), value.replace("\\", "\\\\")}:
            text = re.sub(re.escape(variant), lambda _, label=label: label, text, flags=re.I)
    text = _URL.sub(lambda m: f"{m.group(1)}/…", text)
    return _BEARER.sub(lambda m: f"{m.group(1)}[redacted]", text)


def _jobs(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for job in conn.execute(
        "SELECT id, status, error, created_at FROM jobs ORDER BY id DESC LIMIT ?", (limit,)
    ):
        items = [
            {
                "status": item["status"],
                "step": item["current_step"],
                "error": item["error"],
                # The file name only: enough to tell items apart.
                "input": Path(str(item["input_path"])).name,
            }
            for item in conn.execute(
                "SELECT status, current_step, error, input_path FROM job_items "
                "WHERE job_id = ? ORDER BY ordinal",
                (job["id"],),
            )
        ]
        jobs.append({**dict(job), "items": items})
    return jobs


def _runtime_state(paths: Paths) -> Any:
    state = paths.home / "runtime" / "state.json"
    try:
        return json.loads(state.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _log_tail(paths: Paths) -> str:
    log = paths.logs / LOG_FILE
    if not log.exists():
        return ""
    data = log.read_bytes()[-MAX_LOG_BYTES:]
    return data.decode("utf-8", errors="replace")


def build(conn: sqlite3.Connection, paths: Paths, system: dict[str, Any]) -> Path:
    """Write the report into the logs folder and return its path."""
    paths.logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = paths.logs / f"cover-maker-diagnostics-{stamp}.zip"
    report = {
        "engine": __version__,
        "python": sys.version,
        "platform": platform.platform(),
        "system": system,
        "runtime_state": _runtime_state(paths),
        "installed_models": [
            row["model_id"] for row in conn.execute("SELECT model_id FROM model_installs")
        ],
        "jobs": _jobs(conn),
    }
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("report.json", redact(json.dumps(report, indent=2, default=str)))
        archive.writestr(LOG_FILE, redact(_log_tail(paths)))
        archive.writestr(
            "README.txt",
            "Cover_Maker diagnostic report. Personal folders, link paths and tokens are\n"
            "redacted. No audio or model files are included.\n",
        )
    return target
