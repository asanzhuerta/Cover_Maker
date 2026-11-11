# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Lead and backing vocals: new stems `vocals.lead` and `vocals.backing` that
  split the vocals with the BS-RoFormer karaoke model by anvuew (GPL-3.0,
  about 200 MB, downloaded on request like every model). Each preset runs it
  on its separated vocals, so the split is cached and reuses vocals already
  separated. Extract either part or remove it ("track without lead vocals"
  keeps the backing vocals); the mixer shows lead and backing lanes in place
  of the vocals, and the mixer maths treat sub-stems as parts of their parent
  with both residual modes. New stem cards and colours in New job (English
  and Spanish), requirement FR-SEP-04, a User Manual section and a benchmark
  row for the RTX 3050 Laptop.
- Practice tools (M14). The engine analyses each song once, after decoding:
  tuning offset from A440 in cents, key (major or minor), tempo, beats and bar
  starts, with librosa (no model weights). Results are stored in SQLite
  (migration 6) and served by `GET /items/{id}/analysis`, computed on demand
  for songs separated earlier. The LCD now shows BPM, key and tuning as played.
- Real-time pitch (-12 to +12 semitones plus fine cents) and tempo (50-150 %
  without pitch change) in the mixer, with one Signalsmith Stretch (MIT)
  worklet on the master bus; *Tune to A440* cancels a recording's detuning.
  Knobs work with the keyboard; `[` `]` change the tempo and `-` `+` the pitch.
- Loops that snap to bar lines, named section markers saved with the song
  (`PUT /items/{id}/markers`), a section loop button, one bar of count-in and
  a click stem from the beat grid.
- Speed trainer: raises the tempo by a step every N loop passes up to a
  target, with the tempo and pass count in the LCD.
- Exports with the chosen pitch and tempo: `POST /items/{id}/render` takes
  `tempo`, `semitones`, `cents`, `click_gain` and `with_stems`; the engine
  uses the same chain as the preview (resample, then Signalsmith Stretch via
  `python-stretch`, MIT), and can also write every stem and the click.
- Practice chapter in the User Manual, ADR-010, requirements FR-PRA-01 to
  FR-PRA-06 and NFR-PERF-05.
- DAW session export: *Export DAW session* in the mixer
  (`POST /items/{id}/session`) writes a folder with every stem, the residual
  and the original mix as WAV files aligned at 0, a REAPER project (`.RPP`), a
  DAWproject file (Bitwig Studio, Studio One, Cubase) and a MIDI tempo map for
  any other DAW. Tracks keep the mixer's volume, pan and mute; the projects
  carry the tempo map fitted to the beat grid (with a pickup bar when the song
  starts mid-bar), the section markers and the key. Pure-Python writers; the
  DAWproject XML is validated against the official schema in the tests
  (`xmlschema`, development only). ADR-011, requirement FR-DAW-03.

### Security
- Release workflow: the tag name reaches run scripts through an environment
  variable instead of `${{ }}` interpolation (script injection).
- Every GitHub Action is pinned to a full commit SHA with its version in a
  comment; Dependabot keeps the pins up to date.
- Dependency cooldown of 7 days for Dependabot (all ecosystems) and for uv
  resolution (`exclude-newer = "7 days"`).
- Catalogue requests use an HTTPS-only opener (no `file:` or `ftp:` handler)
  and may only reach the catalogue hosts; Internet Archive identifiers are
  URL-quoted.
- Job item updates accept only known column names.
- The content security policy allows `'wasm-unsafe-eval'` scripts for the
  stretch worklet's WebAssembly; the worklet is served from the app itself, so
  no `blob:` scripts are allowed.

### Changed
- New visual identity, *Tape & Console* (warm analogue hardware), with the
  descriptor "the cover musician's studio": warm near-black and cream
  surfaces, one signal-orange accent, a cream-paper light theme, new stem
  colours, bundled Archivo SemiExpanded and IBM Plex fonts (SIL OFL 1.1), a
  tape-reel logo, new app icons and favicon, and the same colours in the VST3
  plugin and the documents. The old violet and pink gradients are gone.
- A 64 px icon rail replaces the side bar; page names show on hover and
  keyboard focus.
- Engine and runtime status are lights in the amber display at the bottom
  right instead of a box at the bottom left of the side bar.

### Added
- Transport dock at the bottom of every page: the song opened in the mixer
  keeps playing while you visit other pages, with play, loop, A/B, a scrub
  waveform, an output meter and the display (clock, and slots for tempo, key
  and tuning that a later version fills).
- Mixer: pan knob per stem, applied the same way in the preview and in the
  exported mix (`RenderRequest.pans`); LED level meters per stem with
  peak-programme ballistics; console faders.
- Keyboard shortcuts: Space, M/S, 1-6, up/down, L, A, left/right and `?` for
  the shortcut help. They do nothing while you type in a field.
- Page content rises into place on every page change; all motion is off with
  the system's reduced-motion setting.
