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

# pyzbar (QR image decode, v2.7.0) — used only for the "load/drop a QR
# image" provisioning fallback. Replaces an earlier attempt using
# opencv-python-headless, which imported cleanly in every local test here
# but FAILED to import in the actual built exe with no visible reason —
# confirmed by the user in production. pyzbar is a much smaller, simpler
# native dependency (wraps the zbar C library, ships its DLLs directly in
# the Windows wheel) — lower packaging risk, and reuses Pillow, which is
# already proven working in this exact build (provisioning QR generation
# already depends on it successfully). collect_all() still applies since
# it wraps a compiled shared library, same reasoning as pywebview above.
# ⚠️ If QR image decoding fails again after this change, the in-app error
# message now surfaces the real import failure reason (see
# _QR_DECODE_IMPORT_ERROR in app.py) instead of a dead-end "not available".
pyzbar_datas, pyzbar_binaries, pyzbar_hiddenimports = collect_all('pyzbar')

a = Analysis(
    ['desktop_launcher.py'],
    pathex=[],
    binaries=webview_binaries + qrcode_binaries + pil_binaries + crypto_binaries
             + certifi_binaries + pyzbar_binaries,
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('app.py', '.'),
    ] + webview_datas + qrcode_datas + pil_datas + crypto_datas + certifi_datas + pyzbar_datas,
    hiddenimports=['flask', 'werkzeug', 'jinja2'] + webview_hiddenimports
                  + qrcode_hiddenimports + pil_hiddenimports + crypto_hiddenimports
                  + certifi_hiddenimports + pyzbar_hiddenimports,
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
