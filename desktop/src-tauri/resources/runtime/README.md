# Bundled runtime files

`deps.json` pins the downloads used by the first-run bootstrap (uv, ffmpeg,
deno) by URL and SHA-256, per platform: `windows-x64` and `macos-arm64`
(experimental, ADR-013; its `ffmpeg` is `null`, so the engine uses one on
`PATH`). Everything else in this folder is generated before `pnpm tauri build`
and is not committed: `desktop/scripts/prepare-runtime.ps1` on Windows and
`prepare-runtime.sh` on macOS stage `uv` (`uv.exe`), the engine wheel, the
`pylock.*.toml` lock files and `sizes.json`.
`licenses/uv/` holds the licence texts of the bundled uv (MIT and Apache-2.0,
from the uv repository at the pinned tag); the scripts copy the app's
`LICENSE` and `THIRD_PARTY_NOTICES.md` next to them.
