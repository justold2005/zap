# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files


# =========================================================
# RUTA DE VLC
# =========================================================

VLC_PATH = r"C:\Program Files\VideoLAN\VLC"


# =========================================================
# ARCHIVOS DE VLC
# =========================================================

binaries = []

binaries += [
    (
        os.path.join(VLC_PATH, "libvlc.dll"),
        "."
    ),
    (
        os.path.join(VLC_PATH, "libvlccore.dll"),
        "."
    ),
]


# =========================================================
# PLUGINS DE VLC
# =========================================================

datas = [
    (
        os.path.join(VLC_PATH, "plugins"),
        "plugins"
    )
]


# =========================================================
# PYINSTALLER
# =========================================================

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=["vlc"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)


pyz = PYZ(
    a.pure
)


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Zap",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)