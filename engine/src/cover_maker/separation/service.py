"""Separation service: worker supervision and the out-of-memory fallback ladder."""

from __future__ import annotations

import contextlib
import multiprocessing
import os
import threading
from collections.abc import Callable
from typing import Any, Protocol

from .types import (
    Backend,
    Cancelled,
    Device,
    Precision,
    SeparationError,
    SeparationRequest,
    SeparationResult,
)

# Tried in order on the GPU until one fits in memory (measured in M1: SW fits
# 4 GB at the default chunk in fp16; smaller chunks are the safety net).
GPU_LADDER: tuple[tuple[Precision, float | None], ...] = (
    ("fp16", None),
    ("fp16", 8.0),
    ("fp16", 4.0),
)
CPU_STEP: tuple[Precision, float | None] = ("fp32", None)


class NeedsCpuFallback(SeparationError):
    """The GPU ran out of memory on every step; the user must allow CPU mode."""


class SeparationService(Protocol):
    def separate(self, request: SeparationRequest) -> SeparationResult: ...
    def cancel(self) -> None: ...
    def close(self) -> None: ...


def with_ladder(
    service: SeparationService,
    request: SeparationRequest,
    *,
    use_gpu: bool,
    allow_cpu: bool,
    on_retry: Callable[[str], None] | None = None,
) -> SeparationResult:
    """Run ``request`` stepping down precision/chunk on OOM, then CPU if allowed."""
    steps: list[tuple[Device, Precision, float | None]] = []
    if use_gpu:
        for precision, chunk in GPU_LADDER:
            steps.append(("gpu", precision, chunk))
    if allow_cpu or not use_gpu:
        steps.append(("cpu", CPU_STEP[0], CPU_STEP[1]))
    last: SeparationError | None = None
    for device, precision, chunk in steps:
        attempt = request.model_copy(
            update={"device": device, "precision": precision, "chunk_s": chunk}
        )
        try:
            return service.separate(attempt)
        except SeparationError as exc:
            if not exc.oom:
                raise
            last = exc
            if on_retry:
                on_retry(
                    f"out of memory on {device} ({precision}, chunk {chunk or 'default'}); retrying"
                )
    raise NeedsCpuFallback(
        "The GPU ran out of memory with every setting. Allow CPU mode to continue (much slower).",
        oom=True,
    ) from last


class InProcessService:
    """Runs a backend in the current process (tests and demo mode)."""

    def __init__(self, backend: Backend) -> None:
        self.backend = backend

    def separate(self, request: SeparationRequest) -> SeparationResult:
        return self.backend.separate(request)

    def cancel(self) -> None:
        pass

    def close(self) -> None:
        pass


class WorkerService:
    """Supervises long-lived worker processes, one per device kind.

    Killing a worker is the only reliable way to cancel inference and to free
    all VRAM, so :meth:`cancel` terminates it; it is restarted on next use.
    """

    def __init__(self, *, threads: int | None = None, low_priority: bool = True) -> None:
        self.threads = threads
        self.low_priority = low_priority
        self._workers: dict[Device, tuple[Any, Any]] = {}
        self._lock = threading.Lock()
        self._cancelled = threading.Event()

    def _worker(self, device: Device) -> tuple[Any, Any]:
        existing = self._workers.get(device)
        if existing and existing[0].is_alive():
            return existing
        from . import worker

        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        # The spawned process copies the environment at start: hide the GPU from CPU workers.
        saved = os.environ.get("CUDA_VISIBLE_DEVICES")
        if device == "cpu":
            os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # an empty value does not hide the GPU on Windows
        try:
            process = context.Process(
                target=worker.main, args=(child, self.threads, self.low_priority), daemon=True
            )
            process.start()
        finally:
            if saved is None:
                os.environ.pop("CUDA_VISIBLE_DEVICES", None)
            else:
                os.environ["CUDA_VISIBLE_DEVICES"] = saved
        child.close()
        self._workers[device] = (process, parent)
        return process, parent

    def separate(self, request: SeparationRequest) -> SeparationResult:
        with self._lock:
            self._cancelled.clear()
            process, conn = self._worker(request.device)
            conn.send({"op": "separate", "request": request.model_dump_json()})
            while not conn.poll(0.2):
                if self._cancelled.is_set():
                    raise Cancelled("separation cancelled")
                if not process.is_alive():
                    self._workers.pop(request.device, None)
                    raise SeparationError(f"separation worker exited (code {process.exitcode})")
            reply = conn.recv()
        if reply["ok"]:
            return SeparationResult.model_validate_json(reply["result"])
        raise SeparationError(reply["error"], oom=bool(reply.get("oom")))

    def cancel(self) -> None:
        self._cancelled.set()
        for device, (process, _) in list(self._workers.items()):
            process.kill()
            process.join(timeout=5)
            self._workers.pop(device, None)

    def close(self) -> None:
        for process, conn in self._workers.values():
            with contextlib.suppress(BrokenPipeError, OSError):
                conn.send({"op": "stop"})
            process.join(timeout=5)
            if process.is_alive():
                process.kill()
        self._workers.clear()
