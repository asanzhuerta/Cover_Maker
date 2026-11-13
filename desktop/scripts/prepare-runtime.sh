#!/usr/bin/env bash
# Stage the files the macOS app bundles for the first-run bootstrap (ADR-006,
# ADR-013): uv, the engine wheel and one pylock.toml per install profile
# (`core` and `mps`), all taken from engine/uv.lock. The Windows installer uses
# prepare-runtime.ps1. Run before `pnpm tauri build` on a Mac with uv:
#
#   bash desktop/scripts/prepare-runtime.sh
set -euo pipefail

platform="macos-arm64"
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
engine="$repo/engine"
out="$repo/desktop/src-tauri/resources/runtime"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

find "$out" -mindepth 1 -maxdepth 1 ! -name deps.json ! -name README.md ! -name licenses \
  -exec rm -rf {} +

# The app's own licence and the third-party notices travel with the app.
cp "$repo/LICENSE" "$out/licenses/Cover_Maker-LICENSE.txt"
cp "$repo/THIRD_PARTY_NOTICES.md" "$out/licenses/THIRD_PARTY_NOTICES.md"

# uv, pinned by version and hash (deps.json).
read -r url file sha256 < <(uv run --no-project python -c '
import json, sys
uv = json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]]["uv"]
print(uv["urls"][0], uv["file"], uv["sha256"])
' "$out/deps.json" "$platform")
curl --fail --location --silent --show-error --output "$work/$file" "$url"
actual="$(shasum -a 256 "$work/$file" | cut -d ' ' -f 1)"
if [ "$actual" != "$sha256" ]; then
  echo "uv download hash mismatch: $actual" >&2
  exit 1
fi
tar -xzf "$work/$file" -C "$work"
install -m 0755 "$work/${file%.tar.gz}/uv" "$out/uv"

# Engine wheel and lock files.
uv build --wheel --project "$engine" --out-dir "$out"
rm -f "$out/.gitignore"
export_lock() {
  local name="$1"
  shift
  uv export --project "$engine" --frozen --no-dev --no-emit-project --no-header \
    --format pylock.toml "$@" -o "$out/pylock.$name.toml" -q
}
export_lock core
export_lock mps --extra separation --extra mps

# Download and disk sizes per profile, shown before the first-run download.
uv run --no-project python "$repo/desktop/scripts/runtime_sizes.py" "$out" "$platform"
ls -l "$out"
