"""List the licence of every Python package the installed app's runtime uses.

Reads the package names from the `cu128` profile of engine/uv.lock (a superset
of the `core` and `cpu` profiles apart from the PyTorch build) and each
licence from the package metadata of the engine's development venv, which must
have been synced with `uv sync --extra separation --extra cu128`.

    cd engine && uv run --inexact python ../docs/tools/python_licences.py

Prints a Markdown table for THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

import importlib.metadata as metadata
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2] / "engine"


def locked_packages() -> list[str]:
    exported = subprocess.run(
        ["uv", "export", "--frozen", "--no-dev", "--no-emit-project", "--no-hashes",
         "--extra", "separation", "--extra", "cu128", "--project", str(ENGINE)],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    names = []
    for line in exported.splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "-")):
            names.append(line.split("==")[0].split(" ")[0])
    return sorted(set(names), key=str.lower)


def licence_of(name: str) -> str:
    try:
        meta = metadata.metadata(name)
    except metadata.PackageNotFoundError:
        return "not installed in the dev venv"
    expression = meta.get("License-Expression")
    if expression:
        return expression
    licence = (meta.get("License") or "").strip().splitlines()
    if licence and len(licence[0]) <= 60:
        return licence[0]
    classifiers = [
        c.split("::")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    return ", ".join(classifiers) or "see the package"


def main() -> None:
    print("| Package | Version | Licence |")
    print("|---|---|---|")
    for name in locked_packages():
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            version = "?"
        print(f"| {name} | {version} | {licence_of(name)} |")


if __name__ == "__main__":
    sys.exit(main())
