#!/bin/bash
# Build Duchess AppImage for Linux using Docker.
# Can be run from macOS or any system with Docker installed.
# Must be run from the Duchess project root directory.
set -e

if [ ! -f "duchess.spec" ]; then
    echo "Error: duchess.spec not found. Run this script from the Duchess project root."
    exit 1
fi

if ! command -v docker &>/dev/null; then
    echo "Error: Docker is not installed or not in PATH."
    exit 1
fi

echo "=== Building AppImage via Docker (this may take a few minutes) ==="
docker build --platform linux/amd64 -f Dockerfile.appimage -o dist .

echo ""
echo "=== Done ==="
echo "AppImage: $(pwd)/dist/Duchess-x86_64.AppImage"
