"""In-process event bus: the CLI renders events with Rich, the API forwards them."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

Event = dict[str, Any]
Listener = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._listeners: list[Listener] = []
        self._lock = threading.Lock()
        self._seq = 0

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return unsubscribe

    def emit(self, event_type: str, **payload: Any) -> None:
        with self._lock:
            self._seq += 1
            event: Event = {"seq": self._seq, "type": event_type, **payload}
            listeners = list(self._listeners)
        for listener in listeners:
            listener(event)
