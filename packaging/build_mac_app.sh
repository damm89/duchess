#!/bin/bash
# Build Duchess.app for macOS
# Can be run from anywhere — resolves project root from script location.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON="$HOME/.pyenv/versions/duchess/bin/python"

echo "=== Building C++ engine (if needed) ==="
mkdir -p "$PROJECT_ROOT/engine/build"
cd "$PROJECT_ROOT/engine/build"
cmake .. -Dpybind11_DIR=$("$PYTHON" -m pybind11 --cmakedir) 2>/dev/null
make -j4
cd "$PROJECT_ROOT"

echo "=== Running PyInstaller ==="
"$PYTHON" -m PyInstaller "$SCRIPT_DIR/duchess.spec" \
    --distpath "$PROJECT_ROOT/dist" \
    --workpath "$PROJECT_ROOT/build_pyinstaller" \
    --noconfirm

echo "=== Creating DMG ==="
rm -f "$PROJECT_ROOT/dist/Duchess.dmg"
hdiutil create -volname "Duchess Chess" -srcfolder "$PROJECT_ROOT/dist/Duchess.app" \
    -ov -format UDZO "$PROJECT_ROOT/dist/Duchess.dmg"

echo ""
echo "=== Done ==="
echo "Installer: $PROJECT_ROOT/dist/Duchess.dmg"
echo ""
echo "To install: open dist/Duchess.dmg and drag Duchess to Applications"
