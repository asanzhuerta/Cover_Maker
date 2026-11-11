"""Tempo map for the MIDI files, fitted to the beat grid of the analysis (M14).

The stems keep their timing (every stem starts at 0), so the map is fitted to
the audio. This is the algorithm of the DAW session export (ADR-011), so MIDI
notes and a session share one bar grid:

- **Steady songs** (every downbeat within :data:`STEADY_TOLERANCE` of a straight
  bar grid) get one tempo.
- **Other songs** get one tempo per bar, so every bar line falls on a detected
  downbeat.
- **Pickup**: when the first downbeat is not at 0, the time before it becomes a
  pickup bar (whole beats, in its own time signature). A pickup too short to be
  a bar is merged into the first bar.

Without a beat grid the map is a single tempo (120 BPM when none is known).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

import numpy as np

BEATS_PER_BAR = 4
DEFAULT_BPM = 120.0
MIN_BPM = 20.0
MAX_BPM = 960.0  # REAPER's limit
MIN_PICKUP = 60.0 / MAX_BPM  # seconds: a one-beat bar at the highest tempo
STEADY_TOLERANCE = 0.04  # seconds; the beat tracker works on ~23 ms frames


@dataclass(frozen=True)
class TempoPoint:
    time: float  # seconds
    bpm: float  # quarter notes per minute from here on
    bar_start: bool = True  # a bar line falls on this point
    numerator: int = BEATS_PER_BAR  # time signature numerator/4 from here on


def _clamp(bpm: float) -> float:
    return round(min(MAX_BPM, max(MIN_BPM, bpm)), 4)


def _bar_bpm(seconds: float) -> float:
    return _clamp(60.0 * BEATS_PER_BAR / seconds)


def tempo_map(downbeats: Sequence[float], bpm: float) -> tuple[TempoPoint, ...]:
    """Tempo points (the first at 0) that put a bar line on every downbeat."""
    fallback = _clamp(bpm) if bpm > 0 else DEFAULT_BPM
    bars = sorted({round(t, 6) for t in downbeats if t >= 0})
    if not bars:
        return (TempoPoint(0.0, fallback),)
    if len(bars) == 1:
        return _with_pickup(bars[0], [TempoPoint(bars[0], fallback)])
    index = np.arange(len(bars), dtype=np.float64)
    times = np.asarray(bars, dtype=np.float64)
    slope, intercept = (float(v) for v in np.polyfit(index, times, 1))
    deviation = float(np.max(np.abs(times - (intercept + slope * index))))
    if slope > 0 and deviation <= STEADY_TOLERANCE:
        anchor = round(max(0.0, intercept), 6)
        return _with_pickup(anchor, [TempoPoint(anchor, _bar_bpm(slope))])
    body: list[TempoPoint] = []
    for start, end in pairwise(bars):
        tempo = _bar_bpm(end - start)
        if body and body[-1].bpm == tempo:
            continue  # the same tempo holds; no new point needed
        body.append(TempoPoint(start, tempo, bar_start=not body))
    return _with_pickup(bars[0], body)


def _with_pickup(anchor: float, body: list[TempoPoint]) -> tuple[TempoPoint, ...]:
    """Fill the time before the first downbeat ``anchor`` (the time of ``body[0]``)."""
    head = body[0]
    if anchor <= 0:
        return (TempoPoint(0.0, head.bpm), *body[1:])
    if anchor < MIN_PICKUP:
        # Too short for a bar of its own: the first bar starts at 0 and absorbs it.
        bar_end = round(anchor + 60.0 * BEATS_PER_BAR / head.bpm, 6)
        first = TempoPoint(0.0, _bar_bpm(bar_end))
        if len(body) > 1 and abs(body[1].time - bar_end) < 1e-3:
            return (first, *body[1:])
        return (first, TempoPoint(bar_end, head.bpm, bar_start=False), *body[1:])
    beat = 60.0 / head.bpm
    count = max(1, round(anchor / beat))
    if count >= BEATS_PER_BAR:
        count = max(1, round(anchor / (beat * BEATS_PER_BAR))) * BEATS_PER_BAR
    pickup = TempoPoint(0.0, _clamp(60.0 * count / anchor), numerator=min(count, BEATS_PER_BAR))
    return (pickup, TempoPoint(head.time, head.bpm), *body[1:])


def beats_at(tempo: Sequence[TempoPoint], time: float) -> float:
    """Quarter-note beats from 0 to ``time`` (seconds) under the tempo map."""
    total = 0.0
    for index, point in enumerate(tempo):
        if time <= point.time:
            break
        end = tempo[index + 1].time if index + 1 < len(tempo) else time
        total += (min(time, end) - point.time) * point.bpm / 60.0
    return total


def time_signature_changes(tempo: Sequence[TempoPoint]) -> list[TempoPoint]:
    """Points where a time signature starts (the first point, and any numerator change)."""
    changes: list[TempoPoint] = []
    current: int | None = None
    for point in tempo:
        if current is None or (point.bar_start and point.numerator != current):
            current = point.numerator
            changes.append(point)
    return changes
