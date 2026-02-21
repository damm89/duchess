#!/bin/bash
# Installs the Duchess desktop entry (Linux/Ubuntu only)
set -e

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DESKTOP_DIR="$HOME/.local/share/applications"

mkdir -p "$DESKTOP_DIR"

sed "s|PLACEHOLDER_PROJECT_ROOT|$PROJECT_ROOT|g" \
    "$PROJECT_ROOT/duchess.desktop" > "$DESKTOP_DIR/duchess.desktop"

chmod +x "$DESKTOP_DIR/duchess.desktop"
echo "Desktop entry installed to $DESKTOP_DIR/duchess.desktop"
