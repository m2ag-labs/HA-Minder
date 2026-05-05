#!/usr/bin/env bash
# build.sh — Build HA-Minder as a macOS menu bar .app bundle
# Usage: ./build.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"

echo "==> Using Python from: $PYTHON"

# 1. Ensure py2app is installed in the venv
if ! "$PYTHON" -c "import py2app" 2>/dev/null; then
    echo "==> Installing py2app into .venv..."
    "$PIP" install py2app
fi

# 2. Clean previous build artifacts
echo "==> Cleaning build/ and dist/..."
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist"

# 3. Build the .app bundle
echo "==> Building HA-Minder.app..."
cd "$SCRIPT_DIR"
"$PYTHON" setup.py py2app

echo ""
echo "✅ Done! App bundle is at: dist/HA-Minder.app"
echo "   Open with: open dist/HA-Minder.app"
echo "   Or copy to /Applications: cp -r dist/HA-Minder.app /Applications/"
