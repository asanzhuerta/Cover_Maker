# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
