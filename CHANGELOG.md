# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed (M9.1)
- While the separation runtime is still installing, the Models and New job
  pages show a notice (EN/ES) and model installs are disabled; the sidebar box
  says "Separation runtime installed" when it finishes.
- A model install that fails because the separation runtime is missing now
  shows a translated message (the engine sends the `separation_missing` code
  with `model.install.failed`) instead of the engine's English text.

### Added (M12: About and credits)
- About page (sidebar, EN/ES): author profile with placeholder photo, name,
  email, website (example.com), bio and contact links (GitHub, email,
  website); app description and source link; credits for the main
  open-source components with licences, a link to `THIRD_PARTY_NOTICES.md`
  and a shortcut to the model licences. All content comes from
  `desktop/src/lib/about.json` (photo in `desktop/static/about/avatar.svg`).
- User Manual chapter "About and credits".

### Added (M9: installer, first run and updates)
- The per-user NSIS installer bundles `uv.exe`, the engine wheel and three
  `pylock.toml` locks (core, CPU, CUDA cu128) exported from `uv.lock`
  (`desktop/scripts/prepare-runtime.ps1`).
- First-run bootstrap in the shell with a setup screen: Python 3.12, the engine
  venv, ffmpeg (LGPL) and deno with pinned SHA-256 into
  `%LOCALAPPDATA%\Cover_Maker\runtime`; then the separation runtime in the
  background (CUDA when the GPU has compute capability 7.5 or higher, else
  CPU), with Retry. Release builds run the engine from the runtime; debug
  builds keep using the repository engine.
- The venv is re-synced with `uv pip sync` after an app update.
- Settings → Updates: Tauri updater (signed `latest.json` on GitHub Releases)
  and "Check for yt-dlp update".
- The uninstaller removes the runtime and, when "Delete the application data"
  is ticked, the user data.
- `release.yml`: on a `v*` tag, builds and signs the installer, mirrors the
  ffmpeg archive and attaches the six PDF documents to a draft release.
- Docs: Installation Guide (installation, first run, updates and removal,
  troubleshooting), deployment view and final ADR-006; third-party notices for
  the shipped components.

### Changed
- `engine/pyproject.toml` has mutually exclusive `cpu` and `cu128` extras that
  pick the PyTorch build; development uses
  `uv sync --extra separation --extra cu128` (or `--extra cpu`).

### Fixed
- Model downloads did nothing: the installer ran `python -m
  audio_separator.utils.cli`, which has no `__main__` guard; it now calls the
  CLI entry point and reports a clear error when no file is downloaded.
- The desktop shell starts the engine with `uv run --inexact`, so the optional
  separation runtime (PyTorch, audio-separator) is no longer removed on start.

### Added
- Start of the v2 rewrite: local, legal-by-design stem separation desktop app.
- MIT licence, README and disclaimer.
- Monorepo skeleton: Python engine (`engine/`, uv, ruff, pyright, pytest) with a
  `cover-maker` CLI, and Tauri 2 + SvelteKit desktop shell (`desktop/`).
- GitHub Actions CI for engine, UI and shell on Windows, and LaTeX docs on Ubuntu.
- LaTeX documentation set with a shared `covermaker` class: Project Plan, SRS,
  Architecture & Design, Test Plan, Installation Guide and User Manual; tables
  generated from `docs/data/*.yaml`.
- Scope: user-pasted video and playlist links (audio downloaded with yt-dlp,
  rights confirmation per job) added to v1.0; documented as accepted risk R-08.
- M1 benchmark spike (`spikes/separation-bench`): separation models measured on
  an RTX 3050 Laptop (4 GB) and an i5-11400H; ADR-001 and ADR-002; measured
  performance requirements.
- M2 spike: `cover-maker serve` with a stdout handshake, per-session token,
  exact-Host and Origin checks and WebSocket first-message auth; Tauri shell
  that starts the engine in a kill-on-close Job Object; multi-stem playback
  page; bootstrap measurement script. ADR-004 to ADR-007.
- M3 engine core: SQLite store with migrations, content-addressed assets,
  model catalogue with licence classes and acceptance, recipe graphs for the
  Fast/Balanced/Max presets, GPU worker process with the out-of-memory
  ladder, mixer for "track without X", cached job runner with crash
  recovery, hardware detection, and the `separate`, `models` and `doctor`
  commands.
- M4 sources and library: video and playlist links through yt-dlp (download
  step cached by video id, rights confirmation stored with the job), watched
  folders, video playlists and imported playlist files (data-export JSON, CSV,
  JSPF, M3U) matched to local files with review and manual correction, and
  the `library` commands.
- M5 local API: system, models (licence-gated install), jobs (create, list,
  detail, cancel, pause, resume, retry) and library endpoints; event stream
  with sequence numbers and replay on reconnect; stable error codes; job thread
  with its own connection; `serve --demo`; `cover-maker openapi` and generated
  TypeScript types checked in CI.
- M6 desktop MVP: welcome screen with terms, hardware tier and model choice;
  new-job page (drag and drop, file/folder dialogs, links, stem chips, mode,
  residual, preset, format, output folder, rights confirmation); live queue
  with pause/resume/cancel/retry; models page with licence dialog; settings
  (language EN/ES, theme, defaults); typed API client and event reconnection.
- Export mode `both` (#21): one job writes the selected stems and the song
  without them from a single separation (engine, CLI `--mode both`, API and
  the New job page).
- Producer-oriented redesign (#23, #24): dark theme as the default look,
  per-stem colours and hand-drawn SVG icons, stem cards, mode cards, waveform
  progress bars in the queue, richer model cards with size/VRAM meters, and a
  welcome hero with a three-step wizard (terms → hardware → models).
- Model catalogue entries now record `licence_url` and `verified_on`, shown in
  the licence dialog (#25).
- M7 preview mixer: finished queue items open a mixer that plays the mix and
  every stem in sync from one AudioContext (ADR-007), with per-stem mute, solo
  and volume, residual keep/drop, seek, drag-to-loop, A/B against the original
  and waveforms from engine-computed peaks. Stems decode lazily and long songs
  use a reduced preview sample rate. *Export this mix* renders the current
  settings with the same formula. Engine: preview data per item (migration 3),
  `GET /items/{id}/preview`, `GET /assets/{sha}`, `GET /assets/{sha}/peaks` and
  `POST /items/{id}/render`.
- M11 (DAW integration: VST3 plugin and REAPER extension) added to the roadmap.
- Contribution guide, security policy, code of conduct, issue/PR templates and
  Dependabot configuration.

### Changed
- Model licence data re-verified at the original sources on 2026-11-03 (#25):
  HT Demucs weights reclassified from `disputed` to `non-commercial` (the
  author limits them to personal or research use), Kim Mel-Band's MIT licence
  confirmed in its model card, and more precise sources for BS-RoFormer SW and
  Resurrection. Changed notices must be accepted again.

### Fixed
- The queue's *Open folder* button did nothing: it now reveals the first
  exported file (or the output folder) in Explorer with `revealItemInDir`,
  which the default opener permission allows (#22).
