# Contributing to Cover_Maker

Thanks for your interest in improving Cover_Maker.

## Ground rules

- **Legal by design.** Do not add features that search for, scrape or match
  music on streaming services, use their APIs to locate music, or decrypt DRM.
  Online audio may only come from links the user pastes, through the unmodified
  yt-dlp dependency. Do not add commercial recordings to tests, examples,
  screenshots or documentation; use synthetic audio or Creative Commons
  material with attribution.
- **Model weights are never committed or hosted here.** New catalogue entries
  must state licence and provenance.
- Code, commit messages and documentation are written in English.

## Repository layout

| Path | Contents |
|---|---|
| `engine/` | Python engine (uv project): pipeline, library, API, CLI |
| `desktop/` | Tauri 2 shell + SvelteKit/TypeScript UI |
| `docs/latex/` | Project documentation (LaTeX) |
| `packaging/` | winget and Scoop packaging notes and manifests |
| `branding/` | Logo, social preview and their sources |

## Development setup (Windows)

Prerequisites: Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 22+,
pnpm, Rust (MSVC toolchain), Visual Studio C++ Build Tools and a LaTeX
distribution with `latexmk` and LuaLaTeX.

```bash
cd engine && uv sync && uv run pytest
cd desktop && pnpm install && pnpm tauri dev
cd docs/latex && latexmk
```

### Data folders

Development and the installed app never share data:

| What | Folder |
|---|---|
| Installed app (program, runtime and data) | `%LOCALAPPDATA%\Cover_Maker` |
| Engine run from this checkout (`uv run cover-maker …`, `pnpm tauri dev`) | `%LOCALAPPDATA%\Cover_Maker.dev` |
| Tests | a temporary folder (`COVER_MAKER_HOME`) |

`COVER_MAKER_HOME` overrides the folder for any run. The VST3 plugin and the
REAPER script look for a running engine in `Cover_Maker` first and then in
`Cover_Maker.dev`.

## Workflow

1. Open or pick an issue linked to the current milestone.
2. Work on a branch (`mX/<slug>` for milestone work, `fix/<slug>` otherwise).
3. Keep CI green: `ruff`, `pyright`, `pytest`, `prettier`, `eslint`,
   `svelte-check`, `vitest`, `cargo fmt`, `cargo clippy` and the docs build.
4. Update the affected LaTeX documents and `CHANGELOG.md` in the same pull
   request.
