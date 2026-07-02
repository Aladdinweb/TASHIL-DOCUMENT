# COPYRIGHT ILINE TECH 2026 BY FERAK ALADDIN
"""
Updater TASHIL — Fix [Errno 13] Permission denied
Télécharge dans %TEMP% au lieu du dossier exe.
"""
import sys
import os
import threading
import urllib.request
import json
import subprocess
import datetime

GITHUB_OWNER = "Aladdinweb"
GITHUB_REPO  = "TASHIL-ES"
GITHUB_API   = (
    f"https://api.github.com/repos/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}"
    f"/releases/latest"
)


def obtenir_derniere_version() -> dict | None:
    try:
        req = urllib.request.Request(
            GITHUB_API,
            headers={
                "User-Agent": "TASHIL-Updater/1.0",
                "Accept": "application/vnd.github+json",
            })
        with urllib.request.urlopen(
                req, timeout=12) as resp:
            data = json.loads(
                resp.read().decode("utf-8"))

        tag    = data.get("tag_name", "")
        assets = data.get("assets", [])
        url_exe, taille = None, 0

        for asset in assets:
            if asset.get("name", "").endswith(
                    ".exe"):
                url_exe = asset[
                    "browser_download_url"]
                taille  = asset.get("size", 0)
                break

        return {
            "tag":     tag,
            "url_exe": url_exe,
            "taille":  taille,
            "notes":   data.get("body", "")[:400],
        }
    except Exception as ex:
        print(f"[Updater] API error: {ex}")
        return None


def version_plus_recente(tag_distant: str) -> bool:
    try:
        from app.utils.version import get_version

        def _p(v: str) -> tuple:
            return tuple(
                int(x) for x in
                v.lstrip("v").split(".")
                if x.isdigit())

        return _p(tag_distant) > _p(get_version())
    except Exception:
        return False


def verifier_en_arriere_plan(callback):
    def _worker():
        info = obtenir_derniere_version()
        callback(info)
    threading.Thread(
        target=_worker, daemon=True).start()


def telecharger_et_remplacer(
        url_exe: str,
        callback_progres=None,
        callback_fin=None):

    def _worker():
        tmp_path = None
        bat_path = None
        try:
            # ── Chemin exe actuel ─────────────
            if getattr(sys, 'frozen', False):
                exe_actuel = sys.executable
            else:
                exe_actuel = os.path.abspath(
                    "EPSP_CongeManager.exe")

            exe_actuel   = os.path.abspath(exe_actuel)
            dossier_exe  = os.path.dirname(exe_actuel)

            # ── FIX [Errno 13] ────────────────
            # Toujours télécharger dans %TEMP%
            # jamais dans le dossier de l'exe
            # (Desktop = permission denied)
            temp_dir = (
                os.environ.get("TEMP")
                or os.environ.get("TMP")
                or os.path.expanduser("~"))

            today = datetime.datetime.now().strftime(
                "%Y%m%d_%H%M%S")

            tmp_path = os.path.join(
                temp_dir,
                f"tashil_update_{today}.exe")
            bat_path = os.path.join(
                temp_dir,
                f"tashil_update_{today}.bat")
            bak_path = os.path.join(
                dossier_exe,
                f"_bak_{today}.exe")

            # ── Téléchargement dans TEMP ──────
            def _hook(count, block, total):
                if callback_progres and total > 0:
                    pct = min(
                        100,
                        int(count * block * 100
                            / total))
                    callback_progres(pct)

            urllib.request.urlretrieve(
                url_exe, tmp_path, _hook)

            if callback_progres:
                callback_progres(100)

            # Vérifier intégrité
            if not os.path.exists(tmp_path):
                raise FileNotFoundError(
                    "Fichier téléchargé introuvable.")

            taille = os.path.getsize(tmp_path)
            if taille < 100 * 1024:
                raise ValueError(
                    f"Fichier corrompu "
                    f"({taille} octets).")

            if sys.platform != "win32":
                if callback_fin:
                    callback_fin(
                        False,
                        "MAJ auto Windows uniquement.")
                return

            # ── Script .bat robuste ───────────
            bat = (
                "@echo off\r\n"
                "chcp 65001 > nul\r\n"
                "title TASHIL - Mise a jour\r\n"
                "echo ========================\r\n"
                "echo  TASHIL - Installation\r\n"
                "echo ========================\r\n"
                "echo.\r\n"
                "echo Attente fermeture TASHIL...\r\n"
                "timeout /t 3 /nobreak > nul\r\n"
                "\r\n"
                ":WAIT\r\n"
                "tasklist /fi \"IMAGENAME eq "
                "EPSP_CongeManager.exe\" 2>nul"
                " | find /i \"EPSP_CongeManager"
                ".exe\" > nul\r\n"
                "if %errorlevel% == 0 (\r\n"
                "    timeout /t 1 /nobreak > nul\r\n"
                "    goto WAIT\r\n"
                ")\r\n"
                "\r\n"
                "echo Installation...\r\n"
                f"if exist \"{exe_actuel}\" (\r\n"
                f"    move /Y \"{exe_actuel}\""
                f" \"{bak_path}\" > nul 2>&1\r\n"
                ")\r\n"
                "\r\n"
                f"move /Y \"{tmp_path}\""
                f" \"{exe_actuel}\" > nul 2>&1\r\n"
                "if %errorlevel% neq 0 (\r\n"
                "    echo ERREUR installation!\r\n"
                f"    if exist \"{bak_path}\" (\r\n"
                f"        move /Y \"{bak_path}\""
                f" \"{exe_actuel}\" > nul 2>&1\r\n"
                "    )\r\n"
                "    pause\r\n"
                "    goto END\r\n"
                ")\r\n"
                "\r\n"
                "echo Reussi! Redemarrage...\r\n"
                "timeout /t 2 /nobreak > nul\r\n"
                f"start \"\" \"{exe_actuel}\"\r\n"
                "\r\n"
                ":END\r\n"
                "del /f /q \"%~f0\" > nul 2>&1\r\n"
            )

            with open(bat_path, "w",
                      encoding="cp1252",
                      errors="replace") as f:
                f.write(bat)

            subprocess.Popen(
                ["cmd.exe", "/c", bat_path],
                creationflags=(
                    subprocess.CREATE_NEW_CONSOLE),
                close_fds=True)

            if callback_fin:
                callback_fin(True, "")

        except Exception as ex:
            if tmp_path and os.path.exists(
                    tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            print(f"[Updater] Error: {ex}")
            if callback_fin:
                callback_fin(False, str(ex))

    threading.Thread(
        target=_worker, daemon=True).start()
