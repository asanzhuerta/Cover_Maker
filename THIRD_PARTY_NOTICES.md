# Third-party notices

Cover_Maker is MIT-licensed (see `LICENSE`). It ships with, or downloads on
first run, third-party software that keeps its own licence. This file lists
them. It was reviewed on 2026-11-03 (milestone M9.2) and is not legal advice.
The list of the Rust crates and JavaScript packages compiled into the desktop
shell is generated in milestone M10.

AI model weights are **not** distributed with Cover_Maker. You download them
from their original sources after reviewing each model's licence in the
in-app catalogue (Models page).

## Licences that restrict how you may use the app

- **diffq-fixed** (CC BY-NC 4.0, non-commercial) is required by the Demucs
  backend of audio-separator and is installed with the separation runtime.
  Using the Demucs models commercially may therefore be restricted.
- **Model weights** have their own terms, shown before each download. The
  catalogue marks the HT Demucs models as non-commercial, and models whose
  authors published no licence as "none": no rights are granted for those.
- Everything else below is under a permissive licence (MIT, BSD, Apache-2.0,
  ISC, MPL-2.0, PSF, Unlicense) or the LGPL (FFmpeg; soxr; libsndfile inside
  soundfile), which allows use as separate programs or libraries.

## Bundled in the installer

