"""Hardware detection without importing torch (the engine process stays light).

The GPU is queried through ``nvidia-smi``; everything else comes from psutil.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import psutil

# Executable names of common DAWs, for the low-impact mode.
DAW_PROCESSES = {
    "ableton live": "Ableton Live",
    "fl64.exe": "FL Studio",
    "fl.exe": "FL Studio",
    "reaper.exe": "REAPER",
    "cubase": "Cubase",
    "nuendo": "Nuendo",
    "studio one.exe": "Studio One",
    "bitwig studio.exe": "Bitwig Studio",
    "protools.exe": "Pro Tools",
}


class Tier(StrEnum):
    CPU = "cpu"
    VRAM_4 = "4gb"
    VRAM_6 = "6gb"
    VRAM_8 = "8gb"
    VRAM_12 = "12gb"


@dataclass(frozen=True)
class Gpu:
    name: str
    total_mb: int
    free_mb: int
    compute_capability: float
    driver: str

    @property
    def usable(self) -> bool:
        # Current CUDA builds of PyTorch need Turing (7.5) or newer.
        return self.compute_capability >= 7.5


@dataclass(frozen=True)
class Hardware:
    cpu_name: str
    physical_cores: int
    logical_cores: int
    ram_gb: float
    gpu: Gpu | None
    on_battery: bool | None
    free_disk_gb: float
    daws: list[str] = field(default_factory=list[str])

    @property
    def tier(self) -> Tier:
        if self.gpu is None or not self.gpu.usable:
            return Tier.CPU
        total = self.gpu.total_mb
        if total >= 11_500:
            return Tier.VRAM_12
        if total >= 7_500:
            return Tier.VRAM_8
        if total >= 5_500:
            return Tier.VRAM_6
        if total >= 3_500:
            return Tier.VRAM_4
        return Tier.CPU


def parse_nvidia_smi(output: str) -> Gpu | None:
    for line in output.strip().splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 5:
            continue
        name, total, free, capability, driver = parts[:5]
        try:
            return Gpu(name, int(float(total)), int(float(free)), float(capability), driver)
        except ValueError:
            continue
    return None


def detect_gpu() -> Gpu | None:
    smi = shutil.which("nvidia-smi")
    if smi is None:
        return None
    query = "name,memory.total,memory.free,compute_cap,driver_version"
    try:
        completed = subprocess.run(
            [smi, f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=False,
        )  # fmt: skip
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_nvidia_smi(completed.stdout) if completed.returncode == 0 else None


def running_daws() -> list[str]:
    found: set[str] = set()
    for process in psutil.process_iter(["name"]):
        name = (process.info.get("name") or "").lower()
        for needle, label in DAW_PROCESSES.items():
            if needle in name:
                found.add(label)
    return sorted(found)


def _cpu_name() -> str:
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        )
        return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
    except (ImportError, OSError):
        import platform

        return platform.processor() or "unknown CPU"


def detect(data_dir: Path) -> Hardware:
    battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    data_dir.mkdir(parents=True, exist_ok=True)
    return Hardware(
        cpu_name=_cpu_name(),
        physical_cores=psutil.cpu_count(logical=False) or 1,
        logical_cores=psutil.cpu_count(logical=True) or 1,
        ram_gb=round(psutil.virtual_memory().total / 2**30, 1),
        gpu=detect_gpu(),
        on_battery=None if battery is None else not battery.power_plugged,
        free_disk_gb=round(shutil.disk_usage(data_dir).free / 2**30, 1),
        daws=running_daws(),
    )
