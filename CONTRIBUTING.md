# Contributing to Cover_Maker

Thanks for your interest in improving Cover_Maker.

## Ground rules

- **Legal by design.** Do not add features that download or capture audio from
  streaming platforms, or that use their APIs to locate music. Do not add
  commercial recordings to tests, examples, screenshots or documentation; use
  synthetic audio or Creative Commons material with attribution.
- **Model weights are never committed or hosted here.** New catalogue entries
  must state licence and provenance.
- Code, commit messages and documentation are written in English.

## Repository layout

| Path | Contents |
|---|---|
| `engine/` | Python engine (uv project): pipeline, library, API, CLI |
| `desktop/` | Tauri 2 shell + SvelteKit/TypeScript UI |
| `docs/latex/` | Project documentation (LaTeX) |

## Development setup (Windows)

Prerequisites: Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 22+,
pnpm, Rust (MSVC toolchain), Visual Studio C++ Build Tools and a LaTeX
distribution with `latexmk` and LuaLaTeX.

```bash
cd engine && uv sync && uv run pytest
cd desktop && pnpm install && pnpm tauri dev
cd docs/latex && latexmk
```

## Workflow

1. Open or pick an issue linked to the current milestone.
2. Work on a branch (`mX/<slug>` for milestone work, `fix/<slug>` otherwise).
3. Keep CI green: `ruff`, `pyright`, `pytest`, `prettier`, `eslint`,
   `svelte-check`, `vitest`, `cargo fmt`, `cargo clippy` and the docs build.
4. Update the affected LaTeX documents and `CHANGELOG.md` in the same pull
   request.
