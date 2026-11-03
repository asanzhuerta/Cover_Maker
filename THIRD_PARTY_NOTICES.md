# Third-party notices

Cover_Maker is MIT-licensed. It depends on third-party software that keeps its
own licence. A full, generated list will be published from milestone M10.

AI model weights are **not** distributed with Cover_Maker. They are downloaded
by the user from their original sources after reviewing each model's licence in
the in-app catalogue.

## Shipped with the installer or installed on first run

| Component | Licence | Source |
|---|---|---|
| [uv](https://github.com/astral-sh/uv) (bundled `uv.exe`) | MIT or Apache-2.0 | https://github.com/astral-sh/uv |
| [Tauri](https://tauri.app) and its plugins (desktop shell) | MIT or Apache-2.0 | https://github.com/tauri-apps/tauri |
| [Python](https://www.python.org) 3.12, standalone build | PSF-2.0 | https://github.com/astral-sh/python-build-standalone |
| [FFmpeg](https://ffmpeg.org), LGPL shared build by BtbN | LGPL-2.1-or-later | https://github.com/BtbN/FFmpeg-Builds (sources: https://ffmpeg.org/download.html) |
| [deno](https://deno.com) | MIT | https://github.com/denoland/deno |
| [PyTorch](https://pytorch.org) | BSD-3-Clause | https://github.com/pytorch/pytorch |
| [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) | MIT | https://github.com/nomadkaraoke/python-audio-separator |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense | https://github.com/yt-dlp/yt-dlp |

FFmpeg is used as an unmodified separate program (`ffmpeg.exe` and its DLLs in
`%LOCALAPPDATA%\Cover_Maker\runtime\bin`), downloaded from the pinned build in
`desktop/src-tauri/resources/runtime/deps.json` and mirrored on each GitHub
release. You may replace it with another build of the same version.
