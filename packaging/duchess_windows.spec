# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['duchess/main.py'],
    pathex=[],
    binaries=[
        ('engine/build/Release/duchess_cli.exe', '.'),
    ],
    datas=[
        ('data/gm2001.bin', 'data'),
        ('assets/duchess_icon.png', 'assets'),
    ],
    hiddenimports=['sqlalchemy.ext.baked', 'psycopg2', 'psycopg2-binary'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Duchess',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/duchess_icon.png'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Duchess',
)
