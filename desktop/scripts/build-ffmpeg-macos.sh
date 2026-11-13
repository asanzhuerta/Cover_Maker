#!/usr/bin/env bash
# Build the LGPL ffmpeg that the macOS runtime installs (ADR-013), on a Mac
# with Apple Silicon and the Xcode Command Line Tools:
#
#   bash desktop/scripts/build-ffmpeg-macos.sh <output-dir>
#
# The result is <output-dir>/ffmpeg-n9.0.2-macos-arm64-lgpl.zip, laid out like
# the Windows build that the bootstrap already reads: the programs in bin/ and
# the licence texts next to them, plus SOURCE.md with the exact sources and
# configure line (the LGPL asks for the source to be available).
#
# Everything is pinned: FFmpeg by the object id of its signed release tag,
# LAME (MP3 encoding, LGPL) by the SHA-256 of its release tarball. The build
# links only to macOS system libraries, never --enable-gpl or nonfree code.
set -euo pipefail

FFMPEG_TAG="n9.0.2"
FFMPEG_TAG_OBJECT="ce8f11b9fac4cd7ccfb41ca7c01bc17f5cda8cc3"
FFMPEG_REPO="https://github.com/FFmpeg/FFmpeg.git"
LAME_VERSION="3.100"
LAME_URL="https://downloads.sourceforge.net/project/lame/lame/3.100/lame-3.100.tar.gz"
LAME_SHA256="ddfe36cab873794038ae2c1210557ad34857a4b6bdc515785d1da9e175b1da1e"
NAME="ffmpeg-${FFMPEG_TAG}-macos-arm64-lgpl"
MIN_MACOS="12.3"

out="$(mkdir -p "${1:?usage: build-ffmpeg-macos.sh <output-dir>}" && cd "$1" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
prefix="$work/prefix"
jobs="$(sysctl -n hw.ncpu)"
export MACOSX_DEPLOYMENT_TARGET="$MIN_MACOS"

# LAME, static.
curl --fail --location --silent --show-error --retry 3 --output "$work/lame.tar.gz" "$LAME_URL"
actual="$(shasum -a 256 "$work/lame.tar.gz" | cut -d ' ' -f 1)"
if [ "$actual" != "$LAME_SHA256" ]; then
  echo "LAME download hash mismatch: $actual" >&2
  exit 1
fi
tar -xzf "$work/lame.tar.gz" -C "$work"
(
  cd "$work/lame-$LAME_VERSION"
  ./configure --prefix="$prefix" --disable-shared --enable-static --disable-frontend \
    --disable-dependency-tracking --enable-nasm=no
  make -j"$jobs" install
)

# FFmpeg at the pinned tag.
git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$FFMPEG_TAG" \
  "$FFMPEG_REPO" "$work/ffmpeg"
tag_object="$(git -C "$work/ffmpeg" rev-parse "refs/tags/$FFMPEG_TAG")"
if [ "$tag_object" != "$FFMPEG_TAG_OBJECT" ]; then
  echo "FFmpeg tag $FFMPEG_TAG is $tag_object, expected $FFMPEG_TAG_OBJECT" >&2
  exit 1
fi
commit="$(git -C "$work/ffmpeg" rev-parse HEAD)"

# Only what the engine and yt-dlp use: every native demuxer and decoder,
# PCM and MP3 (LAME) encoding, file input/output. --disable-autodetect keeps
# out any library the build machine happens to have; zlib and AudioToolbox
# are part of macOS.
configure=(
  --prefix="$work/ffmpeg-install"
  --arch=arm64 --enable-static --disable-shared
  --disable-autodetect --enable-zlib --enable-audiotoolbox
  --enable-libmp3lame
  --disable-doc --disable-ffplay --disable-debug --disable-network
  --extra-cflags="-I$prefix/include -mmacosx-version-min=$MIN_MACOS"
  --extra-ldflags="-L$prefix/lib -mmacosx-version-min=$MIN_MACOS"
)
(
  cd "$work/ffmpeg"
  ./configure "${configure[@]}"
  make -j"$jobs"
  make install
)

# Refuse a build that is not LGPL or links to anything outside the system.
license="$("$work/ffmpeg-install/bin/ffmpeg" -hide_banner -L)"
echo "$license"
if ! grep -q "GNU Lesser General Public" <<<"$license"; then
  echo "the build is not LGPL" >&2
  exit 1
fi
for program in ffmpeg ffprobe; do
  if otool -L "$work/ffmpeg-install/bin/$program" | tail -n +2 \
      | grep -v -E '^\s+(/usr/lib/|/System/Library/)'; then
    echo "$program links to a non-system library" >&2
    exit 1
  fi
done

stage="$work/$NAME"
mkdir -p "$stage/bin"
install -m 0755 "$work/ffmpeg-install/bin/ffmpeg" "$work/ffmpeg-install/bin/ffprobe" "$stage/bin/"
cp "$work/ffmpeg/COPYING.LGPLv2.1" "$work/ffmpeg/COPYING.LGPLv3" "$stage/"
cp "$work/ffmpeg/LICENSE.md" "$stage/LICENSE-ffmpeg.md"
cp "$work/lame-$LAME_VERSION/COPYING" "$stage/COPYING-lame"
cat > "$stage/SOURCE.md" <<EOF
# ffmpeg for Cover_Maker on macOS (Apple Silicon)

LGPL-2.1-or-later build of FFmpeg with LAME (LGPL-2.0-or-later), made by
desktop/scripts/build-ffmpeg-macos.sh in https://github.com/asanzhuerta/Cover_Maker.

- FFmpeg $FFMPEG_TAG, $FFMPEG_REPO, tag object $FFMPEG_TAG_OBJECT, commit $commit
- LAME $LAME_VERSION, $LAME_URL, SHA-256 $LAME_SHA256
- Minimum macOS: $MIN_MACOS
- FFmpeg configure: ${configure[*]}
EOF
# Fixed timestamps and order, so the archive depends only on its contents.
find "$stage" -exec touch -h -t 202601010000 {} +
rm -f "$out/$NAME.zip"
(cd "$work" && find "$NAME" | LC_ALL=C sort | zip -q -X -@ "$out/$NAME.zip")
(cd "$out" && shasum -a 256 "$NAME.zip")
