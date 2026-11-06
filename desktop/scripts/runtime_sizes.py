"""Write sizes.json next to the bundled lock files: how much the first-run
bootstrap downloads and roughly how much disk it uses, per install profile.

    uv run --no-project python desktop/scripts/runtime_sizes.py <runtime-dir>

Download sizes are exact (the wheel sizes recorded in each pylock file, plus
the pinned tools); disk sizes are estimates, since wheels are compressed.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
import urllib.request
from pathlib import Path

# Installed size / download size, measured on a cu128 runtime (venv + uv
# cache, which hold the same unpacked files through hard links) and rounded up.
UNPACK_FACTOR = 1.6
# uv's managed CPython 3.12: download and installed size.
PYTHON_DOWNLOAD = 30 * 2**20
PYTHON_DISK = 110 * 2**20
# ffmpeg and deno unpack to roughly this multiple of their archive.
TOOL_FACTOR = 2.5
TOOL_FALLBACK = {"ffmpeg": 90 * 2**20, "deno": 45 * 2**20}

WHEEL = re.compile(r"-(?P<py>[^-]+)-(?P<abi>[^-]+)-(?P<plat>[^-]+)\.whl$")


def compatible(filename: str) -> bool:
    match = WHEEL.search(filename)
    if match is None:
        return False
    plats = match["plat"].split(".")
    pys = match["py"].split(".")
    plat_ok = "any" in plats or "win_amd64" in plats
    py_ok = any(p in ("py3", "cp312", "py2") for p in pys) or match["abi"] == "abi3"
    return plat_ok and py_ok


def lock_bytes(lock: Path) -> int:
    data = tomllib.loads(lock.read_text(encoding="utf-8"))
    total = 0
    for package in data.get("packages", []):
        wheels = [w for w in package.get("wheels", []) if compatible(w["url"].rsplit("/", 1)[-1])]
        if wheels:
            size = wheels[0].get("size")
            # The PyTorch index records no sizes: ask the server.
            total += int(size) if size else remote_size([wheels[0]["url"]], "", 0)
        elif "sdist" in package:
            total += int(package["sdist"].get("size", 0))
    return total


def remote_size(urls: list[str], version: str, fallback: int) -> int:
    for url in urls:
        request = urllib.request.Request(url.replace("{version}", version), method="HEAD")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                length = response.headers.get("Content-Length")
                if length:
                    return int(length)
        except OSError:
            continue
    return fallback


def main(out: Path) -> None:
    deps = json.loads((out / "deps.json").read_text(encoding="utf-8"))
    tools = {
        name: remote_size(deps[name]["urls"], deps[name]["version"], TOOL_FALLBACK[name])
        for name in ("ffmpeg", "deno")
    }
    tools_download = sum(tools.values())
    base_download = PYTHON_DOWNLOAD + tools_download
    base_disk = PYTHON_DISK + int(tools_download * TOOL_FACTOR)
    profiles = {}
    for name in ("core", "cpu", "cu128"):
        lock = out / f"pylock.{name}.toml"
        if not lock.exists():
            continue
        wheels = lock_bytes(lock)
        profiles[name] = {
            "download_bytes": base_download + wheels,
            "disk_bytes": base_disk + int(wheels * UNPACK_FACTOR),
        }
    (out / "sizes.json").write_text(json.dumps(profiles, indent=2) + "\n", encoding="utf-8")
    for name, size in profiles.items():
        print(
            f"{name:6} download {size['download_bytes'] / 2**30:5.2f} GiB, "
            f"disk ~{size['disk_bytes'] / 2**30:5.2f} GiB"
        )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
