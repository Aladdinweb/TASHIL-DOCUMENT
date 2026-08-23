# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — updater.py
Background OTA updater using the GitHub Releases API.
Always downloads to %TEMP% — never Desktop (fixes Errno 13 permission issues).
"""

import os
import sys
import subprocess
import tempfile
import threading
import urllib.request
import json

from app.config import GITHUB_API_RELEASES, EXECUTABLE_NAME
from app.utils.version import get_version


def _version_tuple(v: str):
    v = v.lstrip("v")
    return tuple(int(p) for p in v.split(".") if p.isdigit())


def check_for_update(timeout: int = 6) -> dict | None:
    """
    Returns a dict {version, download_url, notes} if a newer release exists,
    otherwise None. Never raises — network failures are swallowed so the
    app always boots even offline.
    """
    try:
        req = urllib.request.Request(
            GITHUB_API_RELEASES,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "TASHIL-DOCUMENT-HUB-Updater"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        latest_tag = data.get("tag_name", "0.0.0")
        if _version_tuple(latest_tag) <= _version_tuple(get_version()):
            return None

        asset_url = None
        for asset in data.get("assets", []):
            if asset.get("name", "").endswith(".exe"):
                asset_url = asset.get("browser_download_url")
                break

        if not asset_url:
            return None

        return {
            "version": latest_tag,
            "download_url": asset_url,
            "notes": data.get("body", ""),
        }
    except Exception:
        return None


def download_update(download_url: str, on_progress=None) -> str:
    """
    Downloads the new .exe into %TEMP% and returns the local path.
    on_progress(percent:int) is called periodically if provided.
    """
    temp_dir = tempfile.gettempdir()
    dest_path = os.path.join(temp_dir, f"TASHIL_UPDATE_{EXECUTABLE_NAME}")

    def _report(block_num, block_size, total_size):
        if on_progress and total_size > 0:
            percent = min(100, int(block_num * block_size * 100 / total_size))
            on_progress(percent)

    urllib.request.urlretrieve(download_url, dest_path, reporthook=_report)
    return dest_path


def launch_updater_and_exit(new_exe_path: str):
    """
    Spawns the freshly downloaded exe (which replaces the running one on
    next launch via a small self-replace routine) and exits the current process.
    """
    current_exe = sys.executable if getattr(sys, "frozen", False) else EXECUTABLE_NAME
    updater_script = os.path.join(tempfile.gettempdir(), "tashil_swap.bat")

    with open(updater_script, "w", encoding="utf-8") as f:
        f.write(f"""@echo off
timeout /t 2 /nobreak > NUL
copy /Y "{new_exe_path}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
""")

    subprocess.Popen(["cmd", "/c", updater_script], shell=False,
                      creationflags=subprocess.CREATE_NO_WINDOW)
    sys.exit(0)


def check_for_update_async(callback):
    """Runs check_for_update() on a background thread; callback(result_or_None)."""
    def _worker():
        result = check_for_update()
        callback(result)
    threading.Thread(target=_worker, daemon=True).start()
