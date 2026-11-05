"""Regenerate the generated sections of THIRD_PARTY_NOTICES.md.

Three tables are rewritten between `<!-- generated:<name> -->` markers:

- `python`: every package of the runtime (the `cu128` profile of
  engine/uv.lock), with the licence from the engine venv's metadata;
- `rust`: the crates compiled into the desktop shell for Windows (normal
  dependencies only, from `cargo metadata`);
- `javascript`: the production packages of the user interface (`pnpm
  licenses`), plus the Svelte and SvelteKit runtimes that the build bundles;
- `vst3`: the crates compiled into the VST3 plugin (`daw/vst3`).

Run from the repository root, with the engine venv synced with
`--extra separation --extra cu128`:

    uv run --project engine --inexact python docs/tools/notices.py
"""

from __future__ import annotations

import importlib.metadata as metadata
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"
ENGINE = ROOT / "engine"
DESKTOP = ROOT / "desktop"
SHELL = DESKTOP / "src-tauri"
PLUGIN = ROOT / "daw" / "vst3"
# Build-time packages whose runtime code ends up in the UI bundle.
BUNDLED_DEV = ("svelte", "@sveltejs/kit")


def run(*args: str, cwd: Path) -> str:
    return subprocess.run(
        list(args), cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True,
        shell=args[0] == "pnpm",
    ).stdout  # fmt: skip


def table(rows: list[tuple[str, str, str]], header: tuple[str, str, str]) -> str:
    lines = [f"| {header[0]} | {header[1]} | {header[2]} |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in sorted(rows, key=lambda r: r[0].lower())]
    return "\n".join(lines)


# ------------------------------------------------------------------ python


def python_licence(name: str) -> str:
    try:
        meta = metadata.metadata(name)
    except metadata.PackageNotFoundError:
        return "not installed in the dev venv"
    if meta.get("License-Expression"):
        return str(meta["License-Expression"])
    licence = (meta.get("License") or "").strip().splitlines()
    if licence and len(licence[0]) <= 60:
        return licence[0]
    classifiers = [
        c.split("::")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    return ", ".join(classifiers) or "see the package"


def python_rows() -> list[tuple[str, str, str]]:
    exported = run(
        "uv", "export", "--frozen", "--no-dev", "--no-emit-project", "--no-hashes",
        "--extra", "separation", "--extra", "cu128", "--project", str(ENGINE), cwd=ROOT,
    )  # fmt: skip
    names = {
        line.split("==")[0].strip()
        for line in exported.splitlines()
        if line.strip() and not line.startswith(("#", "-", " "))
    }
    rows: list[tuple[str, str, str]] = []
    for name in names:
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            version = "?"
        licence = python_licence(name)
        if name == "soundfile":
            licence += " (bundles libsndfile, LGPL-2.1-or-later)"
        rows.append((name, version, licence))
    return rows


# -------------------------------------------------------------------- rust


def rust_rows(cwd: Path = SHELL) -> list[tuple[str, str, str]]:
    data = json.loads(
        run("cargo", "metadata", "--format-version", "1", "--locked",
            "--filter-platform", "x86_64-pc-windows-msvc", cwd=cwd)
    )  # fmt: skip
    packages = {p["id"]: p for p in data["packages"]}
    nodes = {n["id"]: n for n in data["resolve"]["nodes"]}
    # The plugin folder is a workspace (plugin + xtask): start from the plugin.
    root = data["resolve"]["root"] or next(
        i for i, pkg in packages.items() if pkg["name"] == "cover_maker_vst3"
    )
    seen: set[str] = set()
    stack = [root]
    while stack:
        node = nodes[stack.pop()]
        for dep in node["deps"]:
            normal = any(kind["kind"] is None for kind in dep["dep_kinds"])
            if normal and dep["pkg"] not in seen:
                seen.add(dep["pkg"])
                stack.append(dep["pkg"])
    return [
        (packages[i]["name"], packages[i]["version"], packages[i].get("license") or "see the crate")
        for i in seen
    ]


# -------------------------------------------------------------- javascript


def javascript_rows() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for flag in ("--prod", "--dev"):
        data = json.loads(run("pnpm", "licenses", "list", flag, "--json", cwd=DESKTOP))
        for licence, entries in data.items():
            for entry in entries:
                if flag == "--dev" and entry["name"] not in BUNDLED_DEV:
                    continue
                rows.extend((entry["name"], v, licence) for v in entry["versions"])
    return rows


def replace(text: str, name: str, body: str) -> str:
    pattern = re.compile(
        rf"(<!-- generated:{name} -->\n)(?:.*?\n)?(<!-- /generated:{name} -->)", re.S
    )
    if not pattern.search(text):
        raise SystemExit(f"marker generated:{name} missing in {NOTICES.name}")
    return pattern.sub(lambda m: m.group(1) + body + "\n" + m.group(2), text)


def main() -> None:
    text = NOTICES.read_text(encoding="utf-8")
    text = replace(text, "python", table(python_rows(), ("Package", "Version", "Licence")))
    text = replace(text, "rust", table(rust_rows(), ("Crate", "Version", "Licence")))
    text = replace(text, "javascript", table(javascript_rows(), ("Package", "Version", "Licence")))
    text = replace(text, "vst3", table(rust_rows(PLUGIN), ("Crate", "Version", "Licence")))
    NOTICES.write_text(text, encoding="utf-8", newline="\n")
    print(f"updated {NOTICES}")


if __name__ == "__main__":
    main()
