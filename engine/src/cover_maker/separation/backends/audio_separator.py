# pyright: basic
# (PyTorch and audio-separator are untyped; this module runs only in the worker.)
"""Backend that runs models through the audio-separator package.

Only the separation worker imports this module: it pulls in PyTorch, which the
engine process never loads.
"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path
from typing import Any

from ...domain import Stem
from ..types import SeparationError, SeparationRequest, SeparationResult

ROFORMER_HOP = 441
LABEL = re.compile(r"_\(([^)]+)\)")


def segment_size(chunk_s: float) -> int:
    """RoFormer ``dim_t`` for a chunk length: chunk = hop * (segment - 1)."""
    return round(chunk_s * 44_100 / ROFORMER_HOP) + 1


def _is_oom(exc: BaseException) -> bool:
    return "out of memory" in str(exc).lower() or type(exc).__name__ == "OutOfMemoryError"


class AudioSeparatorBackend:
    def __init__(self) -> None:
        self._key: tuple[Any, ...] | None = None
        self._separator: Any = None

    def _load(self, request: SeparationRequest, scratch: Path) -> Any:
        key = (request.model_filename, request.precision, request.chunk_s, str(request.model_dir))
        if self._key == key and self._separator is not None:
            # The loaded model keeps its own copy of the output folder: point
            # both at this job's scratch, or the stems land in the last job's.
            self._separator.output_dir = str(scratch)
            model = getattr(self._separator, "model_instance", None)
            if model is not None:
                model.output_dir = str(scratch)
            return self._separator
        self._release()
        from audio_separator.separator import Separator  # pyright: ignore[reportMissingImports]

        mdxc: dict[str, Any] = {
            "segment_size": 256,
            "override_model_segment_size": False,
            "batch_size": 1,
            "overlap": 2,  # explicit: YAML defaults of 4-8 are 2-4 times slower
            "pitch_shift": 0,
        }
        if request.chunk_s:
            mdxc.update(
                segment_size=segment_size(request.chunk_s), override_model_segment_size=True
            )
        separator = Separator(
            log_level=40,
            model_file_dir=str(request.model_dir),
            output_dir=str(scratch),
            output_format="WAV",
            use_native_fp16=request.precision == "fp16",
            mdxc_params=mdxc,
            demucs_params={
                "segment_size": "Default",
                "shifts": 1,
                "overlap": 0.25,
                "segments_enabled": True,
            },
        )
        separator.load_model(request.model_filename)
        self._key, self._separator = key, separator
        return separator

    def _release(self) -> None:
        self._key, self._separator = None, None
        try:
            import torch  # pyright: ignore[reportMissingImports]

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except ImportError:
            pass

    def separate(self, request: SeparationRequest) -> SeparationResult:
        scratch = request.output_dir / "_raw"
        scratch.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        try:
            separator = self._load(request, scratch)
            produced = separator.separate(str(request.input_path))
        except Exception as exc:
            self._release()
            raise SeparationError(f"{type(exc).__name__}: {exc}", oom=_is_oom(exc)) from exc

        labels = {label.lower(): stem for label, stem in request.stems.items()}
        outputs: dict[Stem, Path] = {}
        for item in produced:
            path = Path(item)
            path = path if path.is_absolute() else scratch / path
            match = LABEL.search(path.stem)
            stem = labels.get(match.group(1).lower()) if match else None
            if stem is None:
                path.unlink(missing_ok=True)
                continue
            target = request.output_dir / f"{stem.value}.wav"
            shutil.move(str(path), target)
            outputs[stem] = target
        shutil.rmtree(scratch, ignore_errors=True)
        missing = set(request.stems.values()) - outputs.keys()
        if missing:
            raise SeparationError(
                f"model produced no output for: {sorted(s.value for s in missing)}"
            )
        return SeparationResult(
            outputs=outputs,
            seconds=time.perf_counter() - started,
            device=request.device,
            precision=request.precision,
            chunk_s=request.chunk_s,
        )
