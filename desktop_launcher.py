# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — desktop_launcher.py
Copyright ILINE TECH 2026 BY FERAK ALADDIN

Windows entry point. Deliberately minimal: starts the Flask server on a
background thread, waits for it to be ready, then opens it in the
system's default browser. There is no custom window, no manual widget
positioning, no PyInstaller icon dependency for the UI itself — the
browser renders everything, which is exactly what makes this reliable
where the old CustomTkinter build was not.

Any failure is shown in a native Windows message box (not just logged),
so nothing can fail silently.
"""

import os
import sys
import time
import ctypes
import socket
import threading
import traceback
import webbrowser


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
            target=lambda: tashil_app.app.run(host="127.0.0.1", port=5000, debug=False,
                                               use_reloader=False),
            daemon=True,
        )
        server_thread.start()

        # Wait for the server to actually be listening before opening the browser
        for _ in range(40):  # up to ~10s
            if _port_is_open(5000):
                break
            time.sleep(0.25)

        webbrowser.open("http://127.0.0.1:5000/")

        # Keep the process alive as long as the server thread is running
        while server_thread.is_alive():
            time.sleep(1)

    except Exception as exc:  # noqa: BLE001 — deliberately broad: this is the top-level guard
        _show_fatal_error(exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
