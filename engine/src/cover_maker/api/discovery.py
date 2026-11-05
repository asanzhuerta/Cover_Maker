"""Let DAW plugins and scripts find the running engine (ADR-008).

While the engine runs it writes ``<home>/run/engine.json`` with its port, PID,
version and a *client token*. The client token is separate from the session
token of the desktop shell, which never touches the disk: revoking DAW access
(``COVER_MAKER_DAW_ACCESS=0``) or a leaked file never exposes the shell's
session. The ``run`` folder is restricted to the current user (inheritance is
removed and only the user's SID is granted access), the file is replaced
atomically and deleted when the engine stops. Clients must check that the PID
is alive and call ``/health`` with the token before trusting the file; the
Host/Origin checks of ADR-004 still apply to them.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import secrets
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ACCESS_ENV = "COVER_MAKER_DAW_ACCESS"
FILE_NAME = "engine.json"
SCHEMA = 1

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Discovery:
    port: int
    token: str
    pid: int
    version: str
    host: str = "127.0.0.1"
    schema: int = SCHEMA


def enabled() -> bool:
    """DAW access is on unless ``COVER_MAKER_DAW_ACCESS`` is 0/false/off."""
    return os.environ.get(ACCESS_ENV, "1").strip().lower() not in ("0", "false", "off", "no")


def new_client_token() -> str:
    return secrets.token_hex(32)


def run_dir(home: Path) -> Path:
    return home / "run"


def _system32(tool: str) -> str:
    root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return str(Path(root) / "System32" / tool)


def _current_sid() -> str | None:
    try:
        out = subprocess.run(
            [_system32("whoami.exe"), "/user", "/fo", "csv", "/nh"],
            capture_output=True, text=True, check=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None
    parts = [p.strip().strip('"') for p in out.strip().split(",")]
    return parts[-1] if parts and parts[-1].startswith("S-") else None


def restrict_to_user(folder: Path) -> bool:
    """Grant only the current user access to ``folder`` (and what it will hold).

    Best effort: ``%LOCALAPPDATA%`` is already private to the user, this also
    drops the inherited SYSTEM/Administrators entries. Returns True on success.
    """
    if sys.platform != "win32":
        with contextlib.suppress(OSError):
            folder.chmod(0o700)
            return True
        return False
    sid = _current_sid()
    if sid is None:
        return False
    try:
        subprocess.run(
            [_system32("icacls.exe"), str(folder), "/inheritance:r", "/grant:r",
             f"*{sid}:(OI)(CI)F"],
            capture_output=True, check=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("could not restrict %s to the current user: %s", folder, exc)
        return False
    return True


def write(home: Path, info: Discovery) -> Path:
    """Write the discovery file atomically and return its path."""
    folder = run_dir(home)
    folder.mkdir(parents=True, exist_ok=True)
    restrict_to_user(folder)
    target = folder / FILE_NAME
    tmp = folder / f"{FILE_NAME}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(asdict(info), indent=2), encoding="utf-8")
    os.replace(tmp, target)
    return target


def remove(home: Path, pid: int) -> None:
    """Delete the discovery file if it still belongs to this engine."""
    target = run_dir(home) / FILE_NAME
    current = read(home)
    if current is not None and current.pid != pid:
        return
    with contextlib.suppress(OSError):
        target.unlink()


def read(home: Path) -> Discovery | None:
    """Parse the discovery file; None when missing or malformed."""
    try:
        data = json.loads((run_dir(home) / FILE_NAME).read_text(encoding="utf-8"))
        return Discovery(
            port=int(data["port"]), token=str(data["token"]), pid=int(data["pid"]),
            version=str(data["version"]), host=str(data.get("host", "127.0.0.1")),
            schema=int(data.get("schema", SCHEMA)),
        )  # fmt: skip
    except (OSError, ValueError, KeyError, TypeError):
        return None
