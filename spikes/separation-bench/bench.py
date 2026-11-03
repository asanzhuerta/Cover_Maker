"""M1 spike: benchmark separation models on this machine.

Each configuration runs in its own subprocess so that out-of-memory errors are
isolated and VRAM is fully released between runs. Results go to results.csv
and results.json in the output directory.

    uv run python bench.py --seconds 60
    uv run python bench.py --only cpu --seconds 30
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_OUT = Path(os.environ.get("LOCALAPPDATA", ".")) / "Cover_Maker" / "bench"
HOP = 441  # STFT hop of the RoFormer checkpoints used here.


def seg(seconds: float) -> int:
    """RoFormer segment size (dim_t) for a chunk length in seconds."""
    return int(round(seconds * 44_100 / HOP)) + 1


@dataclass
class Config:
    model: str
    device: str = "cuda"
    precision: str = "fp32"  # fp32 | fp16 (native) | autocast
    chunk_s: float | None = None  # None = model default
    label: str = ""
    extra: dict[str, object] = field(default_factory=dict)

    def name(self) -> str:
        chunk = f"{self.chunk_s:g}s" if self.chunk_s else "default"
        return self.label or f"{self.model}|{self.device}|{self.precision}|{chunk}"


ROFORMERS = {
    "BS-Roformer-SW.ckpt": "multi",
    "bs_roformer_vocals_resurrection_unwa.ckpt": "vocals",
    "vocals_mel_band_roformer.ckpt": "vocals",
}
DEMUCS = ("htdemucs.yaml", "htdemucs_6s.yaml")


def matrix(only: str | None) -> list[Config]:
    configs: list[Config] = []
    if only in (None, "cuda"):
        for model in ROFORMERS:
            for precision in ("fp32", "fp16"):
                for chunk in (None, 8.0, 4.0):
                    configs.append(Config(model, "cuda", precision, chunk))
        configs.append(Config("BS-Roformer-SW.ckpt", "cuda", "autocast", 8.0))
        for model in DEMUCS:
            configs.append(Config(model, "cuda", "fp32"))
    if only in (None, "cpu"):
        configs.append(Config("htdemucs.yaml", "cpu", "fp32"))
        configs.append(Config("htdemucs_6s.yaml", "cpu", "fp32"))
        configs.append(Config("BS-Roformer-SW.ckpt", "cpu", "fp32", 8.0))
    return configs


# --------------------------------------------------------------------- worker


class Sampler(threading.Thread):
    """Samples process RSS and device VRAM use every 100 ms."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        import psutil

        self.proc = psutil.Process()
        self.peak_rss = 0
        self.peak_vram = 0
        self._halt = threading.Event()
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml = pynvml
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:  # no NVIDIA driver
            self._nvml = None

    def run(self) -> None:
        while not self._halt.is_set():
            self.peak_rss = max(self.peak_rss, self.proc.memory_info().rss)
            if self._nvml:
                used = self._nvml.nvmlDeviceGetMemoryInfo(self._handle).used
                self.peak_vram = max(self.peak_vram, used)
            time.sleep(0.1)

    def stop(self) -> None:
        self._halt.set()
        self.join()


def sdr(reference, estimate) -> float:
    import numpy as np

    n = min(len(reference), len(estimate))
    ref, est = reference[:n], estimate[:n]
    noise = np.sum((ref - est) ** 2)
    return float(10 * np.log10(np.sum(ref**2) / max(noise, 1e-12)))


