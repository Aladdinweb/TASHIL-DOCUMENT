# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

_icon_path = os.path.join('static', 'assets', 'icon.ico')
_icon = _icon_path if os.path.exists(_icon_path) else None

# pywebview needs its platform-specific DLLs/data collected explicitly on
# Windows (WebView2 loader etc.) — hiddenimports alone is not enough and
# was a real source of "works on my machine, fails on the built exe" bugs
# in earlier iterations of this project. collect_all() pulls in everything
# the package ships so the frozen exe has what it needs at runtime.
webview_datas, webview_binaries, webview_hiddenimports = collect_all('webview')

a = Analysis(
    ['desktop_launcher.py'],
    pathex=[],
    binaries=webview_binaries,
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('app.py', '.'),
    ] + webview_datas,
    hiddenimports=['flask', 'werkzeug', 'jinja2'] + webview_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
