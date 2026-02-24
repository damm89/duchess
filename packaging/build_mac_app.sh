#!/bin/bash
# Build Duchess.app for macOS
# Must be run from the Duchess project root directory.
set -e

PROJECT_ROOT="$(pwd)"
PYTHON="$HOME/.pyenv/versions/duchess/bin/python"

if [ ! -f "$PROJECT_ROOT/duchess.spec" ]; then
    echo "Error: duchess.spec not found. Run this script from the Duchess project root."
    exit 1
fi

echo "=== Building C++ engine (if needed) ==="
mkdir -p "$PROJECT_ROOT/engine/build"
cd "$PROJECT_ROOT/engine/build"
cmake .. -Dpybind11_DIR=$("$PYTHON" -m pybind11 --cmakedir) 2>/dev/null
make -j4
cd "$PROJECT_ROOT"

echo "=== Running PyInstaller ==="
"$PYTHON" -m PyInstaller duchess.spec --distpath "$PROJECT_ROOT/dist" --workpath "$PROJECT_ROOT/build_pyinstaller" --noconfirm

echo "=== Creating DMG ==="
rm -f "$PROJECT_ROOT/dist/Duchess.dmg"
hdiutil create -volname "Duchess Chess" -srcfolder "$PROJECT_ROOT/dist/Duchess.app" \
    -ov -format UDZO "$PROJECT_ROOT/dist/Duchess.dmg"

echo ""
echo "=== Done ==="
echo "Installer: $PROJECT_ROOT/dist/Duchess.dmg"
echo ""
echo "To install: open dist/Duchess.dmg and drag Duchess to Applications"
