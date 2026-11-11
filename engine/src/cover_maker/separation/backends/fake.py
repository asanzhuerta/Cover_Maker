"""Deterministic stand-in for a separation model, used by tests and demo mode.

Each requested stem is the mix scaled by a fixed weight. When a model produces
every stem the weights add up to one, so the residual is zero, like a perfect
model; models that produce fewer stems leave a residual, like real ones.
"""

from __future__ import annotations

import time
from pathlib import Path

from ...audio import io
from ...domain import Stem
from ..types import SeparationRequest, SeparationResult

WEIGHTS: dict[Stem, float] = {
    Stem.VOCALS: 0.3,
    Stem.GUITAR: 0.2,
    Stem.DRUMS: 0.2,
    Stem.BASS: 0.1,
    Stem.PIANO: 0.1,
    Stem.OTHER: 0.1,
    # A lead/backing model splits the vocals it is given (weights add up to one).
    Stem.VOCALS_LEAD: 0.7,
    Stem.VOCALS_BACKING: 0.3,
}


class FakeBackend:
    def __init__(self, *, fail_oom_above_chunk: float | None = None) -> None:
        self.calls: list[SeparationRequest] = []
        self.fail_oom_above_chunk = fail_oom_above_chunk

    def separate(self, request: SeparationRequest) -> SeparationResult:
        from ..types import SeparationError

        self.calls.append(request)
        limit = self.fail_oom_above_chunk
        if limit is not None and request.device == "gpu" and (request.chunk_s or 99) > limit:
            raise SeparationError("CUDA out of memory (simulated)", oom=True)
        started = time.perf_counter()
        mix = io.read(request.input_path)
        request.output_dir.mkdir(parents=True, exist_ok=True)
        outputs: dict[Stem, Path] = {}
        for stem in request.stems.values():
            target = request.output_dir / f"{stem.value}.wav"
            io.write(mix * WEIGHTS[stem], target, "wav")
            outputs[stem] = target
        return SeparationResult(
            outputs=outputs,
            seconds=time.perf_counter() - started,
            device=request.device,
            precision=request.precision,
            chunk_s=request.chunk_s,
        )
