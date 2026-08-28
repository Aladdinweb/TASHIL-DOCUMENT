# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — desktop_launcher.py
Copyright ILINE TECH 2026 BY FERAK ALADDIN

Windows entry point. Starts the Flask server on a background thread,
waits for it to be ready, then shows it in a native desktop window via
pywebview (its own title bar and icon, no external Chrome/Edge tab).

⚠️ Reliability note: pywebview on Windows depends on the Microsoft Edge
WebView2 runtime and its own bundled DLLs — this is a real dependency
that the old browser-tab approach didn't have. If pywebview fails to
import or the native window fails to start for any reason (WebView2
missing, DLL not bundled correctly, etc.), this launcher automatically
falls back to opening the default browser — the same approach already
confirmed working — so a WebView2 problem can never again produce a
silent blank or frozen window like the old CustomTkinter build did.
"""

import os
import sys
import time
import ctypes
import socket
import threading
import traceback
import webbrowser


APP_URL = "http://127.0.0.1:5000/"


def _dump_path() -> str:
    base_dir = os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                                else os.path.abspath(__file__))
    return os.path.join(base_dir, "tashil_boot_error.txt")


def _show_fatal_error(exc: Exception):
    tb = traceback.format_exc()
    path = _dump_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("TASHIL DOCUMENT HUB — Crash Dump\n" + "=" * 50 + "\n" + tb)
    except Exception:
        pass
    message = f"TASHIL n'a pas pu démarrer.\n\n{exc}\n\nDétails : {path}\n\n{tb[-1000:]}"
    try:
        ctypes.windll.user32.MessageBoxW(0, message, "TASHIL DOCUMENT HUB — Erreur", 0x10)
    except Exception:
        print(message, file=sys.stderr)


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_server(port: int, attempts: int = 40, interval: float = 0.25) -> bool:
    for _ in range(attempts):  # up to ~10s
        if _port_is_open(port):
            return True
        time.sleep(interval)
    return False


def _try_native_window(icon_path: str | None) -> bool:
    """
    Attempts to show the app in a native pywebview window. Returns True if
    the window ran and closed normally, False if it could not start at all
    (caller should fall back to the browser in that case).
    """
    try:
        import webview
    except Exception:
        return False  # pywebview not available in this build — fall back silently

    try:
        window_kwargs = dict(
            title="TASHIL DOCUMENT HUB",
            url=APP_URL,
            width=1180,
            height=720,
            min_size=(980, 620),
            text_select=True,
        )
        webview.create_window(**window_kwargs)
        webview.start(icon=icon_path) if icon_path else webview.start()
        return True
    except Exception:
        # WebView2 runtime missing, DLL bundling issue, etc. — don't crash,
        # let main() fall back to the browser instead.
        return False


def main():
    try:
        # When frozen by PyInstaller, app.py and its templates/static folders
        # are bundled alongside this launcher — make sure imports resolve.
        base_dir = os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                                    else os.path.abspath(__file__))
        sys.path.insert(0, base_dir)
        os.chdir(base_dir)

        import app as tashil_app  # the Flask app defined in app.py

        server_thread = threading.Thread(
            target=lambda: tashil_app.app.run(host="0.0.0.0", port=5000, debug=False,
                                               use_reloader=False),
            daemon=True,
        )
        server_thread.start()

        if not _wait_for_server(5000):
            raise RuntimeError("Le serveur local TASHIL n'a pas démarré à temps.")

        icon_path = os.path.join(base_dir, "static", "assets", "icon.ico")
        icon_path = icon_path if os.path.exists(icon_path) else None

        opened_native = _try_native_window(icon_path)

        if not opened_native:
            # Fallback: proven-reliable browser-tab approach.
            webbrowser.open(APP_URL)
            while server_thread.is_alive():
                time.sleep(1)

    except Exception as exc:  # noqa: BLE001 — deliberately broad: this is the top-level guard
        _show_fatal_error(exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
