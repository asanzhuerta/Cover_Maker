"""Engine service behind the local API.

The API thread (asyncio) and a single job thread use separate SQLite
connections. Jobs are queued and run one at a time on the job thread; events
from the runner are kept in a bounded buffer (for reconnecting clients) and
pushed to WebSocket subscribers through their event loop.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..domain import JobSpec
from ..library.collections import Library
from ..paths import Paths
from ..pipeline.events import Event, EventBus
from ..pipeline.runner import JobRunner
from ..separation.catalog import Catalog, Installs
from ..separation.hardware import Hardware, Tier, detect
from ..separation.service import InProcessService, SeparationService, WorkerService
from ..store.db import connect

BUFFER_SIZE = 1000


@dataclass
class Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[Event] = field(default_factory=lambda: asyncio.Queue[Event]())


class EventHub:
    """Fans runner events out to WebSocket clients and keeps recent history."""

    def __init__(self, bus: EventBus) -> None:
        self._lock = threading.Lock()
        self._history: deque[Event] = deque(maxlen=BUFFER_SIZE)
        self._subscribers: list[Subscriber] = []
        bus.subscribe(self._publish)

    def _publish(self, event: Event) -> None:
        with self._lock:
            self._history.append(event)
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            subscriber.loop.call_soon_threadsafe(subscriber.queue.put_nowait, event)

    def subscribe(
        self, loop: asyncio.AbstractEventLoop, since: int | None
    ) -> tuple[Subscriber, list[Event]]:
        subscriber = Subscriber(loop)
        with self._lock:
            missed = [e for e in self._history if since is not None and e["seq"] > since]
            self._subscribers.append(subscriber)
        return subscriber, missed

    def unsubscribe(self, subscriber: Subscriber) -> None:
        with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)


class EngineService:
    def __init__(
        self,
        paths: Paths,
        *,
        separation: SeparationService | None = None,
        hardware_probe: Callable[[Path], Hardware] = detect,
        demo: bool = False,
    ) -> None:
        self.paths = paths.ensure()
        self.catalog = Catalog.load()
        self.bus = EventBus()
        self.events = EventHub(self.bus)
        self.demo = demo
        self.hardware_probe = hardware_probe
        self._hardware: Hardware | None = None

        self.conn = connect(paths.db)  # used by the API thread only
        self.library = Library(self.conn)
        self.installs = Installs(self.conn)
        # Read-side runner on the API connection (submit, list, retry; no execution).
        self.jobs = JobRunner(
            paths, self.conn, self.catalog, InProcessService(_NoBackend()), self.bus
        )

        self._separation = separation or WorkerService()
        self._queue: queue.Queue[int | None] = queue.Queue()
        self._active: JobRunner | None = None
        self._thread = threading.Thread(target=self._work, name="cover-maker-jobs", daemon=True)
        self._started = False

    # ------------------------------------------------------------ lifecycle

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread.start()
        # Resume work interrupted by a crash or a closed app.
        self.jobs.recover()
        for row in self.jobs.jobs():
            if row["status"] in ("pending", "running"):
                self._queue.put(int(row["id"]))

    def stop(self) -> None:
        if self._active:
            self._active.cancel()
        self._queue.put(None)
        if self._started:
            self._thread.join(timeout=10)
        self._separation.close()

    def _work(self) -> None:
        conn = connect(self.paths.db)  # the job thread's own connection
        runner = JobRunner(
            self.paths, conn, self.catalog, self._separation, self.bus, use_gpu=self._use_gpu()
        )
        while True:
            job_id = self._queue.get()
            if job_id is None:
                return
            self._active = runner
            try:
                runner.run(job_id)
            except Exception as exc:  # e.g. a model removed after submission
                conn.execute(
                    "UPDATE jobs SET status = 'failed', error = ? WHERE id = ?", (str(exc), job_id)
                )
                self.bus.emit("job.finished", job=job_id, status="failed", error=str(exc))
            finally:
                self._active = None

    # ------------------------------------------------------------ jobs

    def hardware(self, refresh: bool = False) -> Hardware:
        if self._hardware is None or refresh:
            self._hardware = self.hardware_probe(self.paths.home)
        return self._hardware

    def _use_gpu(self) -> bool:
        return self.hardware().tier is not Tier.CPU

    def submit(self, spec: JobSpec) -> int:
        job_id = self.jobs.submit(spec)
        self._queue.put(job_id)
        return job_id

    def cancel(self) -> None:
        if self._active:
            self._active.cancel()

    def pause(self) -> None:
        if self._active:
            self._active.pause()

    @property
    def busy(self) -> bool:
        """True while a job runs or waits in the queue."""
        return self._active is not None or not self._queue.empty()

    def resume(self, job_id: int) -> None:
        self._queue.put(job_id)

    def retry(self, job_id: int) -> int:
        count = self.jobs.retry(job_id)
        self._queue.put(job_id)
        return count

    def snapshot(self) -> dict[str, Any]:
        return {"jobs": [dict(row) for row in self.jobs.jobs(20)]}


class _NoBackend:
    def separate(self, request: Any) -> Any:  # pragma: no cover - never called
        raise RuntimeError("the API connection never runs separations")
