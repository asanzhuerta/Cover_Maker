# Cover_Maker engine

Python engine for Cover_Maker: separation pipeline, library, local API and CLI.

```bash
uv sync
uv run cover-maker --version
uv run pytest
```

The separation runtime (PyTorch, audio-separator) is an optional extra. Pick
the PyTorch build with exactly one of `cpu` or `cu128` (NVIDIA, compute
capability 7.5 or higher):

```bash
uv sync --extra separation --extra cu128
```

The installed app does not use this checkout: it installs the engine wheel and
the locks exported from `uv.lock` (see `desktop/scripts/prepare-runtime.ps1`
and ADR-006).
