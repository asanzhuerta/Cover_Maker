"""Polyphonic note transcription with Spotify's Basic Pitch model on ONNX Runtime.

Ported from basic-pitch (https://github.com/spotify/basic-pitch, commit fa5997a),
Copyright 2022 Spotify AB, licensed under the Apache License 2.0:

- ``inference.py``: windowing of the audio and unwrapping of the model output;
- ``note_creation.py``: onset peak picking, note tracking, inferred onsets and
  the "melodia trick".

Changes from the original: numpy only (no TensorFlow, pretty_midi or mir_eval,
which do not install on Python 3.12 on Windows), windows run in batches, frame
times follow the window hop exactly, notes are returned in seconds and pitch
bends are not produced. The model file ``nmp.onnx`` is unmodified.
"""

# onnxruntime ships without complete type information.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from .notes import Note

MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "basic_pitch" / "nmp.onnx"

SAMPLE_RATE = 22_050
FFT_HOP = 256
_FPS = SAMPLE_RATE // FFT_HOP  # 86 model frames per second
_WINDOW = SAMPLE_RATE * 2 - FFT_HOP  # 43 844 samples per model window
_WINDOW_FRAMES = _FPS * 2  # 172 frames out of each window
_OVERLAP_FRAMES = 30
_OVERLAP = _OVERLAP_FRAMES * FFT_HOP
_HOP = _WINDOW - _OVERLAP  # 36 164 samples between windows
_KEPT = _WINDOW_FRAMES - _OVERLAP_FRAMES  # 142 frames kept per window
_MIDI_OFFSET = 21  # the lowest model bin is A0
_N_PITCHES = 88
_BATCH = 16

_INPUT = "serving_default_input_2:0"
_NOTE = "StatefulPartitionedCall:1"
_ONSET = "StatefulPartitionedCall:2"

Matrix = NDArray[np.float32]


class Cancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    """Basic Pitch's defaults; the frequency range narrows the search per stem."""

    onset_threshold: float = 0.5
    frame_threshold: float = 0.3
    min_note_ms: float = 127.7
    min_hz: float | None = None
    max_hz: float | None = None
    melodia_trick: bool = True
    energy_tolerance: int = 11