def run_one(cfg: Config, mix_path: Path, truth_dir: Path, models_dir: Path) -> dict[str, object]:
    import numpy as np
    import soundfile as sf

    result: dict[str, object] = {"config": cfg.name(), **cfg.__dict__}
    sampler = Sampler()
    baseline_vram = 0
    if sampler._nvml:
        baseline_vram = sampler._nvml.nvmlDeviceGetMemoryInfo(sampler._handle).used
    sampler.start()
    out_dir = Path(tempfile.mkdtemp(prefix="cmbench-"))
    try:
        import torch
        from audio_separator.separator import Separator

        mdxc = {"segment_size": 256, "override_model_segment_size": False, "batch_size": 1, "overlap": 2, "pitch_shift": 0}
        if cfg.chunk_s:
            mdxc.update(segment_size=seg(cfg.chunk_s), override_model_segment_size=True)
        separator = Separator(
            log_level=40,
            model_file_dir=str(models_dir),
            output_dir=str(out_dir),
            output_format="WAV",
            use_autocast=cfg.precision == "autocast",
            use_native_fp16=cfg.precision == "fp16",
            mdxc_params=mdxc,
            demucs_params={"segment_size": "Default", "shifts": 1, "overlap": 0.25, "segments_enabled": True},
        )
        t0 = time.perf_counter()
        separator.load_model(cfg.model)
        t1 = time.perf_counter()
        outputs = separator.separate(str(mix_path))
        t2 = time.perf_counter()
        info = sf.info(str(mix_path))
        result.update(
            status="ok",
            load_s=round(t1 - t0, 2),
            sep_s=round(t2 - t1, 2),
            s_per_audio_min=round((t2 - t1) / (info.duration / 60), 2),
            torch_peak_mb=round(torch.cuda.max_memory_allocated() / 2**20) if torch.cuda.is_available() else 0,
        )
        scores: dict[str, float] = {}
        mix_truth, _ = sf.read(str(truth_dir / "mix.wav"), dtype="float32")
        produced: dict[str, Path] = {}
        for output in outputs:
            path = Path(output)
            path = path if path.is_absolute() else out_dir / path
            produced[path.stem.split("_(")[-1].split(")")[0].lower()] = path

        def truth(name: str):
            return sf.read(str(truth_dir / f"{name}.wav"), dtype="float32")[0]

        for stem, path in produced.items():
            est, _ = sf.read(str(path), dtype="float32")
            if stem == "instrumental":
                ref = mix_truth - truth("vocals")
            elif stem == "other":
                # "Other" holds everything the model has no dedicated stem for.
                ref = mix_truth - sum(truth(s) for s in produced if s not in ("other", "instrumental"))
            elif (truth_dir / f"{stem}.wav").exists():
                ref = truth(stem)
            else:
                continue
            scores[stem] = round(sdr(ref, est), 2)
        result["sdr"] = scores
        result["sdr_mean"] = round(float(np.mean(list(scores.values()))), 2) if scores else None
    except Exception as exc:  # noqa: BLE001 - report every failure
        text = f"{type(exc).__name__}: {exc}"
        result.update(status="oom" if "out of memory" in text.lower() else "error", error=text[:300])
    finally:
        sampler.stop()
        result["peak_rss_mb"] = round(sampler.peak_rss / 2**20)
        result["peak_vram_mb"] = round((sampler.peak_vram - baseline_vram) / 2**20) if sampler._nvml else 0
        for path in out_dir.glob("*"):
            path.unlink(missing_ok=True)
        out_dir.rmdir()
    return result


# ------------------------------------------------------------------ orchestrator


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--only", choices=["cuda", "cpu"])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()

    models_dir = args.out / "models"
    truth_dir = args.out / f"synthetic-{args.seconds:g}s"

    if args.worker:
        cfg = Config(**json.loads(args.worker))
        print("RESULT " + json.dumps(run_one(cfg, truth_dir / "mix.wav", truth_dir, models_dir)), flush=True)
        return

    from synth import write_multitrack

    if not (truth_dir / "mix.wav").exists():
        write_multitrack(truth_dir, args.seconds)
    models_dir.mkdir(parents=True, exist_ok=True)

    results_path = args.out / f"results-{args.only or 'all'}.json"
    # Resume: keep finished configurations from a previous, interrupted run.
    results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else []
    done = {r["config"] for r in results if r.get("status") in ("ok", "oom")}
    for cfg in matrix(args.only):
        if cfg.name() in done:
            continue
        env = dict(os.environ)
        if cfg.device == "cpu":
            env["CUDA_VISIBLE_DEVICES"] = "-1"  # "" does not hide the GPU on Windows
        payload = json.dumps({k: v for k, v in cfg.__dict__.items() if k != "extra"})
        print(f"== {cfg.name()}", flush=True)
        proc = subprocess.run(
            [sys.executable, __file__, "--seconds", str(args.seconds), "--out", str(args.out), "--worker", payload],
            capture_output=True, text=True, env=env, timeout=3 * 3600,
        )
        line = next((l for l in proc.stdout.splitlines() if l.startswith("RESULT ")), None)
        result = json.loads(line[7:]) if line else {"config": cfg.name(), "status": "crash", "error": proc.stderr[-300:]}
        print("   ", {k: result.get(k) for k in ("status", "sep_s", "s_per_audio_min", "peak_vram_mb", "peak_rss_mb", "sdr_mean")}, flush=True)
        results.append(result)
        (args.out / f"results-{args.only or 'all'}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    fields = ["config", "model", "device", "precision", "chunk_s", "status", "load_s", "sep_s", "s_per_audio_min",
              "torch_peak_mb", "peak_vram_mb", "peak_rss_mb", "sdr_mean", "sdr", "error"]
    with open(args.out / f"results-{args.only or 'all'}.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
