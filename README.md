# Cover_Maker

**Local AI stem separation for musicians and producers, on Windows.**

Cover_Maker splits your audio files, or the audio of a video or playlist link
you paste, into the stems you choose (vocals, guitar, drums, bass, piano and
other), or renders a "track without X" (for
example, the song without vocals and guitar) so you can practise, rehearse or
record a cover on top of it. Everything runs locally on your machine.

## Download

Get the installer (`Cover_Maker_<version>_x64-setup.exe`) from the
[Releases page](https://github.com/asanzhuerta/Cover_Maker/releases). The
optional VST3 plugin and REAPER script are attached to the same release. Read
the [code signing policy](#code-signing-policy) and the
[privacy notice](#privacy) below.

## Features

- Pick the stems to extract, or the stems to remove ("track without X").
- Drag and drop local files or whole folders; watched folders are processed
  incrementally.
- Paste a video or playlist link: only the audio is downloaded (via
  [yt-dlp](https://github.com/yt-dlp/yt-dlp)) and separated.
- Preview mixer with synced waveforms and per-stem mute, solo and volume.
- Job queue with per-song progress, pause and cancel.
- Library with re-sync: only new or changed files are processed again.
- Import a playlist file (for example a streaming service data export in JSON,
  CSV, JSPF or M3U) and match it against the audio files you already own.
- Built-in Creative Commons catalogues, with licence and attribution kept.
- Model catalogue showing each AI model's licence and provenance; you choose
  which models to download.
- English and Spanish user interface.
- DAW integration: a REAPER script that inserts each stem as a new track, and
  a VST3 plugin to separate, preview and drag stems into any VST3 host.

## Legal by design

Cover_Maker never searches for, scrapes or matches music on streaming
services. Online audio is fetched only from links you paste yourself, after you
confirm you have the right to use that content. AI model weights are never
bundled or hosted by this project; each model's licence is shown before you
download it. Read [DISCLAIMER.md](DISCLAIMER.md).

## Target hardware

| | Minimum | Recommended |
|---|---|---|
| OS | Windows 10/11 64-bit | Windows 11 |
| CPU | 4 cores / 8 threads, AVX2 | 6–8 cores (2022 or newer) |
| RAM | 16 GB | 32 GB |
| GPU | Optional (CPU mode is slower) | NVIDIA RTX with 8 GB VRAM or more |
| Disk | SSD, 10 GB free | NVMe, 20 GB free or more |

## Tech stack

Tauri 2 + Svelte 5 (TypeScript) desktop shell, Python engine (FastAPI, PyTorch,
`audio-separator`, `yt-dlp`) managed with `uv`, SQLite storage.

## Documentation

Professional documentation (Project Plan, Software Requirements Specification,
Architecture & Design, Test Plan, Installation Guide and User Manual) is written
in LaTeX under `docs/` and attached as PDFs to each release.

## Code signing policy

Windows releases are built from this repository by GitHub Actions
([`release.yml`](.github/workflows/release.yml)) and are meant to be signed
with an Authenticode certificate through the SignPath Foundation's free code
signing programme for open-source projects. Until the project is accepted, the
installer is unsigned and Windows SmartScreen may warn about an unknown
publisher. Once approved, this section will read: *Free code signing provided
by [SignPath.io](https://about.signpath.io), certificate by
[SignPath Foundation](https://signpath.org).*

Only binaries built from this repository's source by the release workflow are
signed: the installer, the Cover_Maker app and its uninstaller, and the VST3
plugin. Third-party programs that the app downloads (uv, Python, ffmpeg, deno,
Python packages) keep their publishers' own signatures and are verified by
SHA-256 hash before use.

Team roles:

- Committers and reviewers: [asanzhuerta](https://github.com/asanzhuerta)
  (owner). Changes from other contributors are reviewed by the owner before
  they are merged.
- Approvers: [asanzhuerta](https://github.com/asanzhuerta). Every release
  signing request is approved manually.

All team members use multi-factor authentication for GitHub and SignPath.

## Privacy

Cover_Maker has no accounts, no telemetry and no analytics: it does not send
your audio, your library or usage data anywhere. Separation runs on your
computer. The app connects to the Internet only for:

- **First run and repairs:** downloading the separation runtime (Python from
  GitHub, packages from PyPI and the PyTorch index, ffmpeg and deno), each
  pinned by hash.
- **Updates:** checking this repository's GitHub Releases for a new version,
  verified by the update signature before it is installed.
- **Models:** downloading an AI model from its original source (Hugging Face
  or GitHub) when you accept it on the Models page.
- **What you ask for:** the video or playlist links you paste (through
  yt-dlp, after you confirm you have the rights), and searches and downloads
  on the Creative Commons sources page (ccMixter, Internet Archive).

Those services receive the usual request data (your IP address and the files
requested) under their own privacy policies. The engine listens only on
`127.0.0.1`; see [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE). The optional VST3 plugin in `daw/vst3` is GPL-3.0-or-later
because of its VST3 bindings. Third-party components and AI models keep their
own licences: see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and
[MODEL_LICENCES.md](MODEL_LICENCES.md).
