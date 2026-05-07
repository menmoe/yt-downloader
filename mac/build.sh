#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  build.sh  —  Packages yt_downloader_gui.py into a standalone
#               macOS .app (no Python required to run the result)
#
#  Usage:
#    chmod +x build.sh
#    ./build.sh
#
#  Output:  ./dist/YT Downloader.app
#  Just double-click it — no Python, no terminal needed.
# ─────────────────────────────────────────────────────────────

set -e

APP_NAME="YT Downloader"
SCRIPT="yt_downloader_gui.py"

echo ""
echo "══════════════════════════════════════════════"
echo "   YT Downloader — Build Script"
echo "══════════════════════════════════════════════"
echo ""

# ── 1. Check Python ────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌  python3 not found. Install it from https://python.org"
  exit 1
fi
echo "✔  Python: $(python3 --version)"

# ── 2. Install / upgrade pip dependencies ─────────────────────
echo ""
echo "📦  Installing dependencies…"
python3 -m pip install --upgrade --quiet pip
python3 -m pip install --quiet yt-dlp certifi pyinstaller

echo "✔  Dependencies installed"

# ── 3. Locate certifi's cacert.pem so PyInstaller bundles it ──
CERTIFI_PATH=$(python3 -c "import certifi; print(certifi.where())")
echo "✔  certifi CA bundle: $CERTIFI_PATH"

# ── 4. Locate ffmpeg (warn if missing, but don't abort) ────────
FFMPEG_PATH=$(command -v ffmpeg || true)
if [ -z "$FFMPEG_PATH" ]; then
  echo ""
  echo "⚠   ffmpeg not found on PATH."
  echo "    MP3 conversion and MP4 re-encoding won't work without it."
  echo "    Install it with:  brew install ffmpeg"
  echo "    Then re-run this script."
  echo ""
  FFMPEG_ARGS=""
else
  echo "✔  ffmpeg: $FFMPEG_PATH"
  # Bundle the ffmpeg binary into the app so it truly needs nothing installed
  FFMPEG_ARGS="--add-binary \"$FFMPEG_PATH:.\""

  # Also grab ffprobe if present (yt-dlp uses it)
  FFPROBE_PATH=$(command -v ffprobe || true)
  if [ -n "$FFPROBE_PATH" ]; then
    FFMPEG_ARGS="$FFMPEG_ARGS --add-binary \"$FFPROBE_PATH:.\""
    echo "✔  ffprobe: $FFPROBE_PATH"
  fi
fi

# ── 5. Clean previous build ────────────────────────────────────
echo ""
echo "🧹  Cleaning previous build…"
rm -rf build dist "${APP_NAME}.spec"

# ── 6. Run PyInstaller ─────────────────────────────────────────
echo ""
echo "🔨  Building app (this takes ~30–60 seconds)…"
echo ""

eval python3 -m PyInstaller \
  --noconfirm \
  --windowed \
  --onedir \
  --name "$APP_NAME" \
  --add-data "$CERTIFI_PATH:certifi" \
  $FFMPEG_ARGS \
  --hidden-import "yt_dlp" \
  --hidden-import "yt_dlp.extractor" \
  --hidden-import "yt_dlp.postprocessor" \
  --hidden-import "certifi" \
  --collect-all "yt_dlp" \
  --collect-all "certifi" \
  "$SCRIPT"

# ── 7. Patch the bundled app to find ffmpeg at runtime ─────────
# PyInstaller places extra binaries in Contents/MacOS/
# yt-dlp looks for ffmpeg on PATH, so we set PATH in a launcher wrapper.
APP_PATH="dist/${APP_NAME}.app"
MACOS_DIR="$APP_PATH/Contents/MacOS"
REAL_BIN="${APP_NAME}"          # the real binary PyInstaller created

if [ -f "$MACOS_DIR/$REAL_BIN" ]; then
  mv "$MACOS_DIR/$REAL_BIN" "$MACOS_DIR/${REAL_BIN}_bin"
  cat > "$MACOS_DIR/$REAL_BIN" <<LAUNCHER
#!/bin/bash
DIR="\$(cd "\$(dirname "\$0")" && pwd)"
export PATH="\$DIR:\$PATH"
exec "\$DIR/${REAL_BIN}_bin" "\$@"
LAUNCHER
  chmod +x "$MACOS_DIR/$REAL_BIN"
  echo "✔  Launcher wrapper written"
fi

# ── 8. Done ────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
echo "  ✅  Build complete!"
echo ""
echo "  App:  $(pwd)/dist/${APP_NAME}.app"
echo ""
echo "  To use:  double-click the .app in Finder"
echo "           or drag it to your Applications folder."
echo "══════════════════════════════════════════════"
echo ""

# Optionally open Finder at the dist folder
open dist/ 2>/dev/null || true
