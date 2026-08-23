# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

_icon_path = os.path.join('app', 'assets', 'icon.ico')
_icon = _icon_path if os.path.exists(_icon_path) else None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('app/assets', 'app/assets')],
    hiddenimports=['customtkinter', 'PIL', 'qrcode'],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TASHIL_DOCUMENT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)
