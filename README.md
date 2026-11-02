# Cover_Maker

**Local AI stem separation for musicians and producers, on Windows.**

Cover_Maker splits *your own* audio files into the stems you choose — vocals,
guitar, drums, bass, piano and other — or renders a "track without X" (for
example, the song without vocals and guitar) so you can practise, rehearse or
record a cover on top of it. Everything runs locally on your machine.

> **Status:** v2 is being rewritten from scratch. There is no usable release yet.
> Follow the [milestones](https://github.com/asanzhuerta/Cover_Maker/milestones)
> for progress.

## Planned features (v1.0)

- Pick the stems to extract, or the stems to remove ("track without X").
- Drag and drop local files or whole folders; watched folders are processed
  incrementally.
- Preview mixer with synced waveforms and per-stem mute, solo and volume.
- Job queue with per-song progress, pause and cancel.
- Library with re-sync: only new or changed files are processed again.
- Import a playlist file (for example a streaming service data export in JSON,
  CSV, JSPF or M3U) and match it against the audio files you already own.
- Built-in Creative Commons catalogues, with licence and attribution kept.
- Model catalogue showing each AI model's licence and provenance; you choose
  which models to download.
- English and Spanish user interface.

## Legal by design

Cover_Maker does **not** download audio from streaming platforms and does not
integrate with their APIs. It only processes files you provide or content from
catalogues with an explicit Creative Commons licence. AI model weights are never
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
`audio-separator`) managed with `uv`, SQLite storage.

## Documentation

Professional documentation (Project Plan, Software Requirements Specification,
Architecture & Design, Test Plan, Installation Guide and User Manual) is written
in LaTeX under `docs/` and attached as PDFs to each release.

## License

[MIT](LICENSE). Third-party components and AI models keep their own licences.
