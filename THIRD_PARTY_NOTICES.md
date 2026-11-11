# Third-party notices

Cover_Maker is MIT-licensed (see `LICENSE`). It ships with, or downloads on
first run, third-party software that keeps its own licence. This file lists
them. It was reviewed on 2026-11-03 (milestone M9.2) and is not legal advice.
The tables of packages are generated with `docs/tools/notices.py`.

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
  ISC, MPL-2.0, PSF, Unlicense, SIL Open Font License 1.1) or the LGPL (FFmpeg; soxr; libsndfile inside
  soundfile), which allows use as separate programs or libraries.

## Bundled in the installer

| Component | Licence | Notes |
|---|---|---|
| [uv](https://github.com/astral-sh/uv) (`uv.exe`) | MIT or Apache-2.0 | Licence texts in `bundle\licenses\uv` of the install folder |
| [Tauri](https://tauri.app), its plugins and the shell's Rust crates | MIT or Apache-2.0 (mostly) | Listed below |
| [Svelte](https://svelte.dev), SvelteKit and the UI's JavaScript packages | MIT (mostly) | Listed below |
| Archivo SemiExpanded, IBM Plex Sans and IBM Plex Mono fonts | SIL Open Font License 1.1 | Listed below |
| Example song: "Airplane Mode" by Josh Woodward, 28-second excerpt with fades | CC BY 4.0 | In the engine package; see [Example song](#example-song) |
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
PyTorch.

<!-- generated:python -->
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
| python-stretch | 0.3.1 | MIT |
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
<!-- /generated:python -->

## Compiled into the installer

### Rust crates of the desktop shell

The crates linked into `cover-maker-desktop.exe` for Windows, with the licence
declared in each crate's manifest.

<!-- generated:rust -->
| Crate | Version | Licence |
|---|---|---|
| adler2 | 2.0.1 | 0BSD OR MIT OR Apache-2.0 |
| aho-corasick | 1.1.5 | Unlicense OR MIT |
| alloc-no-stdlib | 3.0.0 | BSD-3-Clause |
| alloc-stdlib | 0.3.0 | BSD-3-Clause |
| anyhow | 1.0.104 | MIT OR Apache-2.0 |
| atomic-waker | 1.1.2 | Apache-2.0 OR MIT |
| base64 | 0.23.1 | MIT OR Apache-2.0 |
| bit-set | 0.8.0 | Apache-2.0 OR MIT |
| bit-vec | 0.8.0 | Apache-2.0 OR MIT |
| bitflags | 2.13.2 | MIT OR Apache-2.0 |
| bitflags | 1.3.2 | MIT/Apache-2.0 |
| block-buffer | 0.12.1 | MIT OR Apache-2.0 |
| block-buffer | 0.10.4 | MIT OR Apache-2.0 |
| brotli | 9.1.1 | BSD-3-Clause AND MIT |
| brotli-decompressor | 6.2.0 | BSD-3-Clause/MIT |
| bs58 | 0.5.1 | MIT/Apache-2.0 |
| bumpalo | 3.20.3 | MIT OR Apache-2.0 |
| byteorder | 1.5.0 | Unlicense OR MIT |
| bytes | 1.12.1 | MIT |
| camino | 1.2.6 | MIT OR Apache-2.0 |
| cargo-platform | 0.1.9 | MIT OR Apache-2.0 |
| cargo_metadata | 0.19.2 | MIT |
| cfb | 0.14.0 | MIT |
| cfg-if | 1.0.5 | MIT OR Apache-2.0 |
| chrono | 0.4.45 | MIT OR Apache-2.0 |
| const-oid | 0.10.2 | Apache-2.0 OR MIT |
| cookie | 0.18.2 | MIT OR Apache-2.0 |
| cookie_store | 0.22.1 | MIT OR Apache-2.0 |
| cpufeatures | 0.2.17 | MIT OR Apache-2.0 |
| cpufeatures | 0.3.1 | MIT OR Apache-2.0 |
| crc32fast | 1.5.4 | MIT OR Apache-2.0 |
| crossbeam-channel | 0.5.17 | MIT OR Apache-2.0 |
| crossbeam-utils | 0.8.23 | MIT OR Apache-2.0 |
| crypto-common | 0.1.7 | MIT OR Apache-2.0 |
| crypto-common | 0.2.2 | MIT OR Apache-2.0 |
| cssparser | 0.37.0 | MPL-2.0 |
| cssparser-macros | 0.7.1 | MPL-2.0 |
| ctor | 1.0.13 | Apache-2.0 OR MIT |
| darling | 0.24.1 | MIT |
| darling_core | 0.24.1 | MIT |
| darling_macro | 0.24.1 | MIT |
| defmt | 1.2.0 | MIT OR Apache-2.0 |
| defmt-macros | 1.2.0 | MIT OR Apache-2.0 |
| defmt-parser | 1.1.0 | MIT OR Apache-2.0 |
| deranged | 0.5.9 | MIT OR Apache-2.0 |
| derive_more | 2.1.1 | MIT |
| derive_more-impl | 2.1.1 | MIT |
| digest | 0.10.7 | MIT OR Apache-2.0 |
| digest | 0.11.3 | MIT OR Apache-2.0 |
| dirs | 7.0.0 | MIT OR Apache-2.0 |
| dirs-sys | 0.5.0 | MIT OR Apache-2.0 |
| displaydoc | 0.2.7 | MIT OR Apache-2.0 |
| document-features | 0.2.12 | MIT OR Apache-2.0 |
| dom_query | 0.28.0 | MIT |
| dpi | 0.1.2 | Apache-2.0 AND MIT |
| dtoa | 1.0.11 | MIT OR Apache-2.0 |
| dtoa-short | 0.3.5 | MPL-2.0 |
| dunce | 1.0.5 | CC0-1.0 OR MIT-0 OR Apache-2.0 |
| dyn-clone | 1.0.20 | MIT OR Apache-2.0 |
| equivalent | 1.0.3 | Apache-2.0 OR MIT |
| erased-serde | 0.4.11 | MIT OR Apache-2.0 |
| fastrand | 2.5.0 | Apache-2.0 OR MIT |
| fdeflate | 0.3.7 | MIT OR Apache-2.0 |
| flate2 | 1.1.10 | MIT OR Apache-2.0 |
| fnv | 1.0.7 | Apache-2.0 / MIT |
| foldhash | 0.2.0 | Zlib |
| form_urlencoded | 1.2.2 | MIT OR Apache-2.0 |
| futures-channel | 0.3.34 | MIT OR Apache-2.0 |
| futures-core | 0.3.34 | MIT OR Apache-2.0 |
| futures-io | 0.3.34 | MIT OR Apache-2.0 |
| futures-macro | 0.3.34 | MIT OR Apache-2.0 |
| futures-sink | 0.3.34 | MIT OR Apache-2.0 |
| futures-task | 0.3.34 | MIT OR Apache-2.0 |
| futures-util | 0.3.34 | MIT OR Apache-2.0 |
| generic-array | 0.14.7 | MIT |
| getrandom | 0.2.17 | MIT OR Apache-2.0 |
| getrandom | 0.3.4 | MIT OR Apache-2.0 |
| getrandom | 0.4.3 | MIT OR Apache-2.0 |
| glob | 0.3.4 | MIT OR Apache-2.0 |
| hashbrown | 0.17.1 | MIT OR Apache-2.0 |
| hashbrown | 0.12.3 | MIT OR Apache-2.0 |
| heck | 0.5.0 | MIT OR Apache-2.0 |
| hex | 0.4.3 | MIT OR Apache-2.0 |
| html5ever | 0.39.0 | MIT OR Apache-2.0 |
| http | 1.5.0 | MIT OR Apache-2.0 |
| http-body | 1.1.0 | MIT |
| http-body-util | 0.1.5 | MIT |
| httparse | 1.10.1 | MIT OR Apache-2.0 |
| hybrid-array | 0.4.15 | MIT OR Apache-2.0 |
| hyper | 1.12.0 | MIT |
| hyper-rustls | 0.27.10 | Apache-2.0 OR ISC OR MIT |
| hyper-util | 0.1.21 | MIT |
| ico | 0.6.0 | MIT |
| icu_collections | 2.4.0 | Unicode-3.0 |
| icu_locale_core | 2.4.0 | Unicode-3.0 |
| icu_normalizer | 2.4.0 | Unicode-3.0 |
| icu_normalizer_data | 2.4.0 | Unicode-3.0 |
| icu_properties | 2.4.0 | Unicode-3.0 |
| icu_properties_data | 2.4.0 | Unicode-3.0 |
| icu_provider | 2.4.0 | Unicode-3.0 |
| ident_case | 1.0.1 | MIT/Apache-2.0 |
| idna | 1.1.0 | MIT OR Apache-2.0 |
| idna_adapter | 1.2.2 | Apache-2.0 OR MIT |
| indexmap | 2.14.2 | Apache-2.0 OR MIT |
| indexmap | 1.9.3 | Apache-2.0 OR MIT |
| infer | 0.22.0 | MIT |
| ipnet | 2.12.2 | MIT OR Apache-2.0 |
| itoa | 1.0.18 | MIT OR Apache-2.0 |
| jiff | 0.2.39 | Unlicense OR MIT |
| jiff-core | 0.1.2 | Unlicense OR MIT |
| jiff-tzdb | 0.1.9 | Unlicense OR MIT |
| jiff-tzdb-platform | 0.1.3 | Unlicense OR MIT |
| json-patch | 4.2.0 | MIT/Apache-2.0 |
| jsonptr | 0.7.1 | MIT OR Apache-2.0 |
| keyboard-types | 0.8.3 | MIT OR Apache-2.0 |
| libc | 0.2.191 | MIT OR Apache-2.0 |
| litemap | 0.8.3 | Unicode-3.0 |
| litrs | 1.0.1 | MIT OR Apache-2.0 |
| lock_api | 0.4.14 | MIT OR Apache-2.0 |
| log | 0.4.35 | MIT OR Apache-2.0 |
| markup5ever | 0.39.0 | MIT OR Apache-2.0 |
| memchr | 2.8.3 | Unlicense OR MIT |
| mime | 0.3.17 | MIT OR Apache-2.0 |
| minisign-verify | 0.3.0 | MIT |
| miniz_oxide | 0.9.1 | MIT OR Zlib OR Apache-2.0 |
| miniz_oxide | 0.8.9 | MIT OR Zlib OR Apache-2.0 |
| mio | 1.2.4 | MIT |
| muda | 0.20.0 | Apache-2.0 OR MIT |
| new_debug_unreachable | 1.0.6 | MIT |
| num-conv | 0.2.2 | MIT OR Apache-2.0 |
| num-traits | 0.2.19 | MIT OR Apache-2.0 |
| once_cell | 1.21.4 | MIT OR Apache-2.0 |
| open | 5.4.5 | MIT |
| option-ext | 0.2.0 | MPL-2.0 |
| parking_lot | 0.12.5 | MIT OR Apache-2.0 |
| parking_lot_core | 0.9.12 | MIT OR Apache-2.0 |
| percent-encoding | 2.3.2 | MIT OR Apache-2.0 |
| phf | 0.13.1 | MIT |
| phf_generator | 0.13.1 | MIT |
| phf_macros | 0.13.1 | MIT |
| phf_shared | 0.13.1 | MIT |
| pin-project-lite | 0.2.17 | Apache-2.0 OR MIT |
| plist | 1.10.3 | MIT |
| png | 0.18.1 | MIT OR Apache-2.0 |
| potential_utf | 0.1.6 | Unicode-3.0 |
| powerfmt | 0.2.1 | MIT OR Apache-2.0 |
| precomputed-hash | 0.1.1 | MIT |
| proc-macro2 | 1.0.107 | MIT OR Apache-2.0 |
| quick-xml | 0.42.0 | MIT |
| quote | 1.0.47 | MIT OR Apache-2.0 |
| raw-window-handle | 0.6.2 | MIT OR Apache-2.0 OR Zlib |
| ref-cast | 1.0.27 | MIT OR Apache-2.0 |
| ref-cast-impl | 1.0.27 | MIT OR Apache-2.0 |
| regex | 1.13.1 | MIT OR Apache-2.0 |
| regex-automata | 0.4.18 | MIT OR Apache-2.0 |
| regex-syntax | 0.8.11 | MIT OR Apache-2.0 |
| reqwest | 0.13.5 | MIT OR Apache-2.0 |
| rfd | 0.17.2 | MIT |
| ring | 0.17.14 | Apache-2.0 AND ISC |
| rustc-hash | 2.1.3 | Apache-2.0 OR MIT |
| rustls | 0.23.46 | Apache-2.0 OR ISC OR MIT |
| rustls-pki-types | 1.15.1 | MIT OR Apache-2.0 |
| rustls-platform-verifier | 0.7.1 | MIT OR Apache-2.0 |
| rustls-webpki | 0.103.16 | ISC |
| same-file | 1.0.6 | Unlicense/MIT |
| schemars | 1.2.3 | MIT |
| schemars | 0.9.0 | MIT |
| schemars | 0.8.22 | MIT |
| schemars_derive | 0.8.22 | MIT |
| scopeguard | 1.2.0 | MIT OR Apache-2.0 |
| selectors | 0.38.0 | MPL-2.0 |
| semver | 1.0.28 | MIT OR Apache-2.0 |
| serde | 1.0.229 | MIT OR Apache-2.0 |
| serde-untagged | 0.1.9 | MIT OR Apache-2.0 |
| serde_core | 1.0.229 | MIT OR Apache-2.0 |
| serde_derive | 1.0.229 | MIT OR Apache-2.0 |
| serde_derive_internals | 0.29.1 | MIT OR Apache-2.0 |
| serde_json | 1.0.154 | MIT OR Apache-2.0 |
| serde_repr | 0.1.21 | MIT OR Apache-2.0 |
| serde_spanned | 1.1.2 | MIT OR Apache-2.0 |
| serde_with | 3.24.0 | MIT OR Apache-2.0 |
| serde_with_macros | 3.24.0 | MIT OR Apache-2.0 |
| serialize-to-javascript | 0.1.2 | MIT OR Apache-2.0 |
| serialize-to-javascript-impl | 0.1.2 | MIT OR Apache-2.0 |
| servo_arc | 0.4.3 | MIT OR Apache-2.0 |
| sha2 | 0.11.1 | MIT OR Apache-2.0 |
| sha2 | 0.10.9 | MIT OR Apache-2.0 |
| simd-adler32 | 0.3.10 | MIT |
| siphasher | 1.0.4 | MIT OR Apache-2.0 |
| slab | 0.4.12 | MIT |
| smallvec | 1.16.4 | MIT OR Apache-2.0 |
| socket2 | 0.6.5 | MIT OR Apache-2.0 |
| softbuffer | 0.4.8 | MIT OR Apache-2.0 |
| stable_deref_trait | 1.2.1 | MIT OR Apache-2.0 |
| string_cache | 0.9.0 | MIT OR Apache-2.0 |
| strsim | 0.11.1 | MIT |
| subtle | 2.6.1 | BSD-3-Clause |
| syn | 2.0.119 | MIT OR Apache-2.0 |
| syn | 3.0.9 | MIT OR Apache-2.0 |
| sync_wrapper | 1.0.2 | Apache-2.0 |
| synstructure | 0.14.0 | MIT |
| tao | 0.37.2 | Apache-2.0 |
| tauri | 2.12.5 | Apache-2.0 OR MIT |
| tauri-codegen | 2.7.4 | Apache-2.0 OR MIT |
| tauri-macros | 2.7.4 | Apache-2.0 OR MIT |
| tauri-plugin-dialog | 2.8.4 | Apache-2.0 OR MIT |
| tauri-plugin-fs | 2.7.1 | Apache-2.0 OR MIT |
| tauri-plugin-opener | 2.7.2 | Apache-2.0 OR MIT |
| tauri-plugin-process | 2.4.0 | Apache-2.0 OR MIT |
| tauri-plugin-updater | 2.14.1 | Apache-2.0 OR MIT |
| tauri-runtime | 2.12.2 | Apache-2.0 OR MIT |
| tauri-runtime-wry | 2.12.3 | Apache-2.0 OR MIT |
| tauri-utils | 2.10.2 | Apache-2.0 OR MIT |
| tempfile | 3.27.0 | MIT OR Apache-2.0 |
| tendril | 0.5.1 | MIT OR Apache-2.0 |
| thiserror | 2.0.21 | MIT OR Apache-2.0 |
| thiserror-impl | 2.0.21 | MIT OR Apache-2.0 |
| time | 0.3.55 | MIT OR Apache-2.0 |
| time-core | 0.1.9 | MIT OR Apache-2.0 |
| time-macros | 0.2.32 | MIT OR Apache-2.0 |
| tinystr | 0.8.5 | Unicode-3.0 |
| tinyvec | 1.13.3 | Zlib OR Apache-2.0 OR MIT |
| tokio | 1.54.1 | MIT |
| tokio-rustls | 0.26.6 | MIT OR Apache-2.0 |
| tokio-util | 0.7.20 | MIT |
| toml | 1.1.8+spec-1.1.0 | MIT OR Apache-2.0 |
| toml_datetime | 1.1.2+spec-1.1.0 | MIT OR Apache-2.0 |
| toml_parser | 1.1.5+spec-1.1.0 | MIT OR Apache-2.0 |
| toml_writer | 1.1.3+spec-1.1.0 | MIT OR Apache-2.0 |
| tower | 0.5.3 | MIT |
| tower-http | 0.6.11 | MIT |
| tower-layer | 0.3.3 | MIT |
| tower-service | 0.3.3 | MIT |
| tracing | 0.1.44 | MIT |
| tracing-attributes | 0.1.31 | MIT |
| tracing-core | 0.1.36 | MIT |
| tray-icon | 0.25.1 | MIT OR Apache-2.0 |
| try-lock | 0.2.5 | MIT |
| typed-path | 0.13.0 | MIT OR Apache-2.0 |
| typeid | 1.0.3 | MIT OR Apache-2.0 |
| typenum | 1.20.1 | MIT OR Apache-2.0 |
| unicode-ident | 1.0.27 | (MIT OR Apache-2.0) AND Unicode-3.0 |
| unicode-segmentation | 1.13.3 | MIT OR Apache-2.0 |
| untrusted | 0.9.0 | ISC |
| ureq | 3.5.1 | MIT OR Apache-2.0 |
| ureq-proto | 0.7.1 | MIT OR Apache-2.0 |
| url | 2.5.8 | MIT OR Apache-2.0 |
| urlpattern | 0.6.0 | MIT |
| utf8-zero | 0.8.1 | MIT OR Apache-2.0 |
| utf8_iter | 1.1.0 | Apache-2.0 OR MIT |
| utf_types | 1.0.0 | Apache-2.0 OR MIT |
| uuid | 1.29.0 | Apache-2.0 OR MIT |
| walkdir | 2.5.0 | Unlicense/MIT |
| want | 0.3.2 | MIT |
| web-time | 1.1.0 | MIT OR Apache-2.0 |
| web_atoms | 0.2.6 | MIT OR Apache-2.0 |
| webpki-roots | 1.0.11 | CDLA-Permissive-2.0 |
| webview2-com | 0.39.1 | MIT |
| webview2-com-macros | 0.8.1 | MIT |
| webview2-com-sys | 0.39.1 | MIT |
| winapi-util | 0.1.11 | Unlicense OR MIT |
| window-vibrancy | 0.8.1 | Apache-2.0 OR MIT |
| windows | 0.62.2 | MIT OR Apache-2.0 |
| windows | 0.61.3 | MIT OR Apache-2.0 |
| windows-collections | 0.3.2 | MIT OR Apache-2.0 |
| windows-collections | 0.2.0 | MIT OR Apache-2.0 |
| windows-core | 0.62.2 | MIT OR Apache-2.0 |
| windows-core | 0.61.2 | MIT OR Apache-2.0 |
| windows-future | 0.2.1 | MIT OR Apache-2.0 |
| windows-future | 0.3.2 | MIT OR Apache-2.0 |
| windows-implement | 0.60.2 | MIT OR Apache-2.0 |
| windows-interface | 0.59.3 | MIT OR Apache-2.0 |
| windows-link | 0.1.3 | MIT OR Apache-2.0 |
| windows-link | 0.2.1 | MIT OR Apache-2.0 |
| windows-numerics | 0.3.1 | MIT OR Apache-2.0 |
| windows-numerics | 0.2.0 | MIT OR Apache-2.0 |
| windows-registry | 0.6.1 | MIT OR Apache-2.0 |
| windows-result | 0.3.4 | MIT OR Apache-2.0 |
| windows-result | 0.4.1 | MIT OR Apache-2.0 |
| windows-strings | 0.4.2 | MIT OR Apache-2.0 |
| windows-strings | 0.5.1 | MIT OR Apache-2.0 |
| windows-sys | 0.61.2 | MIT OR Apache-2.0 |
| windows-threading | 0.2.1 | MIT OR Apache-2.0 |
| windows-threading | 0.1.0 | MIT OR Apache-2.0 |
| windows-version | 0.1.7 | MIT OR Apache-2.0 |
| winnow | 1.0.4 | MIT |
| writeable | 0.6.4 | Unicode-3.0 |
| wry | 0.57.1 | Apache-2.0 OR MIT |
| yoke | 0.8.4 | Unicode-3.0 |
| yoke-derive | 0.8.4 | Unicode-3.0 |
| zerofrom | 0.1.8 | Unicode-3.0 |
| zerofrom-derive | 0.1.8 | Unicode-3.0 |
| zeroize | 1.9.1 | Apache-2.0 OR MIT |
| zerotrie | 0.2.5 | Unicode-3.0 |
| zerovec | 0.11.9 | Unicode-3.0 |
| zerovec-derive | 0.11.7 | Unicode-3.0 |
| zip | 9.3.0 | MIT |
| zlib-rs | 0.6.8 | Zlib |
| zmij | 1.0.23 | MIT |
| zopfli | 0.8.4 | Apache-2.0 |
<!-- /generated:rust -->

### JavaScript packages of the user interface

The production packages of the user interface, plus the Svelte and SvelteKit
runtimes that the build bundles into it.

<!-- generated:javascript -->
| Package | Version | Licence |
|---|---|---|
| @sveltejs/kit | 2.70.3 | MIT |
| @tauri-apps/api | 2.12.4 | Apache-2.0 OR MIT |
| @tauri-apps/plugin-dialog | 2.8.4 | MIT OR Apache-2.0 |
| @tauri-apps/plugin-opener | 2.7.2 | MIT OR Apache-2.0 |
| @tauri-apps/plugin-process | 2.4.0 | MIT OR Apache-2.0 |
| @tauri-apps/plugin-updater | 2.14.1 | MIT OR Apache-2.0 |
| openapi-fetch | 0.17.0 | MIT |
| openapi-typescript-helpers | 0.1.0 | MIT |
| signalsmith-stretch | 1.3.2 | MIT |
| svelte | 5.57.3 | MIT |
<!-- /generated:javascript -->

The practice tools (M14) use the [Signalsmith Stretch](https://github.com/Signalsmith-Audio/signalsmith-stretch)
library by Signalsmith Audio (MIT), with its Signalsmith Linear helpers (MIT):
compiled to WebAssembly in `signalsmith-stretch` for the mixer preview, and as a
Python extension in `python-stretch` (MIT, which also contains nanobind,
BSD-3-Clause) for exports. No Rubber Band (GPL) or SoundTouch (LGPL) code is
used.

### Fonts of the user interface

Bundled as WOFF2 files in `desktop/static/fonts`, each folder with its
licence text (`OFL.txt`). The app never loads fonts from the network.

| Font | Version | Source | Licence |
|---|---|---|---|
| Archivo SemiExpanded (Medium, SemiBold, Bold) | 2.66, commit `2111276` | [Omnibus-Type/Archivo](https://github.com/Omnibus-Type/Archivo) | SIL OFL 1.1, Copyright 2020 The Archivo Project Authors |
| IBM Plex Sans (Regular, Italic, Medium, SemiBold) | 1.1.0 | [IBM/plex](https://github.com/IBM/plex) | SIL OFL 1.1, Copyright 2017 IBM Corp., Reserved Font Name "Plex" |
| IBM Plex Mono (Regular, Medium, SemiBold) | 2.5.0 | [IBM/plex](https://github.com/IBM/plex) | SIL OFL 1.1, Copyright 2017 IBM Corp., Reserved Font Name "Plex" |

### Example song

The engine package includes a short clip for *Try it with the example song*
on first run:
`engine/src/cover_maker/data/example/josh-woodward-airplane-mode-excerpt.mp3`.

- **Work:** "Airplane Mode" by Josh Woodward,
  <https://www.joshwoodward.com/song/AirplaneMode>
- **Licence:** Creative Commons Attribution 4.0 International (CC BY 4.0),
  <https://creativecommons.org/licenses/by/4.0/>
- **Changes:** this is a modified version: an excerpt from 0:45 to 1:13
  (28 s) with a fade-in and a fade-out, re-encoded as MP3 (256 kbps).
- **Obtained from:** the Internet Archive copy of the single,
  <https://archive.org/details/jamendo-124697>, which lists CC BY 3.0; the
  author's site offers the song under CC BY 4.0.

Stems and mixes made from the clip are adaptations under the same terms: every
export writes this attribution, with the changes, to a `CREDITS.txt` next to
the stems.

## VST3 plugin

The optional VST3 plugin in `daw/vst3` is distributed separately under the
**GNU General Public License v3.0 or later** (`daw/vst3/COPYING`), because the
VST3 bindings it uses (`vst3-sys`, through NIH-plug) are GPLv3. The rest of
Cover_Maker stays under the MIT licence. VST is a registered trademark of
Steinberg Media Technologies GmbH. The crates linked into the plugin:

<!-- generated:vst3 -->
| Crate | Version | Licence |
|---|---|---|
| ab_glyph | 0.2.32 | Apache-2.0 |
| ab_glyph_rasterizer | 0.1.10 | Apache-2.0 |
| ahash | 0.8.12 | MIT OR Apache-2.0 |
| anyhow | 1.0.104 | MIT OR Apache-2.0 |
| anymap3 | 1.1.0 | BlueOak-1.0.0 OR MIT OR Apache-2.0 |
| atomic_float | 0.1.0 | Apache-2.0 OR MIT OR Zlib |
| atomic_refcell | 0.1.14 | Apache-2.0 OR MIT |
| atty | 0.2.14 | MIT |
| backtrace | 0.3.77 | MIT OR Apache-2.0 |
| base64 | 0.22.1 | MIT OR Apache-2.0 |
| baseview | 0.1.0 | MIT OR Apache-2.0 |
| bitflags | 1.3.2 | MIT/Apache-2.0 |
| bitflags | 2.13.2 | MIT OR Apache-2.0 |
| bytemuck | 1.25.2 | Zlib OR Apache-2.0 OR MIT |
| bytemuck_derive | 1.12.1 | Zlib OR Apache-2.0 OR MIT |
| cfg-if | 1.0.5 | MIT OR Apache-2.0 |
| clap-sys | 0.5.0 | MIT/Apache-2.0 |
| clipboard-win | 5.4.3 | BSL-1.0 |
| copypasta | 0.10.2 | MIT / Apache-2.0 |
| crossbeam | 0.8.5 | MIT OR Apache-2.0 |
| crossbeam-channel | 0.5.17 | MIT OR Apache-2.0 |
| crossbeam-deque | 0.8.8 | MIT OR Apache-2.0 |
| crossbeam-epoch | 0.9.21 | MIT OR Apache-2.0 |
| crossbeam-queue | 0.3.14 | MIT OR Apache-2.0 |
| crossbeam-utils | 0.8.23 | MIT OR Apache-2.0 |
| cursor-icon | 1.2.0 | MIT OR Apache-2.0 OR Zlib |
| deranged | 0.5.9 | MIT OR Apache-2.0 |
| displaydoc | 0.2.7 | MIT OR Apache-2.0 |
| dpi | 0.1.2 | Apache-2.0 AND MIT |
| ecolor | 0.31.1 | MIT OR Apache-2.0 |
| egui | 0.31.1 | MIT OR Apache-2.0 |
| egui-baseview | 0.5.0 | MIT |
| egui_glow | 0.31.1 | MIT OR Apache-2.0 |
| emath | 0.31.1 | MIT OR Apache-2.0 |
| epaint | 0.31.1 | MIT OR Apache-2.0 |
| epaint_default_fonts | 0.31.1 | (MIT OR Apache-2.0) AND OFL-1.1 AND Ubuntu-font-1.0 |
| error-code | 3.4.0 | BSL-1.0 |
| form_urlencoded | 1.2.2 | MIT OR Apache-2.0 |
| getrandom | 0.2.17 | MIT OR Apache-2.0 |
| glow | 0.16.0 | MIT OR Apache-2.0 OR Zlib |
| hound | 3.5.1 | Apache-2.0 |
| icu_collections | 2.4.0 | Unicode-3.0 |
| icu_locale_core | 2.4.0 | Unicode-3.0 |
| icu_normalizer | 2.4.0 | Unicode-3.0 |
| icu_normalizer_data | 2.4.0 | Unicode-3.0 |
| icu_properties | 2.4.0 | Unicode-3.0 |
| icu_properties_data | 2.4.0 | Unicode-3.0 |
| icu_provider | 2.4.0 | Unicode-3.0 |
| idna | 1.1.0 | MIT OR Apache-2.0 |
| idna_adapter | 1.2.2 | Apache-2.0 OR MIT |
| itoa | 1.0.18 | MIT OR Apache-2.0 |
| keyboard-types | 0.6.2 | MIT/Apache-2.0 |
| litemap | 0.8.3 | Unicode-3.0 |
| lock_api | 0.4.14 | MIT OR Apache-2.0 |
| log | 0.4.35 | MIT OR Apache-2.0 |
| memchr | 2.8.3 | Unlicense OR MIT |
| memoffset | 0.9.1 | MIT |
| midi-consts | 0.1.0 | MIT OR Apache-2.0 |
| nih_log | 0.3.1 | ISC |
| nih_plug | 0.0.0 | ISC |
| nih_plug_derive | 0.1.0 | ISC |
| nih_plug_egui | 0.0.0 | ISC |
| nohash-hasher | 0.2.0 | Apache-2.0 OR MIT |
| num-conv | 0.2.2 | MIT OR Apache-2.0 |
| once_cell | 1.21.4 | MIT OR Apache-2.0 |
| open | 5.4.5 | MIT |
| owned_ttf_parser | 0.25.1 | Apache-2.0 |
| parking_lot | 0.12.5 | MIT OR Apache-2.0 |
| parking_lot_core | 0.9.12 | MIT OR Apache-2.0 |
| percent-encoding | 2.3.2 | MIT OR Apache-2.0 |
| pin-project-lite | 0.2.17 | Apache-2.0 OR MIT |
| potential_utf | 0.1.6 | Unicode-3.0 |
| powerfmt | 0.2.1 | MIT OR Apache-2.0 |
| proc-macro2 | 1.0.107 | MIT OR Apache-2.0 |
| profiling | 1.0.18 | MIT OR Apache-2.0 |
| quote | 1.0.47 | MIT OR Apache-2.0 |
| raw-window-handle | 0.6.2 | MIT OR Apache-2.0 OR Zlib |
| raw-window-handle | 0.5.2 | MIT OR Apache-2.0 OR Zlib |
| rustc-demangle | 0.1.28 | MIT/Apache-2.0 |
| scopeguard | 1.2.0 | MIT OR Apache-2.0 |
| serde | 1.0.229 | MIT OR Apache-2.0 |
| serde_core | 1.0.229 | MIT OR Apache-2.0 |
| serde_derive | 1.0.229 | MIT OR Apache-2.0 |
| serde_json | 1.0.154 | MIT OR Apache-2.0 |
| smallvec | 1.16.4 | MIT OR Apache-2.0 |
| smol_str | 0.2.2 | MIT OR Apache-2.0 |
| stable_deref_trait | 1.2.1 | MIT OR Apache-2.0 |
| syn | 1.0.109 | MIT OR Apache-2.0 |
| syn | 3.0.9 | MIT OR Apache-2.0 |
| syn | 2.0.119 | MIT OR Apache-2.0 |
| synstructure | 0.14.0 | MIT |
| termcolor | 1.4.1 | Unlicense OR MIT |
| thiserror | 2.0.21 | MIT OR Apache-2.0 |
| thiserror-impl | 2.0.21 | MIT OR Apache-2.0 |
| time | 0.3.55 | MIT OR Apache-2.0 |
| time-core | 0.1.9 | MIT OR Apache-2.0 |
| time-macros | 0.2.32 | MIT OR Apache-2.0 |
| tinystr | 0.8.5 | Unicode-3.0 |
| tracing | 0.1.44 | MIT |
| tracing-core | 0.1.36 | MIT |
| ttf-parser | 0.25.1 | MIT OR Apache-2.0 |
| unicode-ident | 1.0.27 | (MIT OR Apache-2.0) AND Unicode-3.0 |
| unicode-segmentation | 1.13.3 | MIT OR Apache-2.0 |
| ureq | 2.12.1 | MIT OR Apache-2.0 |
| url | 2.5.8 | MIT OR Apache-2.0 |
| utf8_iter | 1.1.0 | Apache-2.0 OR MIT |
| utf_types | 1.0.0 | Apache-2.0 OR MIT |
| uuid | 0.8.2 | Apache-2.0 OR MIT |
| vst3-com | 0.1.0 | MIT |
| vst3-com-macros | 0.2.0 | MIT |
| vst3-com-macros-support | 0.2.0 | MIT |
| vst3-sys | 0.1.0 | GPLv3 |
| widestring | 1.2.1 | MIT OR Apache-2.0 |
| winapi | 0.3.9 | MIT/Apache-2.0 |
| winapi-util | 0.1.11 | Unlicense OR MIT |
| windows | 0.44.0 | MIT OR Apache-2.0 |
| windows | 0.58.0 | MIT OR Apache-2.0 |
| windows-core | 0.58.0 | MIT OR Apache-2.0 |
| windows-implement | 0.58.0 | MIT OR Apache-2.0 |
| windows-interface | 0.58.0 | MIT OR Apache-2.0 |
| windows-link | 0.2.1 | MIT OR Apache-2.0 |
| windows-result | 0.2.0 | MIT OR Apache-2.0 |
| windows-strings | 0.1.0 | MIT OR Apache-2.0 |
| windows-sys | 0.52.0 | MIT OR Apache-2.0 |
| windows-sys | 0.61.2 | MIT OR Apache-2.0 |
| windows-targets | 0.52.6 | MIT OR Apache-2.0 |
| windows-targets | 0.42.2 | MIT OR Apache-2.0 |
| windows_x86_64_msvc | 0.42.2 | MIT OR Apache-2.0 |
| windows_x86_64_msvc | 0.52.6 | MIT OR Apache-2.0 |
| winit | 0.30.13 | Apache-2.0 |
| writeable | 0.6.4 | Unicode-3.0 |
| yoke | 0.8.4 | Unicode-3.0 |
| yoke-derive | 0.8.4 | Unicode-3.0 |
| zerocopy | 0.8.63 | BSD-2-Clause OR Apache-2.0 OR MIT |
| zerofrom | 0.1.8 | Unicode-3.0 |
| zerofrom-derive | 0.1.8 | Unicode-3.0 |
| zerotrie | 0.2.5 | Unicode-3.0 |
| zerovec | 0.11.9 | Unicode-3.0 |
| zerovec-derive | 0.11.7 | Unicode-3.0 |
| zmij | 1.0.23 | MIT |
<!-- /generated:vst3 -->
