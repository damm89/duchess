#!/bin/bash
# Build Duchess AppImage for Linux
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
cmake "$PROJECT_ROOT/engine" -Dpybind11_DIR=$("$PYTHON" -m pybind11 --cmakedir) 2>/dev/null
make -j4
cd "$PROJECT_ROOT"

echo "=== Running PyInstaller ==="
"$PYTHON" -m PyInstaller duchess.spec --distpath "$PROJECT_ROOT/dist" --workpath "$PROJECT_ROOT/build_pyinstaller" --noconfirm

echo "=== Preparing AppDir ==="
APPDIR="$PROJECT_ROOT/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"

# Copy PyInstaller output
cp -r "$PROJECT_ROOT/dist/duchess/"* "$APPDIR/usr/bin/"

# Desktop entry
sed "s|PLACEHOLDER_PROJECT_ROOT|/usr/bin|g; s|Exec=.*|Exec=duchess|; s|Icon=.*|Icon=duchess_icon|" \
    "$PROJECT_ROOT/duchess.desktop" > "$APPDIR/duchess.desktop"

# Icon
cp "$PROJECT_ROOT/assets/duchess_icon.png" "$APPDIR/duchess_icon.png"

# AppRun
cat > "$APPDIR/AppRun" << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "$HERE/usr/bin/duchess" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

echo "=== Building AppImage ==="
if ! command -v appimagetool &>/dev/null; then
    echo "Downloading appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" \
         -O /tmp/appimagetool
    chmod +x /tmp/appimagetool
    APPIMAGETOOL=/tmp/appimagetool
else
    APPIMAGETOOL=appimagetool
fi

"$APPIMAGETOOL" "$APPDIR" "$PROJECT_ROOT/dist/Duchess-x86_64.AppImage"

echo ""
echo "=== Done ==="
echo "AppImage: $PROJECT_ROOT/dist/Duchess-x86_64.AppImage"