def frame_times(n_frames: int) -> NDArray[np.float64]:
    """Start time in seconds of every unwrapped output frame."""
    k = np.arange(n_frames)
    return ((k // _KEPT) * _HOP + (k % _KEPT) * FFT_HOP) / SAMPLE_RATE


class BasicPitch:
    """A loaded model; one instance can transcribe many stems."""

    def __init__(self, model_path: Path = MODEL_PATH, threads: int | None = None) -> None:
        import onnxruntime as ort

        options = ort.SessionOptions()
        if threads:
            options.intra_op_num_threads = threads
        self._session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )

    def activations(
        self,
        y: NDArray[np.float32],
        progress: Callable[[float], None] | None = None,
        cancel: threading.Event | None = None,
    ) -> tuple[Matrix, Matrix]:
        """Note and onset activations (frames x 88) of mono audio at 22.05 kHz."""
        padded = np.concatenate([np.zeros(_OVERLAP // 2, dtype=np.float32), y])
        starts = list(range(0, len(padded), _HOP)) or [0]
        notes: list[Matrix] = []
        onsets: list[Matrix] = []
        for first in range(0, len(starts), _BATCH):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            batch = np.zeros((len(starts[first : first + _BATCH]), _WINDOW, 1), dtype=np.float32)
            for row, start in enumerate(starts[first : first + _BATCH]):
                chunk = padded[start : start + _WINDOW]
                batch[row, : len(chunk), 0] = chunk
            note, onset = self._session.run([_NOTE, _ONSET], {_INPUT: batch})
            half = _OVERLAP_FRAMES // 2
            notes.append(
                np.asarray(note, dtype=np.float32)[:, half:-half, :].reshape(-1, _N_PITCHES)
            )
            onsets.append(
                np.asarray(onset, dtype=np.float32)[:, half:-half, :].reshape(-1, _N_PITCHES)
            )
            if progress is not None:
                progress(min(1.0, (first + _BATCH) / len(starts)))
        n_frames = int(len(y) / _HOP * _KEPT)
        return np.concatenate(notes)[:n_frames], np.concatenate(onsets)[:n_frames]

    def transcribe(
        self,
        y: NDArray[np.float32],
        settings: Settings | None = None,
        progress: Callable[[float], None] | None = None,
        cancel: threading.Event | None = None,
    ) -> list[Note]:
        frames, onsets = self.activations(y, progress, cancel)
        return activations_to_notes(frames, onsets, settings or Settings())


def _hz_to_bin(hz: float) -> int:
    return round(12 * np.log2(hz / 440.0) + 69 - _MIDI_OFFSET)


def _inferred_onsets(onsets: Matrix, frames: Matrix, n_diff: int = 2) -> Matrix:
    """Add onsets where the frame activation jumps (Basic Pitch ``get_infered_onsets``)."""
    diffs: list[Matrix] = []
    for n in range(1, n_diff + 1):
        shifted = np.concatenate([np.zeros((n, frames.shape[1]), dtype=np.float32), frames])
        diffs.append(shifted[n:, :] - shifted[:-n, :])
    frame_diff = np.min(diffs, axis=0)
    frame_diff[frame_diff < 0] = 0
    frame_diff[:n_diff, :] = 0
    top = float(np.max(frame_diff)) if frame_diff.size else 0.0
    if top > 0:
        frame_diff = float(np.max(onsets)) * frame_diff / top
    return np.maximum(onsets, frame_diff).astype(np.float32)


def _local_maxima(x: Matrix) -> Matrix:
    """Values at strict local maxima along time, zero elsewhere (``scipy.signal.argrelmax``)."""
    peaks = np.zeros_like(x)
    if len(x) >= 3:
        inner = x[1:-1]
        mask = (inner > x[:-2]) & (inner > x[2:])
        peaks[1:-1][mask] = inner[mask]
    return peaks


def _clear(energy: Matrix, rows: slice | int, pitch: int) -> None:
    energy[rows, pitch] = 0
    if pitch < _N_PITCHES - 1:
        energy[rows, pitch + 1] = 0
    if pitch > 0:
        energy[rows, pitch - 1] = 0


def activations_to_notes(frames: Matrix, onsets: Matrix, settings: Settings) -> list[Note]:
    """Decode the activations to notes (Basic Pitch ``output_to_notes_polyphonic``)."""
    n_frames = frames.shape[0]
    if n_frames < 3:
        return []
    frames = frames.copy()
    onsets = onsets.copy()
    low = _hz_to_bin(settings.min_hz) if settings.min_hz else 0
    high = _hz_to_bin(settings.max_hz) if settings.max_hz else _N_PITCHES
    for matrix in (frames, onsets):
        matrix[:, : max(0, low)] = 0
        matrix[:, max(0, high) :] = 0
    onsets = _inferred_onsets(onsets, frames)
    min_len = round(settings.min_note_ms / 1000 * SAMPLE_RATE / FFT_HOP)
    tol = settings.energy_tolerance
    thresh = settings.frame_threshold
    times = frame_times(n_frames + 1)

    peaks = _local_maxima(onsets)
    onset_t, onset_p = np.where(peaks >= settings.onset_threshold)
    remaining = frames.copy()
    events: list[tuple[int, int, int, float]] = []
    for start, pitch in zip(onset_t[::-1].tolist(), onset_p[::-1].tolist(), strict=True):
        if start >= n_frames - 1:
            continue
        i, k = start + 1, 0
        while i < n_frames - 1 and k < tol:
            k = k + 1 if remaining[i, pitch] < thresh else 0
            i += 1
        i -= k
        if i - start <= min_len:
            continue
        _clear(remaining, slice(start, i), pitch)
        events.append((start, i, pitch, float(np.mean(frames[start:i, pitch]))))

    if settings.melodia_trick:
        while float(np.max(remaining)) > thresh:
            mid, pitch = (int(v) for v in np.unravel_index(np.argmax(remaining), remaining.shape))
            remaining[mid, pitch] = 0
            i, k = mid + 1, 0
            while i < n_frames - 1 and k < tol:
                k = k + 1 if remaining[i, pitch] < thresh else 0
                _clear(remaining, i, pitch)
                i += 1
            end = i - 1 - k
            i, k = mid - 1, 0
            while i > 0 and k < tol:
                k = k + 1 if remaining[i, pitch] < thresh else 0
                _clear(remaining, i, pitch)
                i -= 1
            begin = i + 1 + k
            if end - begin <= min_len:
                continue
            events.append((begin, end, pitch, float(np.mean(frames[begin:end, pitch]))))

    notes = [
        Note(
            start=float(times[a]),
            end=float(times[b]),
            pitch=p + _MIDI_OFFSET,
            velocity=max(1, min(127, round(127 * amp))),
        )
        for a, b, p, amp in events
    ]
    return sorted(notes, key=lambda n: (n.start, n.pitch))