- *Retry* next to the runtime notice when the separation runtime failed to
  install.
- First run asks before downloading: the setup screen shows the download
  size, the approximate disk space, the free space on the drive, the PyTorch
  build and the folder, and stops with a clear message when the drive is too
  full. The sizes come from the bundled lock files (`sizes.json`).
- The model licence dialog shows the download size and the free disk space,
  and the engine refuses a model download that does not fit
  (`507 not_enough_space`).
- Library page: *Temporary files* lists what stopped or failed jobs left
  behind, deletes it after showing exactly what goes (`GET /storage/temporary`,
  `POST /storage/temporary/clear`), and opens the folder in Explorer.

### Added (Interface languages)
- The interface is now also in Portuguese (Brazil), French, German and
  Italian, community-maintained translations next to English and Spanish.
  The About page texts are translated too.
- The installer offers the same six languages and the app starts in the one
  you pick; without an installer choice it follows the Windows language,
  falling back to the same language from another region (`pt-PT` → `pt-BR`,
  `fr-CA` → `fr`) and then to English.
- *Settings* marks community translations and links to the new translation
  guide, [docs/TRANSLATING.md](docs/TRANSLATING.md), with a style guide and a
  glossary of music terms.
- The page language (`<html lang>`) follows the interface language.

### Changed (Interface languages)
- The strings moved from `i18n.svelte.ts` to one file per language in
  `desktop/src/lib/i18n/`, each typed against the English source, so a
  missing or unknown key fails `pnpm check`. A new CI step,
  `pnpm check:i18n`, also reports empty strings and changed `{placeholders}`.

