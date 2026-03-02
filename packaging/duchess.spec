# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Duchess Chess — cross-platform (macOS & Linux)."""
import os
import platform

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
PROJECT_ROOT = os.path.dirname(SPEC_DIR)
ENGINE_BUILD = os.path.join(PROJECT_ROOT, "engine", "build")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")

# Find the duchess_engine shared library
from pathlib import Path
engine_so = list(Path(ENGINE_BUILD).glob("duchess_engine*.so"))
if not engine_so:
    engine_so = list(Path(ENGINE_BUILD).glob("duchess_engine*.dylib"))
if not engine_so:
    raise FileNotFoundError("duchess_engine shared library not found in engine/build/")

# Find the duchess_cli executable
engine_cli = Path(ENGINE_BUILD) / "duchess_cli"
if not engine_cli.exists():
    raise FileNotFoundError("duchess_cli executable not found in engine/build/")

a = Analysis(
    [os.path.join(PROJECT_ROOT, "duchess", "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[(str(engine_so[0]), "."), (str(engine_cli), ".")],
    datas=[(ASSETS_DIR, "assets")],
    hiddenimports=["duchess_engine", "duchess.gui", "duchess.gui.board_widget",
                   "duchess.gui.main_window", "duchess.gui.worker"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="duchess",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=os.path.join(ASSETS_DIR, "duchess_icon.icns") if platform.system() == "Darwin"
         else os.path.join(ASSETS_DIR, "duchess_icon.png"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="duchess",
)

# macOS .app bundle
if platform.system() == "Darwin":
    app = BUNDLE(
        coll,
        name="Duchess.app",
        icon=os.path.join(ASSETS_DIR, "duchess_icon.icns"),
        bundle_identifier="com.duchess.chess",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleName": "Duchess Chess",
            "NSHighResolutionCapable": True,
        },
    )
