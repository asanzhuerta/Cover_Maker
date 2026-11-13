"""Write sizes.json next to the bundled lock files: how much the first-run
bootstrap downloads and roughly how much disk it uses, per install profile.

    uv run --no-project python desktop/scripts/runtime_sizes.py <runtime-dir> [platform]

``platform`` is a key of ``deps.json``: ``windows-x64`` (the default) or
``macos-arm64``. Download sizes are exact (the wheel sizes recorded in each
pylock file for that platform, plus the pinned tools); disk sizes are
estimates, since wheels are compressed.
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
PROFILES = ("core", "cpu", "cu128", "mps")
# `sys_platform` of each platform key, for the markers of the lock files.
SYS_PLATFORM = {"windows-x64": "win32", "macos-arm64": "darwin"}


def platform_tag_ok(tag: str, platform: str) -> bool:
    if tag == "any":
        return True
    if platform == "macos-arm64":
        return tag.startswith("macosx_") and tag.endswith(("_arm64", "_universal2"))
    return tag == "win_amd64"


def compatible(filename: str, platform: str = "windows-x64") -> bool:
    match = WHEEL.search(filename)
    if match is None:
        return False
    plats = match["plat"].split(".")
    pys = match["py"].split(".")
    plat_ok = any(platform_tag_ok(tag, platform) for tag in plats)
    py_ok = any(p in ("py3", "cp312", "py2") for p in pys) or match["abi"] == "abi3"
    return plat_ok and py_ok


def for_platform(marker: str | None, platform: str) -> bool:
    """False when a package's marker names only another platform.

    The lock files cover Windows and macOS; their markers compare
    ``sys_platform`` with one value, which is all this needs to read.
    """
    if not marker:
        return True
    ours = SYS_PLATFORM[platform]
    for other in set(SYS_PLATFORM.values()) - {ours}:
        if f"sys_platform == '{other}'" in marker and f"sys_platform == '{ours}'" not in marker:
            return False
    return f"sys_platform != '{ours}'" not in marker


def lock_bytes(lock: Path, platform: str = "windows-x64") -> int:
    data = tomllib.loads(lock.read_text(encoding="utf-8"))
    total = 0
    for package in data.get("packages", []):
        if not for_platform(package.get("marker"), platform):
            continue
        wheels = [
            w
            for w in package.get("wheels", [])
            if compatible(w["url"].rsplit("/", 1)[-1], platform)
        ]
        if wheels:
            size = wheels[0].get("size")
            # The PyTorch index records no sizes: ask the server.
            total += int(size) if size else remote_size([wheels[0]["url"]], "", 0)
        elif "sdist" in package:
            total += int(package["sdist"].get("size", 0))
    return total


def remote_size(urls: list[str], version: str, fallback: int) -> int:
    for url in urls:
        # URLs come from the repository's lock files; only HTTPS is accepted.
        if not url.startswith("https://"):
            continue
        request = urllib.request.Request(url.replace("{version}", version), method="HEAD")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
                length = response.headers.get("Content-Length")
                if length:
                    return int(length)
        except OSError:
            continue
    return fallback


def main(out: Path, platform: str = "windows-x64") -> None:
    deps = json.loads((out / "deps.json").read_text(encoding="utf-8"))[platform]
    # A tool set to null is not installed by the runtime on that platform.
    tools = {
        name: remote_size(deps[name]["urls"], deps[name]["version"], TOOL_FALLBACK[name])
        for name in ("ffmpeg", "deno")
        if deps.get(name)
    }
    tools_download = sum(tools.values())
    base_download = PYTHON_DOWNLOAD + tools_download
    base_disk = PYTHON_DISK + int(tools_download * TOOL_FACTOR)
    profiles = {}
    for name in PROFILES:
        lock = out / f"pylock.{name}.toml"
        if not lock.exists():
            continue
        wheels = lock_bytes(lock, platform)
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
    main(Path(sys.argv[1]), *sys.argv[2:3])
