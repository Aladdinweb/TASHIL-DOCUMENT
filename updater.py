# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — Zero-Touch Auto-Updater (v2.10.0, flux simplifié)
Copyright ILINE TECH 2026 BY FERAK ALADDIN

FLUX (v2.10.0) — DÉTECTION puis ACTION UTILISATEUR :
  * Au démarrage (thread daemon, puis toutes les 6 h) et sur clic de
    « Vérifier les mises à jour » : l'app DÉTECTE seulement. Rien n'est
    téléchargé ni appliqué ; l'état passe à "available" (kind = "app" ou
    "front") et l'interface affiche une bannière.
  * Un clic sur « Mettre à jour maintenant » (POST /api/update/apply) lance
    l'application réelle : patch d'interface en direct, ou .exe + updater.bat.

Deux mécanismes d'application :

  1. LIVE FRONT PATCHING — si la release contient tashil_front.zip (static/ +
     templates/) et que son tag est plus récent : téléchargement, extraction
     stricte, puis activation SANS redémarrer. Les fichiers vivent dans
     ~/TASHIL_DATA/front_override/ (persistant) que Flask sert en priorité :
     le static/ + templates/ d'un .exe PyInstaller --onefile est un dossier
     TEMPORAIRE recréé à chaque lancement, y écrire serait perdu à la fermeture.
  2. AUTO-REPLACE BINARY — si la release contient TASHIL_DOCUMENT.exe et que
     son tag est plus récent : téléchargement sous update_temp.exe (dans le
     dossier d'installation, ex. Documents\\TASHIL\\), puis updater.bat remplace
     l'exécutable après la fermeture de l'application et la relance.

⚠️ DÉPÔT : l'app interroge l'API GitHub SANS authentification (aucun jeton
n'est embarqué dans l'exécutable — il serait extractible de chaque copie).
Le dépôt indiqué par GITHUB_REPO (app.py) doit donc être PUBLIC (par exemple
un dépôt dédié aux seuls binaires de release). Sur un dépôt privé, GitHub
répond 404 et aucune mise à jour n'est jamais trouvée.

Contrôles conservés (sans signature) : HTTPS uniquement, hôtes GitHub
uniquement (redirections comprises), tailles plafonnées, certificats certifi,
aucune rétrogradation, .exe contrôlé (en-tête « MZ », taille minimale),
extraction du zip en liste blanche (static/ + templates/, extensions
autorisées, pas de ../, pas de chemin absolu, pas de lien symbolique —
jamais de .py ni .exe). L'intégrité repose sur le contrôle d'accès du dépôt
de release (compte protégé par 2FA).
"""

import os
import re
import sys
import json
import time
import ssl
import shutil
import zipfile
import threading
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from urllib.parse import urlparse

try:
    import certifi
    _CERTIFI = True
except ImportError:
    _CERTIFI = False

EXE_ASSET_NAME = "TASHIL_DOCUMENT.exe"
FRONT_ASSET_NAME = "tashil_front.zip"
TEMP_EXE_NAME = "update_temp.exe"
BAT_NAME = "updater.bat"

MAX_FRONT_ZIP_BYTES = 30 * 1024 * 1024
MAX_FRONT_UNPACKED_BYTES = 120 * 1024 * 1024
MAX_FRONT_FILES = 600
MAX_EXE_BYTES = 300 * 1024 * 1024
MIN_EXE_BYTES = 3 * 1024 * 1024

_ALLOWED_TOP = ("static", "templates")
_ALLOWED_EXT = {".js", ".css", ".html", ".json", ".txt", ".map", ".svg", ".png", ".jpg",
                ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".ttf", ".md", ".apk"}
_ALLOWED_HOSTS = ("github.com", "api.github.com", "githubusercontent.com")

FRONT_POINTER = "front_current.json"

_cfg = {}
_state = {"state": "idle", "message": "", "current": "", "latest": "", "kind": "", "last_check": None}
_state_lock = threading.Lock()
_run_lock = threading.Lock()
_auto_started = False


# --------------------------------------------------------------------------- #
# Versions
# --------------------------------------------------------------------------- #
def parse_version(text) -> tuple:
    nums = re.findall(r"\d+", str(text or ""))[:3]
    nums = [int(n) for n in nums] + [0] * (3 - len(nums))
    return tuple(nums)


def fmt_version(t: tuple) -> str:
    return ".".join(str(n) for n in t)


# --------------------------------------------------------------------------- #
# Front override directory (called BEFORE Flask() is created — standalone)
# --------------------------------------------------------------------------- #
def _front_root(base_dir):
    return os.path.join(base_dir, "front_override")


def _read_pointer(base_dir):
    try:
        with open(os.path.join(_front_root(base_dir), FRONT_POINTER), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def resolve_front_dirs(base_dir, app_version, bundled_static, bundled_templates):
    """
    Returns (static_dir, templates_dir) that Flask must use at startup.
    The override is used only if it is intact AND built on top of THIS exact
    app version AND still newer than it: a newer .exe ships its own bundled
    front, and an override built on an older base would silently miss new
    bundled assets — it is then discarded and the next check re-applies
    whatever front patch is still newer than the exe.
    Never raises: any problem falls back to the bundled folders.
    """
    try:
        ptr = _read_pointer(base_dir)
        if ptr:
            d = os.path.join(_front_root(base_dir), ptr.get("dir", ""))
            ok = (ptr.get("base_app_version") == fmt_version(parse_version(app_version))
                  and parse_version(ptr.get("front_version")) > parse_version(app_version)
                  and os.path.isfile(os.path.join(d, "templates", "index.html"))
                  and os.path.isfile(os.path.join(d, "static", "js", "app.js")))
            if ok:
                return os.path.join(d, "static"), os.path.join(d, "templates")
            _purge_front_root(base_dir)
    except Exception:
        pass
    return bundled_static, bundled_templates


def _purge_front_root(base_dir, keep=None):
    root = _front_root(base_dir)
    if not os.path.isdir(root):
        return
    for name in os.listdir(root):
        if name == FRONT_POINTER or name == keep:
            continue
        shutil.rmtree(os.path.join(root, name), ignore_errors=True)
    if keep is None:
        try:
            os.remove(os.path.join(root, FRONT_POINTER))
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# State / config
# --------------------------------------------------------------------------- #
def configure(*, repo, app_version, base_dir, bundled_static, bundled_templates,
              on_front_applied=None, before_exit=None):
    _cfg.update(repo=repo, app_version=app_version, base_dir=base_dir,
                bundled_static=bundled_static, bundled_templates=bundled_templates,
                on_front_applied=on_front_applied, before_exit=before_exit)
    _set_state("idle", "", current=fmt_version(parse_version(app_version)))


def _set_state(state, message="", **extra):
    with _state_lock:
        _state.update(state=state, message=message, **extra)


def get_status() -> dict:
    with _state_lock:
        return dict(_state)


# --------------------------------------------------------------------------- #
# Network (https + GitHub hosts only, certifi, size caps)
# --------------------------------------------------------------------------- #
def _host_ok(url: str) -> bool:
    p = urlparse(url)
    if p.scheme != "https" or not p.hostname:
        return False
    h = p.hostname.lower()
    return any(h == a or h.endswith("." + a) for a in _ALLOWED_HOSTS)


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _host_ok(newurl):
            raise urllib.error.URLError(f"redirection refusée vers {newurl!r}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener():
    ctx = ssl.create_default_context(cafile=certifi.where()) if _CERTIFI else ssl.create_default_context()
    return urllib.request.build_opener(_SafeRedirect(), urllib.request.HTTPSHandler(context=ctx))


_HEADERS = {"User-Agent": "TASHIL-DOCUMENT-HUB-Updater/1.0", "Accept": "application/vnd.github+json"}


def _http_json(url: str):
    if not _host_ok(url):
        raise ValueError("URL non autorisée")
    req = urllib.request.Request(url, headers=_HEADERS)
    with _opener().open(req, timeout=20) as resp:
        return json.loads(resp.read(2 * 1024 * 1024).decode("utf-8"))


def _download(url: str, dest: str, max_bytes: int):
    """Streams to dest, enforcing max_bytes. Deletes dest on any failure."""
    if not _host_ok(url):
        raise ValueError("URL de téléchargement non autorisée")
    req = urllib.request.Request(url, headers={**_HEADERS, "Accept": "application/octet-stream"})
    total = 0
    try:
        with _opener().open(req, timeout=60) as resp, open(dest, "wb") as out:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("fichier trop volumineux")
                out.write(chunk)
    except Exception:
        _silent_remove(dest)
        raise


def _silent_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Downloaded-file sanity checks (no signature: structural validation only)
# --------------------------------------------------------------------------- #
def validate_exe(path: str):
    size = os.path.getsize(path)
    if size < MIN_EXE_BYTES:
        raise ValueError(f"exécutable anormalement petit ({size} octets)")
    with open(path, "rb") as f:
        if f.read(2) != b"MZ":
            raise ValueError("le fichier téléchargé n'est pas un exécutable Windows")


def validate_zip(path: str):
    if not zipfile.is_zipfile(path):
        raise ValueError("archive tashil_front.zip invalide")


# --------------------------------------------------------------------------- #
# Front zip: strict extraction + atomic activation
# --------------------------------------------------------------------------- #
def _safe_extract(zip_path: str, dest: str) -> dict:
    """Extracts ONLY allow-listed paths into dest. Returns the optional
    front_manifest.json content ({} if absent). Raises ValueError on anything
    suspicious — the whole patch is then rejected, nothing is half-applied."""
    manifest = {}
    root = os.path.realpath(dest)
    total, count = 0, 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
                raise ValueError(f"chemin absolu refusé : {name}")
            parts = name.split("/")
            if any(p in ("", ".", "..") for p in parts):
                raise ValueError(f"chemin refusé : {name}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"lien symbolique refusé : {name}")

            if name == "front_manifest.json":
                manifest = json.loads(zf.read(info).decode("utf-8"))
                continue
            if parts[0] not in _ALLOWED_TOP:
                raise ValueError(f"fichier hors static/ ou templates/ : {name}")
            if os.path.splitext(name)[1].lower() not in _ALLOWED_EXT:
                raise ValueError(f"extension non autorisée : {name}")

            count += 1
            total += info.file_size
            if count > MAX_FRONT_FILES or total > MAX_FRONT_UNPACKED_BYTES:
                raise ValueError("archive trop volumineuse")

            target = os.path.realpath(os.path.join(root, *parts))
            if not target.startswith(root + os.sep):
                raise ValueError(f"évasion de dossier refusée : {name}")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
    return manifest


def read_front_manifest(zip_path: str) -> dict:
    with zipfile.ZipFile(zip_path) as zf:
        if "front_manifest.json" in zf.namelist():
            return json.loads(zf.read("front_manifest.json").decode("utf-8"))
    return {}


def apply_front_zip(zip_path: str, front_version: tuple) -> tuple:
    """Builds a COMPLETE front tree (bundled files + zip overlay) in a new
    uniquely-named folder, then flips the pointer atomically. Returns
    (static_dir, templates_dir). The previous override is removed only AFTER
    the switch, so a failure at any step leaves the running front (and the
    previous override, if any) untouched."""
    base = _cfg["base_dir"]
    root = _front_root(base)
    os.makedirs(root, exist_ok=True)
    name = f"front_{fmt_version(front_version)}_{int(time.time())}"
    new_dir = os.path.join(root, name)
    try:
        shutil.copytree(_cfg["bundled_static"], os.path.join(new_dir, "static"))
        shutil.copytree(_cfg["bundled_templates"], os.path.join(new_dir, "templates"))
        _safe_extract(zip_path, new_dir)
        if not (os.path.isfile(os.path.join(new_dir, "templates", "index.html"))
                and os.path.isfile(os.path.join(new_dir, "static", "js", "app.js"))):
            raise ValueError("patch incomplet (index.html / app.js introuvables)")
    except Exception:
        shutil.rmtree(new_dir, ignore_errors=True)
        raise

    ptr_path = os.path.join(root, FRONT_POINTER)
    tmp_ptr = ptr_path + ".tmp"
    with open(tmp_ptr, "w", encoding="utf-8") as f:
        json.dump({"dir": name, "front_version": fmt_version(front_version),
                   "base_app_version": fmt_version(parse_version(_cfg["app_version"])),
                   "applied_at": datetime.now().isoformat()}, f)
    os.replace(tmp_ptr, ptr_path)

    static_dir, templates_dir = os.path.join(new_dir, "static"), os.path.join(new_dir, "templates")
    cb = _cfg.get("on_front_applied")
    if cb:
        try:
            cb(static_dir, templates_dir)
        except Exception:
            pass
    _purge_front_root(base, keep=name)
    return static_dir, templates_dir


def current_front_version() -> tuple:
    ptr = _read_pointer(_cfg["base_dir"])
    cur = parse_version(_cfg["app_version"])
    if ptr and ptr.get("base_app_version") == fmt_version(cur):
        return max(cur, parse_version(ptr.get("front_version")))
    return cur


# --------------------------------------------------------------------------- #
# Binary replacement
# --------------------------------------------------------------------------- #
def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_dir_problem(exe_dir: str):
    """Returns a human-readable reason the install folder can't be used for a
    self-update, or None if it's fine (e.g. %USERPROFILE%\\Documents\\TASHIL).
    The folder is taken from the RUNNING exe — never hard-coded — so a
    localized or OneDrive-redirected "Documents" works unchanged."""
    if exe_dir.startswith("\\\\"):
        return ("L'application est lancée depuis un dossier réseau (UNC) : cmd.exe ne sait pas "
                "y exécuter updater.bat. Copiez TASHIL dans Documents\\TASHIL sur ce poste.")
    probe = os.path.join(exe_dir, ".tashil_write_test")
    try:
        with open(probe, "w") as f:
            f.write("x")
        os.remove(probe)
    except OSError as exc:
        return (f"Écriture impossible dans {exe_dir} ({exc.__class__.__name__}). Vérifiez les droits du "
                f"dossier ou la « Protection contre les ransomwares / accès contrôlé aux dossiers » "
                f"de Windows Defender, qui peut bloquer l'écriture dans Documents.")
    return None


def build_updater_bat(target_basename: str) -> str:
    # Only plain file names are used (the batch runs with cwd = the .exe
    # folder): cmd.exe reads .bat files in the OEM code page, so a Windows
    # user folder with accented characters would otherwise corrupt a path.
    # `ping` is the delay (not `timeout`, which fails with redirected stdin
    # when started without a console). The 45-try loop covers the PyInstaller
    # one-file bootloader, which exits a moment AFTER the app process and keeps
    # the .exe locked until then (also OneDrive/antivirus holding the file).
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        f'set "NEW={TEMP_EXE_NAME}"\r\n'
        f'set "TARGET={target_basename}"\r\n'
        'set "N=0"\r\n'
        'copy /y "%TARGET%" "%TARGET%.old" >nul 2>&1\r\n'
        ":retry\r\n"
        "ping -n 2 127.0.0.1 >nul\r\n"
        'move /y "%NEW%" "%TARGET%" >nul 2>&1\r\n'
        "if not errorlevel 1 goto done\r\n"
        "set /a N+=1\r\n"
        "if %N% geq 45 goto fail\r\n"
        "goto retry\r\n"
        ":done\r\n"
        'start "" "%TARGET%"\r\n'
        '(goto) 2>nul & del "%~f0"\r\n'
        ":fail\r\n"
        'del "%NEW%" >nul 2>&1\r\n'
        '(goto) 2>nul & del "%~f0"\r\n'
    )


def _launch_bootstrapper_and_exit(exe_path: str):
    exe_dir, exe_name = os.path.split(exe_path)
    bat_path = os.path.join(exe_dir, BAT_NAME)
    with open(bat_path, "w", encoding="ascii", newline="") as f:
        f.write(build_updater_bat(exe_name))

    # PyInstaller one-file: a child started from inside the app inherits
    # variables that make the NEW exe reuse the OLD (about to be replaced)
    # extraction folder -> crash at relaunch. Strip them / ask for a reset.
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI") and k != "_MEIPASS2"}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
    subprocess.Popen(["cmd.exe", "/c", BAT_NAME], cwd=exe_dir, env=env, creationflags=flags,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True)
    _set_state("restarting", "Mise à jour installée — redémarrage...")
    cb = _cfg.get("before_exit")
    if cb:
        try:
            cb()
        except Exception:
            pass
    time.sleep(0.8)  # let the UI status poll pick up "restarting"
    # sys.exit(0) would only end THIS (worker) thread: the Flask server, the
    # pywebview window and the tray run in other threads and would keep the
    # .exe locked. os._exit(0) ends the whole process at once; SQLite (WAL)
    # is crash-safe and every write in this app is a short transaction.
    os._exit(0)


def cleanup_leftovers():
    """Removes debris of an interrupted earlier update (never the .old backup)."""
    if not is_frozen():
        return
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    for name in (TEMP_EXE_NAME, BAT_NAME):
        _silent_remove(os.path.join(exe_dir, name))


# --------------------------------------------------------------------------- #
# Detection (no side effect) and application (on user click)
# --------------------------------------------------------------------------- #
def _find_asset(release: dict, name: str):
    for a in release.get("assets", []):
        if a.get("name") == name:
            return a
    return None


def _fetch_release(manual: bool):
    """Returns the latest release dict, or None after setting an error state."""
    try:
        return _http_json(f"https://api.github.com/repos/{_cfg['repo']}/releases/latest")
    except urllib.error.HTTPError as exc:
        hint = (" (dépôt privé ou introuvable : le dépôt de release doit être public)"
                if exc.code == 404 else "")
        _set_state("error", f"GitHub a répondu {exc.code}{hint}" if manual else "",
                   last_check=datetime.now().isoformat())
    except Exception as exc:
        _set_state("error", f"GitHub injoignable : {exc}" if manual else "",
                   last_check=datetime.now().isoformat())
    return None


def _decide(release: dict) -> dict:
    """What would an update do? {"kind": "app"|"front"|None, "version", "problem"}.
    The new .exe wins when it can be installed (it contains the front too);
    otherwise a newer front patch; otherwise nothing."""
    current = parse_version(_cfg["app_version"])
    remote = parse_version(release.get("tag_name"))
    plan = {"kind": None, "version": fmt_version(remote), "problem": None}

    if remote > current and _find_asset(release, EXE_ASSET_NAME) and is_frozen():
        problem = install_dir_problem(os.path.dirname(os.path.abspath(sys.executable)))
        if not problem:
            plan["kind"] = "app"
            return plan
        plan["problem"] = problem            # may still fall back to a front patch below

    if remote > current_front_version() and _find_asset(release, FRONT_ASSET_NAME):
        plan["kind"] = "front"
    return plan


def run_check(manual: bool = False, quiet: bool = False) -> dict:
    """DETECTS only. Never raises. quiet=True (background re-check) leaves a
    currently displayed "available" banner untouched until the answer is known."""
    if not _run_lock.acquire(blocking=False):
        return get_status()
    try:
        current = fmt_version(parse_version(_cfg["app_version"]))
        if not quiet:
            _set_state("checking", "Recherche en cours...", current=current)
        release = _fetch_release(manual)
        if release is None:
            return get_status()
        plan = _decide(release)
        now = datetime.now().isoformat()
        if plan["kind"] == "app":
            _set_state("available", f"Nouvelle version v{plan['version']} disponible.",
                       current=current, latest=plan["version"], kind="app", last_check=now)
        elif plan["kind"] == "front":
            _set_state("available", f"Amélioration de l'interface v{plan['version']} disponible.",
                       current=current, latest=plan["version"], kind="front", last_check=now)
        elif plan["problem"]:
            _set_state("error", plan["problem"] if manual else "", current=current,
                       latest=plan["version"], kind="", last_check=now)
        else:
            _set_state("up_to_date", f"TASHIL est à jour (v{current}).", current=current,
                       latest=plan["version"], kind="", last_check=now)
        return get_status()
    except Exception as exc:  # an updater bug must never hurt the app
        _set_state("error", f"Vérification impossible : {exc}" if manual else "",
                   last_check=datetime.now().isoformat())
        return get_status()
    finally:
        _run_lock.release()


def run_apply() -> dict:
    """APPLIES the update (called only after the user clicked the button).
    Re-fetches the release first so it never applies something stale."""
    if not _run_lock.acquire(blocking=False):
        return get_status()
    try:
        return _apply_locked()
    except Exception as exc:
        _set_state("error", f"Mise à jour impossible : {exc}", last_check=datetime.now().isoformat())
        return get_status()
    finally:
        _run_lock.release()


def _apply_locked() -> dict:
    current = parse_version(_cfg["app_version"])
    release = _fetch_release(manual=True)
    if release is None:
        return get_status()
    plan = _decide(release)
    version_str, base = plan["version"], _cfg["base_dir"]

    if plan["kind"] == "app":
        exe_asset = _find_asset(release, EXE_ASSET_NAME)
        exe_path = os.path.abspath(sys.executable)
        tmp_exe = os.path.join(os.path.dirname(exe_path), TEMP_EXE_NAME)
        try:
            _set_state("downloading", f"Téléchargement de la v{version_str}...", kind="app")
            _download(exe_asset["browser_download_url"], tmp_exe, MAX_EXE_BYTES)
            validate_exe(tmp_exe)
            _launch_bootstrapper_and_exit(exe_path)   # does not return
        except Exception as exc:
            _silent_remove(tmp_exe)
            _set_state("error", f"Mise à jour de l'application refusée : {exc}",
                       last_check=datetime.now().isoformat())
        return get_status()

    if plan["kind"] == "front":
        front_asset = _find_asset(release, FRONT_ASSET_NAME)
        tmp_zip = os.path.join(base, f"front_download_{os.getpid()}.zip")
        try:
            _set_state("downloading", "Téléchargement du correctif d'interface...", kind="front")
            os.makedirs(base, exist_ok=True)
            _download(front_asset["browser_download_url"], tmp_zip, MAX_FRONT_ZIP_BYTES)
            validate_zip(tmp_zip)
            # Optional compatibility gate: front_manifest.json {"requires_app": "2.10.1"}
            if parse_version(read_front_manifest(tmp_zip).get("requires_app", "0")) > current:
                _set_state("error", f"L'interface v{version_str} nécessite d'abord une version plus "
                                    f"récente de l'application.", last_check=datetime.now().isoformat())
                return get_status()
            apply_front_zip(tmp_zip, parse_version(version_str))
            _set_state("front_applied", f"Interface mise à jour (v{version_str}).", kind="",
                       current=fmt_version(current), last_check=datetime.now().isoformat())
        except Exception as exc:
            _set_state("error", f"Correctif d'interface refusé : {exc}", last_check=datetime.now().isoformat())
        finally:
            _silent_remove(tmp_zip)
        return get_status()

    _set_state("up_to_date", f"TASHIL est à jour (v{fmt_version(current)}).", kind="",
               last_check=datetime.now().isoformat())
    return get_status()


# --------------------------------------------------------------------------- #
# Entry points
# --------------------------------------------------------------------------- #
def trigger_manual_check() -> dict:
    """Marks the state 'checking' synchronously (so a UI poll right after the
    click never sees a stale answer), then DETECTS in a thread."""
    if _run_lock.locked():
        return get_status()
    _set_state("checking", "Recherche en cours...")
    threading.Thread(target=run_check, kwargs={"manual": True},
                     name="tashil-update-check", daemon=True).start()
    return get_status()


def trigger_apply() -> dict:
    """The 'Mettre à jour maintenant' click. Refuses unless an update was
    actually detected, so the route can't be used to force anything else."""
    if _run_lock.locked():
        return get_status()
    if get_status().get("state") != "available":
        return get_status()
    _set_state("downloading", "Préparation de la mise à jour...")
    threading.Thread(target=run_apply, name="tashil-update-apply", daemon=True).start()
    return get_status()


def start_background_check(first_delay: float = 25.0, interval_hours: float = 6.0):
    """Daemon thread: first DETECTION shortly after launch (once the UI is
    up), then periodically. Silent — it never downloads or applies anything;
    it only sets the 'available' state the UI banner reads. Disable for tests
    with TASHIL_DISABLE_AUTOUPDATE=1."""
    global _auto_started
    if _auto_started or os.environ.get("TASHIL_DISABLE_AUTOUPDATE") == "1":
        return
    _auto_started = True

    def loop():
        try:
            cleanup_leftovers()
        except Exception:
            pass
        time.sleep(first_delay)
        while True:
            try:
                run_check(manual=False, quiet=True)
            except Exception:
                pass
            time.sleep(interval_hours * 3600)

    threading.Thread(target=loop, name="tashil-update-auto", daemon=True).start()
