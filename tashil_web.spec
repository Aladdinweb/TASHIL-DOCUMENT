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

# Same treatment for qrcode + Pillow (network-access QR code feature) —
# Pillow in particular has plugin/codec submodules that plain
# hiddenimports can miss.
qrcode_datas, qrcode_binaries, qrcode_hiddenimports = collect_all('qrcode')
pil_datas, pil_binaries, pil_hiddenimports = collect_all('PIL')

# cryptography (encryption-at-rest, v2.7.0) — it binds to OpenSSL via a
# compiled extension, so the same collect_all() treatment applies for the
# same reason as pywebview above.
crypto_datas, crypto_binaries, crypto_hiddenimports = collect_all('cryptography')

# certifi (v2.7.0) — bundles its own CA certificate list so the Cloud
# Bridge's HTTPS calls verify correctly even when a frozen Windows exe
# can't reach the OS certificate store the normal way. Just data (a
# single .pem file), no binaries, but still needs explicit collection or
# PyInstaller can miss the packaged file.
certifi_datas, certifi_binaries, certifi_hiddenimports = collect_all('certifi')

# opencv-python-headless (QR image decode, v2.7.0) — used only for the
# "load/drop a QR image" provisioning fallback. ⚠️ This is a genuinely
# heavy, complex native dependency (much larger and more failure-prone to
# package than anything else in this project so far) — collect_all() is
# essential here, not optional, but if the built exe ever fails specifically
# around QR image decoding, this is the first dependency to suspect.
cv2_datas, cv2_binaries, cv2_hiddenimports = collect_all('cv2')

a = Analysis(
    ['desktop_launcher.py'],
    pathex=[],
    binaries=webview_binaries + qrcode_binaries + pil_binaries + crypto_binaries
             + certifi_binaries + cv2_binaries,
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('app.py', '.'),
    ] + webview_datas + qrcode_datas + pil_datas + crypto_datas + certifi_datas + cv2_datas,
    hiddenimports=['flask', 'werkzeug', 'jinja2'] + webview_hiddenimports
                  + qrcode_hiddenimports + pil_hiddenimports + crypto_hiddenimports
                  + certifi_hiddenimports + cv2_hiddenimports,
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
