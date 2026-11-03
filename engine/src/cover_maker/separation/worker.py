# pyright: basic
# (PyTorch and audio-separator are untyped; this module runs only in the worker.)
"""Separation worker process (the only process that imports PyTorch).

Protocol over a multiprocessing pipe: the engine sends
``{"request": <SeparationRequest json>}`` and receives either
``{"ok": True, "result": <SeparationResult json>}`` or
``{"ok": False, "error": str, "oom": bool}``.
"""

from __future__ import annotations

import os
from multiprocessing.connection import Connection
from typing import Any

import psutil


def _lower_priority() -> None:
    try:
        process = psutil.Process()
        if os.name == "nt":
            process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)  # pyright: ignore[reportAttributeAccessIssue]
        else:
            process.nice(10)
    except (psutil.Error, AttributeError):
        pass


def main(conn: Connection, threads: int | None, low_priority: bool) -> None:
    if low_priority:
        _lower_priority()
    from .backends.audio_separator import AudioSeparatorBackend
    from .types import SeparationError, SeparationRequest

    if threads:
        import torch  # pyright: ignore[reportMissingImports]

        torch.set_num_threads(threads)
        torch.set_num_interop_threads(1)

    backend = AudioSeparatorBackend()
    while True:
        try:
            message: dict[str, Any] = conn.recv()
        except EOFError:
            return
        if message.get("op") == "stop":
            return
        try:
            request = SeparationRequest.model_validate_json(message["request"])
            result = backend.separate(request)
            conn.send({"ok": True, "result": result.model_dump_json()})
        except SeparationError as exc:
            conn.send({"ok": False, "error": str(exc), "oom": exc.oom})
        except Exception as exc:
            conn.send({"ok": False, "error": f"{type(exc).__name__}: {exc}", "oom": False})