### Added (Launch: download and repository)
- First-run quick start (#95): the last welcome step shows the model, or
  models, that the recommended preset uses on this PC with their licence
  notices, installs them with one click once accepted, then offers *Try it
  with the example song*, which separates a bundled Creative Commons clip
  ("Airplane Mode" by Josh Woodward, CC BY 4.0, a 28 s excerpt with fades) into all six stems and
  opens the queue. *Use the example song* on *New job* adds the same clip.
  Its stems come with a `CREDITS.txt` that also states the changes made.
  API: `GET /example`, `POST /example` and `SystemOut.recommended_models`
  (FR-UI-02).
- Stable download link (#93): every release also carries the installer as
  `Cover_Maker_x64-setup.exe`, so
  `https://github.com/asanzhuerta/Cover_Maker/releases/latest/download/Cover_Maker_x64-setup.exe`
  always serves the newest version, plus `SHA256SUMS.txt`. The versioned
  installer and `latest.json` stay for the updater.
- winget and Scoop (#94): publishing a draft release runs `wingetcreate
  update` (pinned, hash-checked) when a `WINGET_TOKEN` secret exists, and
  `packaging/scoop/cover-maker.json` is ready for the Extras bucket, with
  `checkver` and `autoupdate`. `packaging/README.md` lists the one-time setup.
- New README (#91) in English and Spanish (`README.es.md`): download button,
  demo and screenshots made with the demo engine and the example song, the
  three promises, a feature grid, a comparison with subscription apps and
  basic splitters, measured timings, FAQ, contributing and credits.
- Social preview image (#92): `branding/social-preview.png` (1280 x 640) and
  its HTML source.
- Installation Guide 1.1 and User Manual 1.2: the stable link, checksums,
  package managers and the quick start.

### Changed
- Project Plan 1.1: the roadmap after a competitive review. A new visual
  identity (M13) ships before 1.0, followed by practice tools (M14), a cover
  studio for recording audio and video (M15) and rehearsal with setlists
  (M16), plus a launch plan and risks R-09 to R-13.

### Fixed
- A second song separated with the same model in one session no longer
  fails with `FileNotFoundError`: the reused model wrote its stems into the
  previous job's temporary folder.

### Changed
- Development runs (the engine from a source checkout, `pnpm tauri dev`) keep
  their data in `%LOCALAPPDATA%\Cover_Maker.dev`, apart from the installed
  app's `%LOCALAPPDATA%\Cover_Maker`. The VST3 plugin and the REAPER script
  find either.

### Added (M10: quality and 1.0)
- Presets tuned from measured runs: every separation attempt is recorded
  (migration 5); GPU settings that ran out of memory twice in a row for a
  model are skipped, and *Automatic* picks Fast instead of Balanced when
  Balanced was measured slower than 1.5 times the song length.
  `GET /system` reports the measured speed per preset.
- `MODEL_LICENCES.md` and a User Manual appendix list each catalogue model's
  licence, source and verification date (generated from the catalogue).
- All six documents at version 1.0; the SRS includes the traceability
  matrix, the Installation Guide explains what the installer downloads and how
  it is verified, and the Test Report covers v1.0.0.

### Added (M11: DAW integration)
- REAPER script (`daw/reaper`): separates the selected item's song (or a
  typed file or link) and inserts each stem as a new track below it, lined up
  with the song.
- VST3 plugin (`daw/vst3`, GPL-3.0-or-later): separate a file or link from
  inside any VST3 host, preview each stem through the track and drag the stem
  files onto tracks. Release builds attach the plugin and the script.
- Engine discovery for DAW tools: while it runs the engine writes
  `%LOCALAPPDATA%\Cover_Maker\run\engine.json` with its port and a separate
  client token, in a folder only the user can read; set
  `COVER_MAKER_DAW_ACCESS=0` to turn it off (ADR-008, NFR-SEC-02).
- Docs: User Manual DAW chapter, ADR-008, FR-DAW-01/02, third-party notices
  of the plugin.

### Added (M8: library UI)
- A re-sync now shows what changed in the collection: new, removed,
  unchanged, to check and not available songs.
- "Select new" ticks only the matched songs without separated stems, so only
  what is new is sent to a job.

## [0.3.0] - 2026-11-04

Library page, Creative Commons sources, title and artist in the queue,
actionable errors, diagnostic reports, complete third-party notices and the
test report (M8, M10).

### Added (M10: quality)
- Actionable errors: failed songs in the queue show a translated hint with
  the next step (memory, missing model, ffmpeg, downloads, moved files…).
- Diagnostic report (Settings → Diagnostics, `POST /diagnostics`): a zip with
  versions, hardware, runtime state, models, recent jobs and the engine log,
  with personal folders, link paths and tokens redacted and no audio. The
  engine now keeps failures in `logs/engine.log` (rotating).
- `THIRD_PARTY_NOTICES.md` lists every Rust crate of the shell and every
  JavaScript package of the UI as well as the Python runtime, generated by
  `docs/tools/notices.py` (replaces `python_licences.py`).
- Test report and a requirement → test traceability matrix, generated from
  `docs/data/traceability.yaml`; an engine test fails if a requirement has no
  verification or cites a test that does not exist.
- Accessibility: skip-to-content link, `aria-current` on the active page,
  the engine status announced politely, a labelled main menu.

### Added (M8: library UI, matching and CC catalogues)
- Library page: watched folders, video playlists and imported playlist files
  as collections, with re-sync, removal, each song's match state, the stems
  already exported for it, match review (choose file, not available) and
  "Separate selected", which opens the songs on the New job page.
- Disk space: library, freeable cache, models and temporary files, with a
  "Free space" clean-up that keeps what the mixer needs (`GET /storage`,
  `POST /storage/cleanup`); finished jobs can be removed from the history
  (`DELETE /jobs/{id}`).
- CC sources page: search ccMixter and the Internet Archive (Creative Commons
  and public-domain results only), with licence, NC/ND badges and a warning
  for no-derivatives licences. Internet Archive tracks download into the
  library; ccMixter files are downloaded on its site and attached, since it
  blocks automated downloads. Every file keeps a `.credits.json`, and exports
  made from it write `CREDITS.txt`.
- Docs: User Manual chapters on the library, match review, disk space, your
  own videos and CC sources; Compliance section on the CC catalogues.

### Added
- The queue shows each song's title and artist instead of only the file name
  or link: from the file's tags (or an "Artist - Title" file name) when the
  job is submitted, and from the video's metadata (track and artist, else
  title and channel) before a link downloads. The engine stores them per item
  (migration 4) and sends `item.meta` events.

## [0.2.1] - 2026-11-04

Second test build: the guided first run, the installer language, model
download progress, the centred layout and the licence review (M9.2).

### Added (M9.2: first-run guide and polish)
- Welcome: step 2 "Preparing your PC" explains the background separation
  runtime with its live status and where to watch it; step 3 shows an
  illustrative preview of the Models page and what happens next (#34).
- The installer asks for the language (English or Spanish); the app starts in
  it on first run (#35).
- Model downloads show a green progress bar with the percentage (engine event
  `model.install.progress`) (#36).
- About: the author's real profile (#39).

### Changed (M9.2)
- Wider sidebar; page content is centred next to it (#38).
- Licence review (#37): mutagen (GPL) replaced by tinytag (MIT) and dropped
  from yt-dlp's extras; FFmpeg's licence corrected to LGPL-3.0-or-later and
  its text kept in `runtime\licenses`; uv's licence texts, the app licence and
  the notices are bundled with the installer; `THIRD_PARTY_NOTICES.md` lists
  every Python package of the runtime and the non-commercial diffq-fixed.
- Docs: tables and long code names no longer run past the page edge; the
  Project Plan's milestone table includes M9.2 and M12.

## [0.2.0] - 2026-11-03

First installable build, published for testing. Earlier work is listed
below by milestone.

### Changed (branding)
- Official logo in `branding/logo.svg` (the sidebar's gradient waveform mark)
  with a 1024 px PNG export; the app, installer and taskbar icons and the UI
  favicon are generated from it instead of the Tauri and Svelte defaults.

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
