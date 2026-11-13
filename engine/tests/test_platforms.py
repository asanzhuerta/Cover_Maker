"""Platform differences (ADR-013): Apple Silicon GPU, worker device, DAW names."""

from __future__ import annotations

from typing import Any

import pytest

from cover_maker.separation import hardware, service
from cover_maker.separation.hardware import Hardware, Tier, apple_gpu


def _hardware(gpu: hardware.Gpu | None) -> Hardware:
    return Hardware("Apple M2", 8, 8, 16.0, gpu, None, 100.0)


@pytest.mark.parametrize(
    ("ram_gb", "tier"),
    [(8, Tier.VRAM_4), (16, Tier.VRAM_8), (24, Tier.VRAM_12), (4, Tier.CPU)],
)
def test_apple_gpu_uses_its_share_of_unified_memory(ram_gb: int, tier: Tier) -> None:
    gpu = apple_gpu("Apple M2", ram_gb * 2**30, ram_gb * 2**30)

    assert gpu.api == "mps" and gpu.usable
    assert gpu.name == "Apple M2 GPU" and gpu.driver == "Metal"
    assert gpu.total_mb == int(ram_gb * 1024 * hardware.APPLE_GPU_SHARE)
    assert _hardware(gpu).tier is tier


def test_apple_gpu_free_memory_never_exceeds_its_share() -> None:
    gpu = apple_gpu("", 16 * 2**30, 12 * 2**30)

    assert gpu.name == "Apple Silicon GPU"
    assert gpu.free_mb == 8192 <= gpu.total_mb


def test_nvidia_gpus_keep_the_cuda_rules() -> None:
    old = hardware.Gpu("GTX 1060", 6144, 6000, 6.1, "1")

    assert old.api == "cuda" and not old.usable
    assert _hardware(old).tier is Tier.CPU


def test_detection_follows_the_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "apple_silicon", lambda: True)
    monkeypatch.setattr(hardware, "_sysctl", lambda name: "Apple M3 Pro")

    gpu = hardware.detect_gpu()
    assert gpu is not None and gpu.api == "mps" and gpu.name == "Apple M3 Pro GPU"


def test_daw_names_match_on_both_platforms(monkeypatch: pytest.MonkeyPatch) -> None:
    class Process:
        def __init__(self, name: str) -> None:
            self.info = {"name": name}

    names = ["reaper.exe", "REAPER", "Logic Pro X", "Bitwig Studio", "Finder", "fl64.exe"]
    monkeypatch.setattr(hardware.psutil, "process_iter", lambda attrs: [Process(n) for n in names])

    assert hardware.running_daws() == ["Bitwig Studio", "FL Studio", "Logic Pro", "REAPER"]


def test_workers_learn_their_device(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[tuple[Any, ...]] = []

    class FakeProcess:
        def __init__(self, target: Any, args: tuple[Any, ...], daemon: bool) -> None:
            started.append(args)

        def start(self) -> None:
            pass

    class Connection:
        def close(self) -> None:
            pass

    class Context:
        Process = FakeProcess

        def Pipe(self) -> tuple[Connection, Connection]:  # multiprocessing API name
            return Connection(), Connection()

    monkeypatch.setattr(service.multiprocessing, "get_context", lambda method: Context())
    workers = service.WorkerService(threads=2, low_priority=False)

    workers._worker("cpu")  # pyright: ignore[reportPrivateUsage]
    workers._worker("gpu")  # pyright: ignore[reportPrivateUsage]

    assert [args[1:] for args in started] == [(2, False, "cpu"), (2, False, "gpu")]