| Component | Licence | Notes |
|---|---|---|
| [uv](https://github.com/astral-sh/uv) (`uv.exe`) | MIT or Apache-2.0 | Licence texts in `bundle\licenses\uv` of the install folder |
| [Tauri](https://tauri.app), its plugins and the shell's Rust crates | MIT or Apache-2.0 (mostly) | Full list generated in M10 |
| [Svelte](https://svelte.dev), SvelteKit and the UI's JavaScript packages | MIT (mostly) | Full list generated in M10 |
| Microsoft Edge WebView2 | Microsoft software licence | Not bundled: the installer downloads Microsoft's bootstrapper only when WebView2 is missing |

The installer also copies this file and Cover_Maker's `LICENSE` to
`bundle\licenses`.

## Downloaded on first run

| Component | Licence | Source |
|---|---|---|
| [Python](https://www.python.org) 3.12, python-build-standalone | PSF-2.0; its bundled libraries (OpenSSL, SQLite, zlib…) under their own permissive licences | https://github.com/astral-sh/python-build-standalone |
| [FFmpeg](https://ffmpeg.org) 9.0, LGPL shared build by BtbN | LGPL-3.0-or-later | https://github.com/BtbN/FFmpeg-Builds (sources: https://ffmpeg.org/download.html) |
| [deno](https://deno.com) | MIT | https://github.com/denoland/deno |
| [PyTorch](https://pytorch.org) | BSD-3-Clause | https://github.com/pytorch/pytorch |
| NVIDIA CUDA runtime libraries (CUDA build of PyTorch only) | NVIDIA software licence (redistributable components) | Inside the PyTorch wheel from download.pytorch.org |

FFmpeg is used as an unmodified separate program (`ffmpeg.exe` and its DLLs in
`%LOCALAPPDATA%\Cover_Maker\runtime\bin`); its licence text is copied to
`runtime\licenses\ffmpeg`. It is downloaded from the pinned build in
`desktop/src-tauri/resources/runtime/deps.json` and mirrored, unmodified, on
each GitHub release. The corresponding source code is available from
https://ffmpeg.org/download.html and the build scripts from BtbN's repository.
You may replace it with another build of the same version.

### Python packages of the runtime

Every package installed from `pylock.cu128.toml`, with the licence declared in
its metadata. The CPU profile has the same packages with the CPU build of
PyTorch. Regenerate the table with `docs/tools/python_licences.py`.

| Package | Version | Licence |
|---|---|---|
| absl-py | 2.5.1 | Apache-2.0 |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.16.0 | MIT |
| audio-separator | 0.48.0 | MIT |
| audioread | 3.1.0 | MIT |
| beartype | 0.18.5 | MIT |
| brotli | 1.2.1 | MIT |
| certifi | 2026.10.23 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| cloudpickle | 3.1.2 | BSD-3-Clause |
| colorama | 0.4.6 | BSD License |
| cython | 3.3.1 | Apache-2.0 |
| decorator | 5.3.1 | BSD-2-Clause |
| diffq-fixed | 0.2.4 | Creative Commons Attribution-NonCommercial 4.0 International |
| einops | 0.8.2 | MIT |
| fastapi | 0.162.0 | MIT |
| filelock | 4.2.7 | MIT |
| flatbuffers | 25.12.19 | Apache 2.0 |
| fsspec | 2026.9.0 | BSD-3-Clause |
| h11 | 0.16.0 | MIT |
| idna | 3.20 | BSD-3-Clause |
| jinja2 | 3.1.6 | BSD License |
| joblib | 1.6.0 | BSD-3-Clause |
| julius | 0.2.8 | MIT License |
| lazy-loader | 0.6 | BSD-3-Clause |
| librosa | 1.0.0 | ISC |
| llvmlite | 0.50.0 | BSD-2-Clause AND Apache-2.0 WITH LLVM-exception |
| markdown-it-py | 4.2.0 | MIT License |
| markupsafe | 3.0.4 | BSD-3-Clause |
| mdurl | 0.1.2 | MIT License |
| ml-collections | 1.1.0 | Apache Software License |
| ml-dtypes | 0.6.0 | Apache-2.0 |
| mpmath | 1.3.0 | BSD |
| msgpack | 1.2.4 | Apache-2.0 |
| narwhals | 2.28.0 | MIT |
| networkx | 3.7 | BSD-3-Clause |
| numba | 0.68.1 | BSD |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| onnx-weekly | 1.24.0.dev20261102 | Apache-2.0 |
| onnx2torch-py313 | 1.6.0 | Apache License |
| onnxruntime | 1.31.1 | MIT License |
| opentelemetry-api | 1.45.2 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pillow | 13.0.0 | MIT-CMU |
| platformdirs | 4.14.3 | MIT |
| pooch | 1.9.0 | BSD-3-Clause |
| protobuf | 7.36.2 | 3-Clause BSD License |
| psutil | 7.2.2 | BSD-3-Clause |
| pycparser | 3.12 | BSD-3-Clause |
| pycryptodomex | 3.24.1 | BSD, Public Domain |
| pydantic | 2.14.2 | MIT |
| pydantic-core | 2.50.2 | MIT |
| pydub | 0.25.1 | MIT |
| pygments | 2.21.0 | BSD-2-Clause |
| pyyaml | 6.0.3 | MIT |
| requests | 2.34.2 | Apache-2.0 |
| resampy | 0.4.3 | ISC |
| rich | 15.0.0 | MIT |
| rotary-embedding-torch | 0.6.5 | MIT |
| samplerate | 0.1.0 | MIT |
| scikit-learn | 1.9.1 | BSD-3-Clause |
| scipy | 1.18.1 | BSD License |
| setuptools | 81.0.0 | MIT |
| shellingham | 1.5.4 | ISC License |
| six | 1.17.0 | MIT |
| soundfile | 0.14.0 | BSD 3-Clause License (bundles libsndfile, LGPL-2.1-or-later) |
| soxr | 1.1.0 | LGPL-2.1-or-later |
| starlette | 1.10.0 | BSD-3-Clause |
| sympy | 1.14.0 | BSD |
| threadpoolctl | 3.7.0 | BSD-3-Clause |
| tinytag | 2.3.2 | MIT License |
| torch | 2.11.0+cu128 | BSD-3-Clause |
| torchvision | 0.26.0 | BSD |
| tqdm | 4.70.1 | MPL-2.0 AND MIT |
| typer | 0.27.3 | MIT |
| typing-extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.4 | MIT |
| urllib3 | 2.8.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| websockets | 17.4 | BSD-3-Clause |
| yt-dlp | 2026.10.26 | Unlicense |
| yt-dlp-ejs | 0.8.0 | Unlicense AND MIT AND ISC |
