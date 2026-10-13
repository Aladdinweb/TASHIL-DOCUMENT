# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — WEB EDITION
Copyright ILINE TECH 2026 BY FERAK ALADDIN

A single Python backend that serves a normal responsive web page —
identical on Windows and on Android (Termux). No custom window chrome,
no manual widget positioning: the browser handles all layout.

v2.3.0 — Multi-tenant architecture: this device can now hold several
institution profiles side by side, each with its own isolated database
and archive folders, unlocked by a per-profile PIN. See the "Session /
multi-tenant" section below.

v2.8.1 — SQLite concurrency hardening: every connection now runs in WAL
(Write-Ahead Logging) mode with a 5-second busy_timeout, and every DB
access goes through a context manager that guarantees commit()/close()
even on error — see "SQLite connection handling" below. This fixes
"database is locked" errors observed on the desktop build, caused by the
background Cloud Bridge polling thread and a foreground send both
touching SQLite at once.

v2.8.2 — Two fixes from real desktop testing:
  1. Tracking numbers (next_tracking_number) previously relied solely on
     COUNT(*) for uniqueness, which drops whenever a message is deleted
     — the very next send could then recompute a number an existing
     message already held, causing "UNIQUE constraint failed:
     messages.tracking_number". A random suffix plus an existence check
     (and a retry-on-IntegrityError as a second line of defense in
     api_send_message) now make this effectively impossible.
  2. The desktop layout (static/css/style.css) previously hid the ENTIRE
     .topbar above 900px width, taking the 🌓 theme toggle, 🔒 lock
     button, and 🔄 refresh button with it — no equivalent controls
     existed anywhere else on desktop. Fixed with a CSS Grid layout that
     keeps the topbar visible as a header above the content column
     instead of hiding it; no HTML/JS changes were needed.

v2.8.3 — Camera-captured photos arriving "corrupted" on the recipient's
PC. Root cause verified, not assumed: iPhones running Safari default
their camera to HEIC — a perfectly valid photo, but Windows' built-in
Photos app can't open HEIC without an extra codec extension, which
shows the user "we can't open this file" / "image corrompue". The
upload pipeline itself (multipart file upload, Fernet encryption on raw
bytes, base64 only for the Cloud Bridge's GitHub transport) was audited
end to end and does NOT involve any Data-URL/base64 step on the
frontend — a previously-suspected cause that turned out not to apply to
this codebase, so no fix was invented for it. Two real changes instead:
  1. static/js/app.js: HEIC/HEIF (or any non-standard image type) is now
     converted to a normal JPEG client-side, via canvas, before upload.
     Non-image files and images already in a standard format pass
     through completely untouched. If the browser can't decode the
     source (some non-Safari browsers can't decode HEIC either), the
     original file is sent unchanged rather than losing the attachment.
  2. app.py: a new sniff_real_extension() checks the file's actual magic
     bytes and corrects the archived/displayed filename's extension if
     it disagrees with what the client claimed — a safety net, not a
     format converter, so a mislabeled file at least keeps an honest
     name. A genuinely empty (0-byte) upload is now rejected outright
     with a clear error instead of silently archived.

v2.8.4 — Message card readability + optional Windows system-tray
integration:
  1. Dashboard/Inbox/Registre cards previously showed the long
     tracking_number as the title, with the subject barely visible. The
     title is now the subject ("Sans objet" when empty), the subtitle
     shows the institution plus a short excerpt (message body, or the
     attached filename when the body is empty), and the tracking number
     is now a small monospace badge, kept for reference but no longer
     the headline. Frontend-only change (static/js/app.js,
     static/css/style.css) — no backend/API changes.
  2. A new is_read column tracks unread received messages (default 1 =
     read, so every pre-existing row stays unaffected; new entrant
     messages are inserted with is_read=0). Opening the inbox
     (GET /api/messages?direction=entrant) marks them read as a side
     effect. A new GET /api/messages/unread-count endpoint exposes the
     current unread count — this part has no OS-specific code and was
     tested end to end with the Flask test client.
  3. tray.py (new, fully optional module) + desktop_launcher.py: minimize
     -to-tray instead of exiting when the window is closed, a red
     unread-count badge drawn directly onto the tray icon (Pillow), and
     a toast notification (via plyer) when new messages arrive while the
     window is hidden. Every piece degrades to a complete no-op if
     pystray/plyer are unavailable or anything in tray.py raises — with
     or without a working tray, the window opens and closing it behaves
     at minimum exactly like v2.8.3.
     ⚠️ HONESTY NOTE: this sandbox has no Windows GUI and no display
     server pystray's own backends need even to import cleanly — the
     badge image COMPOSITION was rendered and visually verified with
     Pillow directly (including at a real 24×24px tray-icon size, which
     is why the badge font was resized after the first attempt proved
     illegible that small), and the unread-count endpoint was verified
     against the real database — but the actual on-screen tray behavior
     (does the icon appear next to the clock, does clicking it restore
     the window, does the toast actually pop up) has NOT been confirmed
     here and needs a real test on the Windows build, the same way
     pywebview/pyzbar/certifi each needed one real-device test in this
     project's history before being trusted.

v2.8.5 — National DSP coverage (58 wilayas), an institutional role
hierarchy (DIRECTEUR/DRH/DAS/SECRETARIAT for EPSP and DSP, SECRETARIAT-
only everywhere else, enforced server-side not just in the UI),
automatic hardware pairing, and serial_key-based recovery — replacing an
earlier proposal for a single shared "admin master key" that was
refused: a universal backdoor key baked into a publicly-distributed .exe
is exactly the concentration-of-risk problem this project already
refused once for the Cloud Bridge token (see v2.5.0, section 13.1),
worse here since it would touch confidential director/HR/social-affairs
mail nationwide. See STATE.md v2.8.5 for the full writeup, including a
real bug caught during testing (a misplaced decorator meant the hardware
pairing check silently never ran until fixed) and honestly-documented
known limitations (read-receipt routing doesn't yet know a sender's
specific role, only their institution name).

⚠️ Security honesty note: the PIN is a lock-screen deterrent against
casual/physical snooping on a shared device (hashed with werkzeug's
salted hash, never stored in plaintext) — it is NOT full-disk or
per-file encryption. Anyone with direct filesystem access to
~/TASHIL_DATA/profiles/<key>/ can still read the archived documents and
the SQLite database directly, PIN or not. Treat it as a screen lock, not
as data-at-rest encryption.

⚠️ Concurrency note: "active profile" is tracked as a single in-memory
value on the server process. This app is built for one person on one
device switching between institution hats — not for multiple people
using the same running server concurrently under different profiles.

Run directly:
    python app.py
Then open http://127.0.0.1:5000 in any browser (desktop or phone on the
same network, using the LAN IP shown at startup).
"""

import os
import re
import json
import socket
import sqlite3
import shutil
import secrets
import mimetypes
import tempfile
import hashlib
import hmac
import base64
import uuid
import platform
import subprocess
import time
from io import BytesIO
from datetime import datetime
from contextlib import contextmanager
import threading

from flask import (Flask, request, jsonify, send_from_directory,
                    send_file, render_template, abort)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# v2.9.0: Flask-SocketIO is OPTIONAL, same defensive pattern as qrcode/
# cryptography/certifi: if it is missing from a build, the app still starts
# and works exactly as before (the frontend falls back to its slow check).
try:
    from flask_socketio import SocketIO, join_room, leave_room, rooms
    _SOCKETIO_AVAILABLE = True
except ImportError:
    _SOCKETIO_AVAILABLE = False

try:
    import qrcode
    _QRCODE_AVAILABLE = True
except ImportError:
    _QRCODE_AVAILABLE = False

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes as _crypto_hashes
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

try:
    import certifi
    _CERTIFI_AVAILABLE = True
except ImportError:
    _CERTIFI_AVAILABLE = False

try:
    from pyzbar.pyzbar import decode as _zbar_decode
    _QR_DECODE_AVAILABLE = True
    _QR_DECODE_IMPORT_ERROR = None
except ImportError as _qr_import_exc:
    _QR_DECODE_AVAILABLE = False
    # Captured deliberately (unlike a bare False flag) — a previous choice
    # here (opencv-python-headless) failed to import in a real built exe
    # with no visible reason beyond "not available on this build". This
    # ensures that if the replacement ever fails too, the actual cause is
    # visible instead of another silent dead end.
    _QR_DECODE_IMPORT_ERROR = str(_qr_import_exc)

# --------------------------------------------------------------------------- #
# Paths — cross-platform, no admin rights required (works on Windows AND
# Termux/Android identically, unlike the old C:\TASHIL\... hardcoded paths).
# --------------------------------------------------------------------------- #
BASE_DIR = os.path.join(os.path.expanduser("~"), "TASHIL_DATA")
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
REGISTRY_DB_PATH = os.path.join(BASE_DIR, "registry.db")

# Legacy v2.x single-tenant paths (pre-v2.3.0) — used only for one-time
# migration into the new per-profile structure, never written to again.
_LEGACY_DB_PATH = os.path.join(BASE_DIR, "tashil.db")
_LEGACY_ARCHIVE_SORTANT = os.path.join(BASE_DIR, "archives", "Courrier_Sortant")
_LEGACY_ARCHIVE_ENTRANT = os.path.join(BASE_DIR, "archives", "Courrier_Entrant")

os.makedirs(PROFILES_DIR, exist_ok=True)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_VERSION = "2.9.6"
GITHUB_REPO = "Aladdinweb/TASHIL-ES"  # used by the in-app OTA update checker

app = Flask(__name__,
            template_folder=os.path.join(APP_ROOT, "templates"),
            static_folder=os.path.join(APP_ROOT, "static"))
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64MB upload cap

# v2.9.0: LOCAL real-time channel between this process and its own UI
# (desktop window, or a phone on the same LAN). threading mode on purpose —
# no eventlet/gevent, which are heavy to freeze with PyInstaller. Files
# still travel over plain HTTP multipart; the socket only carries small
# notifications. No CORS override: same-origin only.
if _SOCKETIO_AVAILABLE:
    socketio = SocketIO(app, async_mode="threading", ping_interval=20,
                        ping_timeout=40, max_http_buffer_size=1_000_000)
else:
    socketio = None


# --------------------------------------------------------------------------- #
# Global JSON error handling. Without this, any unhandled exception or
# oversized upload on an /api/ route falls through to Flask/Werkzeug's
# default HTML error page — which is exactly what broke sending from the
# desktop PC: the frontend calls res.json() on that HTML page and gets
# "Unexpected token '<', <!doctype ..." instead of a real error message.
# Every /api/ route now always returns JSON, no matter what fails inside
# it; non-API routes (the page itself, static files) are unaffected.
# --------------------------------------------------------------------------- #
@app.errorhandler(413)
def handle_payload_too_large(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Fichier trop volumineux (limite : 64 Mo)."}), 413
    return e


@app.errorhandler(404)
def handle_not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Route introuvable."}), 404
    return e


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    if request.path.startswith("/api/"):
        # Log the real exception server-side for diagnosis, but never leak
        # a raw traceback to the frontend — just a clear, safe JSON error.
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Erreur interne du serveur : {e}"}), 500
    raise e

INSTITUTION_TYPES = ["DSP", "EPSP", "EPH", "CHU", "EHU"]
# v2.8.6: "Polyclinique" removed from INSTITUTION_TYPES — a polyclinic is
# no longer onboarded as its own institution type; it's a specific NAME
# chosen under an EPSP (see get_onboarding_institutions), with its own
# distinct role (SECRETARIAT_POLYCLINIQUE). "Polyclinique" stays mapped
# in _TYPE_CODES so any institution_key/serial_key already stored for a
# pre-v2.8.6 profile of that type still decodes/regenerates correctly —
# removing it here would only affect NEW onboarding, which is already
# blocked by its absence from INSTITUTION_TYPES above.
_TYPE_CODES = {"DSP": "DS", "EPSP": "EP", "EPH": "EH", "CHU": "CU", "EHU": "HU", "Polyclinique": "PC"}

# v2.8.6: the generic "SECRETARIAT" role is retired in favor of
# explicit, non-ambiguous labels — a secretariat can mean different
# things in this system (a direction-level secretariat, a general/front
# secretariat, or a specific polyclinic's front-desk secretariat), and
# collapsing them into one label made addressing genuinely ambiguous.
ROLE_SECRETARIAT_DIRECTION = "SECRETARIAT_DIRECTION"
ROLE_SECRETARIAT_GENERAL = "SECRETARIAT_GENERAL"
ROLE_SECRETARIAT_POLYCLINIQUE = "SECRETARIAT_POLYCLINIQUE"
DEFAULT_ROLE = ROLE_SECRETARIAT_DIRECTION

# v2.8.5/6/7: institutional role hierarchy. A DSP or an EPSP head office
# has several real distinct services that each need their own isolated
# inbox (DIRECTEUR sees confidential mail, DRH sees personnel matters,
# etc.). EPH/CHU/EHU now get the same kind of precise service choice
# (DRH, DAS, a direction-level secretariat, and a general secretariat)
# rather than a single catch-all role — requested explicitly so staff at
# these standalone facilities can pick their exact service too.
ROLE_RULES = {
    "DSP": ["DIRECTEUR", ROLE_SECRETARIAT_DIRECTION],
    "EPSP": ["DIRECTEUR", "DRH", "DAS", ROLE_SECRETARIAT_DIRECTION],
    # v2.8.8: DIRECTEUR added for EPH/CHU/EHU (was missing in v2.8.7) —
    # these standalone hospital facilities get the same 5-role set for
    # BOTH staff onboarding and the send form's service filter.
    "EPH": ["DIRECTEUR", "DRH", "DAS", ROLE_SECRETARIAT_DIRECTION, ROLE_SECRETARIAT_GENERAL],
    "CHU": ["DIRECTEUR", "DRH", "DAS", ROLE_SECRETARIAT_DIRECTION, ROLE_SECRETARIAT_GENERAL],
    "EHU": ["DIRECTEUR", "DRH", "DAS", ROLE_SECRETARIAT_DIRECTION, ROLE_SECRETARIAT_GENERAL],
}


def _is_satellite_structure_name(institution_name: str) -> bool:
    """
    v2.8.7: a "satellite" structure — a polyclinic OR a salle de soin —
    attached to an EPSP, identified by its NAME starting with
    "POLYCLINIQUE" or "SALLE DE SOIN" (case-insensitive), rather than by
    a separate institution_type. Matches every curated real name in
    _EPSP_HIERARCHY, and any future one typed the same way, with no code
    change needed per new satellite structure. (Named
    _is_polyclinique_name through v2.8.6; renamed when "salle de soin"
    entries were added — same role, SECRETARIAT_POLYCLINIQUE, applies to
    both kinds, since neither has direction-level staff of its own.)
    """
    name = institution_name.strip().upper()
    return name.startswith("POLYCLINIQUE") or name.startswith("SALLE DE SOIN")


def allowed_roles(institution_type: str, institution_name: str = None) -> list:
    """
    v2.8.6/7: role availability depends on the NAME too, not just the
    type — an EPSP's own head office (e.g. "EPSP ES SENIA") gets the
    full direction-level role set, but a polyclinic or salle de soin
    NAMED under that same EPSP type gets exactly one role:
    SECRETARIAT_POLYCLINIQUE. EPH/CHU/EHU get their own 4-role set via
    ROLE_RULES above; anything else not listed falls back to
    DEFAULT_ROLE alone, defensively.
    """
    if institution_type == "EPSP" and institution_name and _is_satellite_structure_name(institution_name):
        return [ROLE_SECRETARIAT_POLYCLINIQUE]
    return ROLE_RULES.get(institution_type, [DEFAULT_ROLE])


WILAYAS = [
    (1, "Adrar"), (2, "Chlef"), (3, "Laghouat"), (4, "Oum El Bouaghi"),
    (5, "Batna"), (6, "Béjaïa"), (7, "Biskra"), (8, "Béchar"),
    (9, "Blida"), (10, "Bouira"), (11, "Tamanrasset"), (12, "Tébessa"),
    (13, "Tlemcen"), (14, "Tiaret"), (15, "Tizi Ouzou"), (16, "Alger"),
    (17, "Djelfa"), (18, "Jijel"), (19, "Sétif"), (20, "Saïda"),
    (21, "Skikda"), (22, "Sidi Bel Abbès"), (23, "Annaba"), (24, "Guelma"),
    (25, "Constantine"), (26, "Médéa"), (27, "Mostaganem"), (28, "M'Sila"),
    (29, "Mascara"), (30, "Ouargla"), (31, "Oran"), (32, "El Bayadh"),
    (33, "Illizi"), (34, "Bordj Bou Arreridj"), (35, "Boumerdès"),
    (36, "El Tarf"), (37, "Tindouf"), (38, "Tissemsilt"), (39, "El Oued"),
    (40, "Khenchela"), (41, "Souk Ahras"), (42, "Tipaza"), (43, "Mila"),
    (44, "Aïn Defla"), (45, "Naâma"), (46, "Aïn Témouchent"), (47, "Ghardaïa"),
    (48, "Relizane"), (49, "Timimoun"), (50, "Bordj Badji Mokhtar"),
    (51, "Ouled Djellal"), (52, "Béni Abbès"), (53, "In Salah"),
    (54, "In Guezzam"), (55, "Touggourt"), (56, "Djanet"),
    (57, "El M'Ghair"), (58, "El Meniaa"),
]

# --------------------------------------------------------------------------- #
# Institution directory (autocomplete source for "Institution destinataire"
# when sending a message — unaffected by the multi-tenant change below).
#
# ⚠️ STARTER LIST, NOT AN OFFICIAL REGISTRY — see onboarding directory notes
# further down for the same caveat, which applies here too.
# --------------------------------------------------------------------------- #
# v2.8.7: a wilaya has SEVERAL distinct EPSPs, each with its own head
# office and its own specifically-attached satellite structures
# (polyclinics, salles de soin) — NOT one undifferentiated "EPSP
# <Wilaya>" covering everything, which was the pre-v2.8.7 model and
# caused real institutions to be unfindable (e.g. "EPSP MISSERGHIN" or
# "EPSP SEDDIKIA" simply didn't exist as onboarding choices).
#
# v2.8.9: this hierarchy now lives in an EXTERNAL JSON file rather than
# a hardcoded Python dict — ~/TASHIL_DATA/epsp_hierarchy.json, editable
# directly by an administrator (add a wilaya, a new EPSP, a new
# polyclinic) with no code change and no app rebuild required. A new
# entry's serial_key is generated automatically the moment
# tools/generate_serial_registry.py is re-run (or that institution is
# really onboarded) — generate_serial_key() is a pure function of
# (wilaya, type, name, role), so a JSON-sourced entry is indistinguish-
# able from a hardcoded one to the rest of the system. Editing the file
# requires an app restart to take effect (loaded once at startup, same
# as INSTITUTIONS_DIRECTORY below) — not hot-reloaded per request.
#
# ⚠️ Only Oran (wilaya 31) has a real, user-confirmed hierarchy in the
# bundled default — every other wilaya still falls back to the single
# generic "EPSP <Wilaya>" head-office option with no satellites, exactly
# as before v2.8.7, until its own real EPSP breakdown is added to the
# JSON file the same way. Guessing a hierarchy for a wilaya without
# confirmed data would risk misrouting real administrative/medical
# correspondence — worse than temporarily offering only the generic
# head-office option, which every "Autre (saisir manuellement)"
# fallback already covers today.
EPSP_HIERARCHY_FILENAME = "epsp_hierarchy.json"
_BUNDLED_EPSP_HIERARCHY_PATH = os.path.join(APP_ROOT, "data", EPSP_HIERARCHY_FILENAME)


def _live_epsp_hierarchy_path() -> str:
    return os.path.join(BASE_DIR, EPSP_HIERARCHY_FILENAME)


def _ensure_live_epsp_hierarchy_file():
    """
    Copies the bundled default hierarchy to ~/TASHIL_DATA/ the FIRST
    time the app ever runs on a given machine — from then on, the live
    file there is authoritative and is never overwritten again, so an
    administrator's manual edits always survive future app updates or
    rebuilds (which only ever touch the bundled copy, never the live one).
    """
    os.makedirs(BASE_DIR, exist_ok=True)
    live_path = _live_epsp_hierarchy_path()
    if not os.path.exists(live_path):
        try:
            shutil.copy(_BUNDLED_EPSP_HIERARCHY_PATH, live_path)
        except Exception:
            pass  # bundled default missing/unreadable — load_epsp_hierarchy() falls back to {}


def load_epsp_hierarchy() -> dict:
    """
    Loads the live JSON file into the {wilaya_code: {epsp_name: [satellites]}}
    shape the rest of this file expects. Falls back to an EMPTY dict
    (== the generic "EPSP <Wilaya>" placeholder for every wilaya) if the
    file is missing, unreadable, or malformed — a bad manual edit
    degrades gracefully instead of crashing the app on startup.
    """
    _ensure_live_epsp_hierarchy_file()
    try:
        with open(_live_epsp_hierarchy_path(), "r", encoding="utf-8") as f:
            raw = json.load(f)
        # JSON object keys are always strings — wilaya codes must be
        # ints to match how every other lookup in this file works
        # (WILAYAS, get_onboarding_institutions, etc.).
        return {int(k): v for k, v in raw.items()}
    except Exception:
        return {}


_EPSP_HIERARCHY = load_epsp_hierarchy()

_CHU_WILAYAS = {"Alger", "Oran", "Constantine", "Annaba", "Tlemcen", "Sétif",
                "Batna", "Blida", "Béjaïa", "Sidi Bel Abbès", "Tizi Ouzou"}

def _build_institutions_directory():
    entries = []
    for wilaya_code, wilaya_name in WILAYAS:
        entries.append(f"DSP {wilaya_name}")  # v2.8.5: one DSP per wilaya, all 58 covered
        epsp_hierarchy = _EPSP_HIERARCHY.get(wilaya_code)
        if epsp_hierarchy:
            # v2.8.7: every real, distinctly-named EPSP head office AND
            # every satellite structure attached to it — not the generic
            # "EPSP <Wilaya>" placeholder, which no longer applies once
            # a wilaya's real breakdown is known.
            for epsp_name, satellites in epsp_hierarchy.items():
                entries.append(epsp_name)
                entries.extend(satellites)
        else:
            entries.append(f"EPSP {wilaya_name}")
        entries.append(f"EPH {wilaya_name}")
        if wilaya_name in _CHU_WILAYAS:
            entries.append(f"CHU {wilaya_name}")
    return sorted(set(entries))


INSTITUTIONS_DIRECTORY = _build_institutions_directory()

# --------------------------------------------------------------------------- #
# Onboarding institution dropdown (feature 1) — deliberately smaller and
# more curated than the messaging autocomplete above: this is what fills
# the "Nom de l'établissement" <select> during onboarding.
#
# ⚠️ Only Oran (wilaya 31) has real, user-confirmed entries below. Every
# other wilaya falls back to a single generic "<Type> <Wilaya>" option.
# The onboarding form always keeps an "Autre (saisir manuellement)" choice
# too, so no one is ever blocked by an incomplete list.
# --------------------------------------------------------------------------- #
_ONBOARDING_KNOWN = {
    (31, "EPH"): ["EPH AIN TURCK"],
    (31, "CHU"): ["CHU ORAN"],
    (31, "EHU"): ["EHU ORAN"],
}

def get_onboarding_institutions(wilaya_code: int, institution_type: str):
    wilaya_name = dict(WILAYAS).get(wilaya_code)
    if wilaya_name is None:
        return []

    if institution_type == "EPSP":
        # v2.8.7: list EVERY real, distinctly-named EPSP for this
        # wilaya, each immediately followed by its own satellite
        # structures — "[Nom EPSP] - SIÈGE" is shown as the label in the
        # frontend's <option> text (see app.js), while the stored
        # institution_name stays the clean "EPSP X" (no suffix), so
        # addressing/registry entries remain simple exact-name matches.
        # Falls back to the single generic head-office option for any
        # wilaya without a confirmed real breakdown yet.
        epsp_hierarchy = _EPSP_HIERARCHY.get(wilaya_code)
        if epsp_hierarchy:
            result = []
            for epsp_name, satellites in epsp_hierarchy.items():
                result.append(epsp_name)
                result.extend(satellites)
            return result
        return [f"EPSP {wilaya_name}"]

    generic = f"{institution_type} {wilaya_name}"
    known = _ONBOARDING_KNOWN.get((wilaya_code, institution_type), [])
    return list(known) if known else [generic]



# --------------------------------------------------------------------------- #
# SQLite connection handling (v2.8.1)
#
# Every single connection opened anywhere in this file — registry or
# per-profile — goes through _open_sqlite_connection(), which:
#   1. Sets a 5-second sqlite3 connect timeout AND `PRAGMA busy_timeout
#      = 5000` — if a writer already holds the database, a second
#      connection now waits up to 5s for it to finish instead of
#      raising "database is locked" immediately.
#   2. Enables `PRAGMA journal_mode=WAL` — Write-Ahead Logging lets
#      readers and a single writer work concurrently instead of
#      exclusive-locking the whole file for every write. This is a
#      database-level setting (persisted in the file itself), so
#      re-issuing it on every connection is a cheap no-op after the
#      first time, not a repeated migration.
#
# registry_db() / profile_db(key) are context managers built on top of
# this: `with registry_db() as conn:` guarantees conn.commit() runs on
# success and conn.close() runs unconditionally (success OR exception),
# so a slow request, a network call, or a bug inside the `with` block
# can never leave a connection open and holding a lock. Pass
# commit=False for read-only blocks where a commit would be a no-op
# anyway (harmless either way, but explicit is clearer).
# --------------------------------------------------------------------------- #
# v2.9.0: 5 s -> 30 s. This is only a safety margin: the REAL fix for
# "database is locked" is that no connection is held open across a network
# call anymore (see run_bridge_poll) and that read-then-write blocks take
# the write lock up-front with BEGIN IMMEDIATE (see _db_write and the
# three routes below). In WAL mode a deferred transaction that reads and
# then tries to write can fail IMMEDIATELY with SQLITE_BUSY whatever the
# timeout is — busy_timeout cannot help that case.
DB_TIMEOUT_SECONDS = 30


def _open_sqlite_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=DB_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(f"PRAGMA busy_timeout={DB_TIMEOUT_SECONDS * 1000};")
    conn.execute("PRAGMA synchronous=NORMAL;")  # safe in WAL, far fewer fsyncs
    return conn


def get_registry_db() -> sqlite3.Connection:
    """Raw connection factory. Prefer the registry_db() context manager
    below in route/business-logic code — this is kept for the handful of
    call sites (init, migration) that need to manage their own lifecycle."""
    return _open_sqlite_connection(REGISTRY_DB_PATH)


@contextmanager
def registry_db(commit: bool = True):
    conn = get_registry_db()
    try:
        yield conn
        if commit:
            conn.commit()
    finally:
        conn.close()


def init_registry_db():
    with registry_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                institution_key TEXT PRIMARY KEY,
                wilaya_code INTEGER NOT NULL,
                wilaya_name TEXT NOT NULL,
                institution_type TEXT NOT NULL,
                institution_name TEXT NOT NULL,
                serial_key TEXT NOT NULL,
                pin_hash TEXT,
                theme TEXT DEFAULT 'dark',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bridge_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                github_owner TEXT,
                github_repo TEXT,
                github_token TEXT,
                enabled INTEGER DEFAULT 0,
                updated_at TEXT
            )
        """)
        # v2.9.5: github_owner/repo/token above are DEAD columns, kept
        # only so an upgrade never has to DROP anything (SQLite's DROP
        # COLUMN support is recent/finicky) — the GitHub Bridge is fully
        # replaced by the Cloudflare Worker Bridge below. worker_url is
        # entered once in Paramètres; device_secret is generated locally
        # (see ensure_device_secret()) and NEVER typed by the user — it
        # is this DEVICE's standing credential for every Worker call it
        # makes, for every institution profile hosted on it.
        bc_cols = [r[1] for r in conn.execute("PRAGMA table_info(bridge_config)").fetchall()]
        if "worker_url" not in bc_cols:
            conn.execute("ALTER TABLE bridge_config ADD COLUMN worker_url TEXT")
        if "device_secret" not in bc_cols:
            conn.execute("ALTER TABLE bridge_config ADD COLUMN device_secret TEXT")
        # Schema migration for pre-v2.7.0 databases: CREATE TABLE IF NOT
        # EXISTS above won't add a new column to an already-existing
        # table, so this runs an explicit, idempotent, backward-compatible
        # ALTER. Existing profiles get encryption_salt = NULL, which the
        # app treats as "legacy, unencrypted" — they keep working exactly
        # as before, in plaintext. Only profiles created from this version
        # onward opt into encryption.
        existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(profiles)").fetchall()]
        if "encryption_salt" not in existing_cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN encryption_salt TEXT")
        # v2.8.5: role hierarchy (DIRECTEUR/DRH/DAS/SECRETARIAT for
        # EPSP, DIRECTEUR/SECRETARIAT for DSP, SECRETARIAT-only for
        # everything else) and hardware pairing. DEFAULT 'SECRETARIAT'
        # means every profile created before this version — which had
        # no concept of roles — is treated as a plain secretariat inbox,
        # exactly matching its prior behavior (nothing was filtered by
        # role before, so nothing changes for it now). Re-running this
        # ALTER on an already-migrated database is a silent no-op thanks
        # to the "not in existing_cols" guard, same pattern as every
        # other migration in this function.
        if "role" not in existing_cols:
            # v2.8.6 fix: do NOT default straight to DEFAULT_ROLE here —
            # a pre-v2.8.5 database has no role information at all yet,
            # and defaulting it immediately to today's DEFAULT_ROLE would
            # make it indistinguishable from a genuinely SECRETARIAT_
            # DIRECTION row, so a legacy Polyclinique-typed profile would
            # never get correctly reclassified as SECRETARIAT_POLYCLINIQUE
            # by the UPDATE just below. Leave it NULL; the classification
            # step handles both this case and the v2.8.5-only case (where
            # the column already existed with the literal 'SECRETARIAT').
            conn.execute("ALTER TABLE profiles ADD COLUMN role TEXT")
        # NULL until the first successful unlock on a given machine —
        # see get_hardware_fingerprint() and api_session_unlock().
        if "paired_hardware_hash" not in existing_cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN paired_hardware_hash TEXT")
        # v2.9.5: 0/NULL until this institution_key has been successfully
        # /register'd against the Cloudflare Worker Bridge — see
        # _ensure_worker_registration(). Lets the heartbeat loop catch up
        # a profile created before the Worker URL was configured, same
        # spirit as the GitHub-era _ensure_registration_claimed().
        if "worker_registered" not in existing_cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN worker_registered INTEGER DEFAULT 0")

        # v2.8.6: classify any row with no role info yet (NULL — a
        # freshly-added column on a pre-v2.8.5 database) OR the legacy
        # generic 'SECRETARIAT' value (a v2.8.5-only database, before
        # this split existed) — a pre-v2.8.6 Polyclinique-typed profile
        # becomes SECRETARIAT_POLYCLINIQUE; everything else (DSP/EPSP/
        # EPH/CHU/EHU) becomes SECRETARIAT_DIRECTION. Runs every startup
        # rather than being gated behind a one-time flag — cheap,
        # targeted UPDATE ... WHERE that becomes a genuine no-op (0 rows
        # matched) once every legacy row has been classified once.
        conn.execute(
            "UPDATE profiles SET role = ? WHERE (role IS NULL OR role = 'SECRETARIAT') "
            "AND institution_type = 'Polyclinique'",
            (ROLE_SECRETARIAT_POLYCLINIQUE,)
        )
        conn.execute(
            "UPDATE profiles SET role = ? WHERE role IS NULL OR role = 'SECRETARIAT'",
            (ROLE_SECRETARIAT_DIRECTION,)
        )


init_registry_db()


def sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip() or "document"


def sniff_real_extension(file_bytes: bytes, fallback_ext: str) -> str:
    """
    Best-effort file-signature check (magic bytes), independent of
    whatever extension the client's filename claims.

    v2.8.3: added as a defense-in-depth safety net alongside the
    frontend's HEIC→JPEG conversion (static/js/app.js,
    normalizeImageForUpload). The frontend fix is what actually solves
    the reported "corrupted image" symptom for camera captures — a
    HEIC photo from an iPhone's Safari camera is a perfectly valid
    file, but Windows Photos can't open HEIC without an extra codec,
    which reads to a user as "corrupted". This backend check does NOT
    convert anything (it can't — decoding image formats server-side
    would be a much bigger dependency than this bug warrants); it only
    makes sure the archived/displayed filename's extension matches
    what the bytes actually are. That protects against a MISLABELED
    extension (e.g. a client sending real HEIC bytes named "photo.jpg")
    reaching a recipient with a name that lies about the format —
    which would show a more confusing "file is corrupted" error
    instead of a correct, if still unopenable-without-a-viewer, ".heic".
    Not exhaustive by design — falls back to whatever the client
    claimed for anything not in this short, common list.
    """
    if file_bytes[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if file_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if file_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
        return ".webp"
    if len(file_bytes) >= 12 and file_bytes[4:8] == b"ftyp" and \
            file_bytes[8:12] in (b"heic", b"heix", b"hevc", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1"):
        return ".heic"
    return fallback_ext


def make_institution_key(wilaya_code: int, institution_type: str, institution_name: str, role: str) -> str:
    """
    v2.8.5: now incorporates the ROLE, not just the institution — each
    (institution, role) pair is a fully separate profile/poste with its
    own isolated inbox, so the DRH and DIRECTEUR of the same EPSP are
    two distinct keys, never sharing a database.
    """
    type_code = _TYPE_CODES.get(institution_type, "XX")
    slug = re.sub(r'[^A-Za-z0-9]+', '_', institution_name.strip().upper()).strip('_')
    role_slug = re.sub(r'[^A-Za-z0-9]+', '_', role.strip().upper()).strip('_') or DEFAULT_ROLE
    base_key = f"{wilaya_code:02d}_{type_code}_{slug}_{role_slug}"[:90]

    with registry_db(commit=False) as conn:
        key = base_key
        suffix = 2
        while conn.execute("SELECT 1 FROM profiles WHERE institution_key = ?", (key,)).fetchone():
            key = f"{base_key}_{suffix}"
            suffix += 1
    return key


# v2.8.5: this secret used to be hardcoded here — fine as long as this
# file stayed private, but app.py lives in a PUBLIC GitHub repository.
# Anyone reading the source could already recompute any institution's
# serial key, since wilaya codes, type codes, and institution-naming
# conventions are ALSO all in this same public file. Moving the secret
# to an environment variable doesn't retroactively protect any key
# already issued with the old hardcoded value (see the honesty note in
# generate_serial_key below), but it means a real, private secret set
# at deployment time actually protects every key issued from here on.
# The fallback below exists ONLY so a fresh install still works before
# anyone has configured a real secret — it must be overridden via the
# TASHIL_HMAC_SECRET environment variable for any real deployment.
_DEFAULT_INSECURE_SECRET = b"ILINE-TECH-2026-FERAK-ALADDIN-TASHIL-DOCUMENT-HUB"


def _hmac_secret() -> bytes:
    env_value = os.environ.get("TASHIL_HMAC_SECRET")
    return env_value.encode("utf-8") if env_value else _DEFAULT_INSECURE_SECRET


def generate_serial_key(wilaya_code, institution_type, institution_name, role: str = DEFAULT_ROLE) -> str:
    """
    v2.8.5: made fully deterministic (the previous version mixed in
    today's date, which was fine when the key was only ever generated
    once at real onboarding and stored — but is incompatible with
    PRE-generating a national reference registry ahead of time, per
    tools/generate_serial_registry.py: the central export and the real
    onboarding on the institution's own machine, possibly months apart,
    must compute the exact same value. Role is now part of the input so
    the DRH and DIRECTEUR of the same EPSP get different keys, matching
    make_institution_key.

    ⚠️ Verification never recomputes this — api_session_recover compares
    a submitted key against the STORED profiles.serial_key column, so
    rotating TASHIL_HMAC_SECRET is always safe for already-issued keys;
    it only changes what gets generated for NEW institutions from then on.
    """
    secret = _hmac_secret()
    type_code = _TYPE_CODES.get(institution_type, "XX")
    role_norm = (role or DEFAULT_ROLE).strip().upper()
    payload = f"{wilaya_code:02d}|{type_code}|{institution_name.strip().upper()}|{role_norm}"
    digest = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).digest()
    body_hex = digest.hex()[:4].upper()
    checksum = base64.b32encode(digest[:3]).decode("utf-8")[:4]
    return f"TSH-{wilaya_code:02d}-{type_code}-{body_hex}-{checksum}"


def list_profiles():
    with registry_db(commit=False) as conn:
        rows = conn.execute("SELECT * FROM profiles ORDER BY institution_name").fetchall()
    return [dict(r) for r in rows]


def get_profile_row(institution_key: str):
    with registry_db(commit=False) as conn:
        row = conn.execute(
            "SELECT * FROM profiles WHERE institution_key = ?", (institution_key,)
        ).fetchone()
    return dict(row) if row else None


def profile_public_dict(row: dict) -> dict:
    """Strip pin_hash before ever sending a profile row to the frontend."""
    return {k: v for k, v in row.items() if k != "pin_hash"}


def profile_paths(institution_key: str):
    folder = os.path.join(PROFILES_DIR, institution_key)
    return {
        "folder": folder,
        "db": os.path.join(folder, "tashil.db"),
        "sortant": os.path.join(folder, "archives", "Courrier_Sortant"),
        "entrant": os.path.join(folder, "archives", "Courrier_Entrant"),
    }


def get_profile_db(institution_key: str) -> sqlite3.Connection:
    """Raw connection factory for a profile's isolated database — ensures
    folders + schema exist, applies WAL/busy_timeout. Prefer the
    profile_db(key) context manager below in route/business-logic code."""
    paths = profile_paths(institution_key)
    os.makedirs(paths["sortant"], exist_ok=True)
    os.makedirs(paths["entrant"], exist_ok=True)
    conn = _open_sqlite_connection(paths["db"])
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            direction TEXT NOT NULL,
            tracking_number TEXT UNIQUE NOT NULL,
            sender_institution TEXT,
            recipient_institution TEXT,
            subject TEXT,
            body TEXT,
            file_path TEXT,
            file_original_name TEXT,
            status TEXT DEFAULT 'envoye',
            created_at TEXT NOT NULL
        )
    """)
    # Idempotent migration: tracks HOW a message reached this database
    # ('local', 'bridge', or NULL for anything predating this column) —
    # needed so accusé-de-réception can route a receipt back to the right
    # place (see api_update_message_status).
    existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()]
    if "delivery_method" not in existing_cols:
        conn.execute("ALTER TABLE messages ADD COLUMN delivery_method TEXT")
    # v2.8.4: unread tracking for the desktop system-tray badge/toast
    # notification feature (see desktop_launcher.py). Default 1 ("read")
    # so every EXISTING row — sent or received, before this column
    # existed — is treated as already seen; only newly-inserted entrant
    # messages from this version onward are explicitly written with
    # is_read=0, which is what actually drives the unread count.
    if "is_read" not in existing_cols:
        conn.execute("ALTER TABLE messages ADD COLUMN is_read INTEGER DEFAULT 1")
        # v2.8.7: fixes a real, previously-documented bug (STATE.md
        # v2.8.5 §22.9) — read-receipt routing only knew the sender's
        # institution NAME, so it silently failed (leaving "En attente"
        # stuck forever) whenever the sender's role wasn't the default
        # one, or several role-specific profiles shared that name. This
        # column records the sender's own exact institution_key on
        # every message it delivers to someone else's inbox — an
        # unambiguous address to route the accusé back to, no name/role
        # guessing needed. NULL for messages received before this
        # column existed; route_read_receipt() falls back to the old
        # name-based matching for those.
        if "sender_institution_key" not in existing_cols:
            conn.execute("ALTER TABLE messages ADD COLUMN sender_institution_key TEXT")
        # v2.9.5: the Cloudflare Worker Bridge addresses every institution
        # by bridge_slug(name, role) — not the real institution_key (the
        # sender's free-text "Institution destinataire" field never
        # carries enough to compute the real key; see bridge_slug's own
        # docstring). sender_institution_key above still holds the REAL
        # key for a LOCALLY delivered message; for a Worker-delivered one
        # this new column instead holds the sender's Worker-side slug id,
        # exactly as the Worker itself reported it in the message
        # metadata — used only to address the /accuse call back to them.
        if "sender_worker_id" not in existing_cols:
            conn.execute("ALTER TABLE messages ADD COLUMN sender_worker_id TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bridge_pending_cleanup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_path TEXT NOT NULL,
            sha TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    # v2.8.9: queues an outgoing Cloud Bridge push (a message send, or a
    # read-receipt) that failed — including "Erreur GitHub (0)" network
    # blips — so it's automatically retried on the next poll cycle
    # (every ~20s, see the frontend's background timer) instead of being
    # silently lost. 'kind' is 'message' or 'receipt'; 'payload' is a
    # JSON blob with everything needed to reconstruct that specific push
    # (see _queue_pending_push / _flush_pending_pushes).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bridge_pending_push (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    # v2.9.4: multiple attachments per message. messages.file_path /
    # file_original_name (the original, v1 columns) are LEFT AS-IS for
    # backward compatibility — every message sent before this version
    # keeps working exactly as before, read straight from those columns.
    # A NEW message (this version onward) instead gets one row per
    # attachment here, and its own messages.file_path/file_original_name
    # are populated with the FIRST attachment's values too (so anything
    # that still only reads the old single-file columns — an older build
    # talking to this same database, a saved link — still shows at least
    # that first file; the authoritative full list lives here).
    # get_message_attachments() below is the one place that resolves
    # either shape into a single list, so every other route only has to
    # call that, never branch on "old vs new message" itself.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS message_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL REFERENCES messages(id),
            file_path TEXT NOT NULL,
            file_original_name TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def get_message_attachments(conn, message_row) -> list:
    """
    v2.9.4: returns this message's attachments as a list of
    {"attachment_id", "file_path", "file_original_name"} dicts, in a
    stable order — regardless of whether this message predates multi-
    attachment support (falls back to its single legacy file_path/
    file_original_name columns, attachment_id 0) or was sent with
    several files (reads message_attachments, real row ids). Every route
    that touches attachments (download, preview, delete, Cloud Bridge
    push/pull) goes through this one function rather than re-deriving
    "old vs new message" logic itself.
    """
    rows = conn.execute(
        "SELECT id, file_path, file_original_name FROM message_attachments "
        "WHERE message_id = ? ORDER BY sort_order ASC, id ASC",
        (message_row["id"],)
    ).fetchall()
    if rows:
        return [{"attachment_id": r["id"], "file_path": r["file_path"],
                  "file_original_name": r["file_original_name"]} for r in rows]
    if message_row["file_path"]:
        return [{"attachment_id": 0, "file_path": message_row["file_path"],
                  "file_original_name": message_row["file_original_name"] or "document"}]
    return []


@contextmanager
def profile_db(institution_key: str, commit: bool = True):
    conn = get_profile_db(institution_key)
    try:
        yield conn
        if commit:
            conn.commit()
    finally:
        conn.close()


def _db_write(institution_key: str, sql: str, params=()):
    """One short, isolated write transaction on a profile database (v2.9.0).
    BEGIN IMMEDIATE takes the write lock right away (waiting up to
    DB_TIMEOUT_SECONDS) instead of upgrading a read lock later."""
    with profile_db(institution_key) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(sql, params)
        return cur.rowcount


def next_tracking_number(conn, direction: str, institution_key: str) -> str:
    """
    Tracking numbers embed a short institution code (derived from the
    wilaya+type prefix of institution_key) so that a number generated by
    one institution's database doesn't collide with an unrelated message
    already present in another institution's database when a message is
    delivered locally (see find_local_profile_by_recipient / api_send_message).

    v2.8.2 fix: the sequential part (count + 1) used to be the ONLY
    source of uniqueness — a real bug, because COUNT(*) drops whenever a
    message is deleted (api_delete_message), so the very next send could
    recompute a sequence number that an still-existing message already
    holds, and Insert failed with "UNIQUE constraint failed:
    messages.tracking_number". A random 6-character suffix is now always
    appended, so the tracking number no longer depends on the table
    still containing exactly the same rows it did a moment ago. Before
    handing the candidate back, we also check it isn't already taken —
    astronomically unlikely to ever loop even once, but checked rather
    than assumed. The sequential part is kept purely as a human-readable,
    roughly-chronological counter — it is never relied upon for
    uniqueness anymore.
    """
    prefix = "S" if direction == "sortant" else "E"
    year = datetime.now().year
    short = "".join(institution_key.split("_")[:2]) or "XX"
    count = conn.execute(
        "SELECT COUNT(*) as c FROM messages WHERE direction = ?", (direction,)
    ).fetchone()["c"]

    for _ in range(10):
        suffix = uuid.uuid4().hex[:6].upper()
        candidate = f"TASHIL-{short}-{prefix}-{year}-{count + 1:06d}-{suffix}"
        exists = conn.execute(
            "SELECT 1 FROM messages WHERE tracking_number = ?", (candidate,)
        ).fetchone()
        if not exists:
            return candidate

    # Should be unreachable in practice (10 random collisions in a row) —
    # fall back to a number with no sequential part at all, just in case.
    return f"TASHIL-{short}-{prefix}-{year}-{uuid.uuid4().hex[:12].upper()}"


def find_local_profile_by_recipient(recipient_text: str, recipient_role: str = None, exclude_key: str = None):
    """
    Looks for another profile registered on THIS device matching the
    given recipient. Three ways to match, tried in order:
      1. An exact institution ID/key (e.g. '31_EP_EPSP_ES_SENIA_DRH',
         shown to each poste as its "ID de routage" in Paramètres) —
         unambiguous by construction, works regardless of role.
      2. institution_name + role together (v2.8.5) — REQUIRED now that
         a single institution can have several role-specific profiles
         (DIRECTEUR, DRH, DAS, SECRETARIAT_DIRECTION for an EPSP/DSP);
         matching by name alone would be ambiguous and could deliver to
         the wrong service. recipient_role defaults to
         SECRETARIAT_DIRECTION when omitted, matching "si non spécifié,
         orienté vers le SECRETARIAT".
      3. institution_name alone, whenever exactly ONE profile with that
         name exists locally — regardless of whether a role was given
         (v2.8.6: relaxed from "only when role omitted", since a named
         polyclinic only ever has a single SECRETARIAT_POLYCLINIQUE
         profile, and the send form always submits SOME service value;
         requiring an exact role match there would make a polyclinic
         unreachable whenever the sender left the default service
         selection untouched). This never introduces ambiguity for a
         multi-role institution (EPSP head office), since len(name_matches)
         is only 1 when there truly is just one profile to deliver to.
    Returns None if no match — this does NOT reach across a network to a
    different computer; see the honesty note in api_send_message().
    """
    role_norm = (recipient_role or DEFAULT_ROLE).strip().upper()
    with registry_db(commit=False) as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM profiles").fetchall()]
    rows = [r for r in rows if r["institution_key"] != exclude_key]

    target_key = recipient_text.strip()
    target_name = recipient_text.strip().casefold()

    for row in rows:
        if row["institution_key"] == target_key:
            return row

    name_matches = [r for r in rows if r["institution_name"].strip().casefold() == target_name]
    role_matches = [r for r in name_matches if (r.get("role") or DEFAULT_ROLE).strip().upper() == role_norm]
    if role_matches:
        return role_matches[0]
    if len(name_matches) == 1:
        return name_matches[0]
    return None


# --------------------------------------------------------------------------- #
# Cloud Bridge — GitHub-backed transport for institutions NOT on this same
# device. Uses only the Python standard library (urllib) rather than a
# GitHub SDK, matching this project's "fewer packaging-risk dependencies"
# lesson from the pywebview/PyInstaller issues earlier.
#
# ⚠️ Security model, stated plainly: the configured repo's PRIVACY setting
# and who has access to it ARE the entire protection here — documents are
# committed as plain content, not end-to-end encrypted. The app refuses to
# save a bridge configuration pointing at a public repository (checked
# live against the GitHub API before saving), but it cannot stop someone
# from making a private repo public later, or from over-sharing repo
# access. Treat the bridge token as a real credential.
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# v2.9.5 — Cloudflare Worker Bridge (replaces the GitHub Bridge entirely).
#
# ⚠️ Security model, read before changing anything here: the Worker URL is
# PUBLIC (it ships inside every TASHIL install) — Cloudflare provides no
# authentication of its own for it. Every protected Worker route instead
# requires a per-institution secret_key, checked server-side on EVERY
# call (see the Worker's own requireValidSecret()), never just once at
# "login". device_secret below is THIS DEVICE's standing credential —
# generated locally, once, the first time it's needed, and reused for
# every institution profile this device hosts. To add a SECOND legitimate
# device for an institution ALREADY claimed elsewhere, that institution's
# original secret must be supplied once (see api_save_profile's
# original_secret_key handling) — this device then ADOPTS it as its own
# device_secret going forward, so every subsequent call from it
# authenticates consistently. This mirrors, and replaces, the GitHub-era
# shared-token model — just scoped per establishment instead of per repo.
# --------------------------------------------------------------------------- #
def ensure_device_secret() -> str:
    """Generates this device's Worker credential once, lazily, the first
    time it's needed — independent of whether a Worker URL has even been
    entered yet in Paramètres, so it's always ready. Never regenerated
    once it exists (that would silently orphan every institution this
    device had already registered)."""
    with registry_db() as conn:
        row = conn.execute("SELECT device_secret FROM bridge_config WHERE id = 1").fetchone()
        if row and row["device_secret"]:
            return row["device_secret"]
        secret = secrets.token_hex(32)
        conn.execute("""
            INSERT INTO bridge_config (id, device_secret, enabled, updated_at)
            VALUES (1, ?, 0, ?)
            ON CONFLICT(id) DO UPDATE SET device_secret = excluded.device_secret
        """, (secret, datetime.now().isoformat()))
        return secret


def adopt_device_secret(new_secret: str):
    """Called once an original_secret_key supplied during onboarding is
    confirmed correct by the Worker — see api_save_profile. From this
    point on, THIS device authenticates with the shared secret instead
    of (silently discarding) its own independently generated one."""
    with registry_db() as conn:
        conn.execute("UPDATE bridge_config SET device_secret = ? WHERE id = 1", (new_secret,))


def get_bridge_config():
    with registry_db(commit=False) as conn:
        row = conn.execute("SELECT * FROM bridge_config WHERE id = 1").fetchone()
    if row is None or not row["worker_url"]:
        return None
    return {
        "worker_url": row["worker_url"].rstrip("/"),
        "device_secret": row["device_secret"] or ensure_device_secret(),
        "enabled": bool(row["enabled"]),
    }


def _worker_request(worker_url: str, method: str, path: str, body: dict = None,
                    query: dict = None, _max_retries: int = 2):
    """
    Minimal JSON HTTP client (urllib only) for the Cloudflare Worker
    Bridge — same certifi-pinned SSL context and same network-failure
    retry policy as the GitHub-era _github_request() (see that function's
    history: status 0 = no real HTTP response at all, i.e. a network
    hiccup worth retrying; any real HTTP status — including a 401 from a
    wrong secret — is returned as-is, never retried, since retrying can't
    change a real answer). Returns (status_code, parsed_json_or_{}).
    """
    import urllib.request
    import urllib.error
    import urllib.parse
    import ssl

    url = f"{worker_url}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "User-Agent": "TASHIL-DOCUMENT-HUB/1.0"}  # v2.9.7: evite le blocage anti-bot Cloudflare
    data = json.dumps(body).encode("utf-8") if body is not None else None
    ssl_context = ssl.create_default_context(cafile=certifi.where()) if _CERTIFI_AVAILABLE else None

    last_exc = None
    for attempt in range(_max_retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20, context=ssl_context) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw.decode("utf-8")) if raw else {})
        except urllib.error.HTTPError as e:
            try:
                payload = json.loads(e.read().decode("utf-8"))
            except Exception:
                payload = {}
            return e.code, payload
        except Exception as exc:
            last_exc = exc
            if attempt < _max_retries:
                time.sleep(1.5 * (attempt + 1))  # 1.5s, then 3s
                continue
    return 0, {"error": str(last_exc)}


def bridge_slug(institution_name: str, role: str = None) -> str:
    """
    Normalizes an institution (+ optional role) into a stable Cloud
    Bridge address. v2.8.5: a role suffix is appended ONLY when it's
    something other than SECRETARIAT — this keeps every pre-v2.8.5
    address (every institution was implicitly SECRETARIAT-only back
    then) byte-for-byte unchanged, so existing Cloud Bridge folders and
    in-flight messages keep resolving correctly. Only the NEW
    DIRECTEUR/DRH/DAS roles get a distinct address, because they didn't
    exist before this version.
    ⚠️ Still name-only for anything else — two institutions sharing both
    name and role would still collide, same pre-existing limitation as
    local delivery matching.
    """
    base = re.sub(r'[^A-Za-z0-9]+', '_', institution_name.strip().upper()).strip('_')
    role_norm = (role or DEFAULT_ROLE).strip().upper()
    if role_norm != DEFAULT_ROLE:
        base = f"{base}_{role_norm}"
    return base[:80]


def push_to_worker_bridge(cfg: dict, recipient_name: str, recipient_role: str, sender_name: str,
                          sender_role: str, sender_institution_key: str, subject: str,
                          body: str, tracking: str, attachments: list) -> bool:
    """
    v2.9.5 — Cloudflare Worker Bridge. `attachments` is a list of
    {"bytes": bytes, "original_filename": str}. Replaces push_to_bridge()
    (GitHub) entirely: one POST /send instead of N GitHub PUTs (one file +
    one JSON per attachment) — the Worker accepts the whole message,
    metadata and every attachment's base64 content, in a single call.

    Addressing: both sender and recipient are identified to the Worker by
    bridge_slug(name, role) — the SAME scheme the GitHub Bridge used
    (see bridge_slug's docstring for its one pre-existing limitation,
    unchanged here). sender_institution_key (the REAL institution_key,
    not a slug) travels only as metadata, for route_read_receipt()'s own
    precision routing on the recipient's LOCAL database — it is never
    used to address the Worker itself.
    """
    worker_url, secret = cfg["worker_url"], cfg["device_secret"]
    recipient_id = bridge_slug(recipient_name, recipient_role)
    sender_id = bridge_slug(sender_name, sender_role)

    total_bytes = sum(len(a["bytes"]) for a in attachments)
    if total_bytes > 20 * 1024 * 1024:
        # Workers KV caps a single value at 25 MB; the message is split
        # across several KV entries (one per attachment) so the real
        # ceiling is per-FILE, not per-message — but a generous combined
        # guard here fails fast with a clear reason instead of a vague
        # Worker-side 413 on whichever attachment happens to push it over.
        return False

    payload = {
        "sender_institution_id": sender_id,
        "secret_key": secret,
        "recipient_institution_id": recipient_id,
        "recipient_role": recipient_role,
        "sender_institution": sender_name,
        "sender_institution_key": sender_institution_key,  # real key — metadata only, see docstring
        "recipient_institution": recipient_name,
        "subject": subject,
        "body": body,
        "tracking": tracking,
        "attachments": [
            {"file_original_name": att["original_filename"],
             "content_base64": base64.b64encode(att["bytes"]).decode("utf-8")}
            for att in attachments
        ],
    }
    status, _ = _worker_request(worker_url, "POST", "/send", payload)
    return status == 200


def get_lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


# --------------------------------------------------------------------------- #
# One-time legacy migration (pre-v2.3.0 single-tenant data).
#
# If an old flat ~/TASHIL_DATA/tashil.db exists from before the multi-tenant
# change AND no profiles have been registered yet, move it (with its
# archives) into a new profile folder rather than silently orphaning it.
# The migrated profile has no PIN yet — the frontend detects this (pin_set:
# false) and prompts the user to CREATE a PIN on first unlock instead of
# asking them to enter one that was never set.
# --------------------------------------------------------------------------- #
def migrate_legacy_single_tenant_if_needed():
    if not os.path.exists(_LEGACY_DB_PATH):
        return
    if list_profiles():
        return  # already have at least one profile — never auto-migrate again

    try:
        legacy_conn = _open_sqlite_connection(_LEGACY_DB_PATH)
        legacy_profile = legacy_conn.execute(
            "SELECT * FROM profile WHERE id = 1"
        ).fetchone()
    except sqlite3.Error:
        legacy_conn.close()
        return

    if legacy_profile is None:
        legacy_conn.close()
        return

    wilaya_code = legacy_profile["wilaya_code"]
    wilaya_name = legacy_profile["wilaya_name"]
    institution_type = legacy_profile["institution_type"]
    institution_name = legacy_profile["institution_name"]
    serial_key = legacy_profile["serial_key"]
    theme = legacy_profile["theme"] if "theme" in legacy_profile.keys() else "dark"

    key = make_institution_key(wilaya_code, institution_type, institution_name, DEFAULT_ROLE)
    legacy_conn.close()

    # Move (not copy) the legacy db and archive folders into the new location
    shutil.move(_LEGACY_DB_PATH, paths["db"])
    if os.path.isdir(_LEGACY_ARCHIVE_SORTANT):
        shutil.move(_LEGACY_ARCHIVE_SORTANT, paths["sortant"])
    if os.path.isdir(_LEGACY_ARCHIVE_ENTRANT):
        shutil.move(_LEGACY_ARCHIVE_ENTRANT, paths["entrant"])

    with registry_db() as conn:
        conn.execute("""
            INSERT INTO profiles (institution_key, wilaya_code, wilaya_name,
                                   institution_type, institution_name, serial_key,
                                   pin_hash, theme, created_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """, (key, wilaya_code, wilaya_name, institution_type, institution_name,
              serial_key, theme, datetime.now().isoformat()))

    print(f"[migration] Legacy profile '{institution_name}' migrated to profiles/{key}/ "
          f"— a PIN must be set on first unlock.")


migrate_legacy_single_tenant_if_needed()


# --------------------------------------------------------------------------- #
# Active session — single in-memory value (see concurrency note at top).
# --------------------------------------------------------------------------- #
_active_key = None
_active_fernet = None  # Fernet instance derived from the active profile's PIN, or None


def require_active_profile():
    """Returns the active profile's registry row, or None if locked."""
    if _active_key is None:
        return None
    return get_profile_row(_active_key)


def locked_response():
    return jsonify({"error": "Session verrouillée. Veuillez entrer votre code PIN.",
                     "locked": True}), 423


# --------------------------------------------------------------------------- #
# Encryption at rest (v2.7.0) — keyed to the profile's own PIN.
#
# ⚠️ Honesty note, stated plainly (also shown to the user in Paramètres):
# a 4-6 digit PIN has only 10,000–1,000,000 possible values. Even with a
# deliberately slow key-derivation function, this is brute-forceable
# offline by anyone who obtains the encrypted files directly, given
# enough time. This protects against the realistic everyday threat —
# a stolen or borrowed device being casually browsed without the PIN —
# not against a determined, resourced attacker with the encrypted blob
# and time to spend on it.
#
# ⚠️ Scope limitation, also stated plainly: encryption only applies to
# content THIS profile's own unlocked session writes — its own sent
# messages, and anything it receives via the Cloud Bridge while unlocked.
# Same-device LOCAL delivery (v2.4.0) writes directly into a recipient
# profile's storage while that profile is locked — we don't have their
# PIN at that moment, so that content is written in plaintext. This is a
# real, currently-unavoidable gap given the local-delivery design, not an
# oversight; see api_send_message for where this is handled.
#
# Only profiles created from v2.7.0 onward (encryption_salt is not NULL)
# participate at all — existing profiles keep working exactly as before.
# --------------------------------------------------------------------------- #
def generate_encryption_salt() -> str:
    return base64.b64encode(os.urandom(16)).decode("ascii")


def derive_fernet(pin: str, salt_b64: str):
    if not _CRYPTO_AVAILABLE:
        return None
    salt = base64.b64decode(salt_b64)
    kdf = PBKDF2HMAC(algorithm=_crypto_hashes.SHA256(), length=32, salt=salt, iterations=480000)
    derived = kdf.derive(pin.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(derived))


def set_active_session(institution_key: str, pin: str, profile_row: dict = None):
    """Activates a profile's session AND derives/caches its encryption key
    (if it has one) in the same place, so the two can never drift apart."""
    global _active_key, _active_fernet
    _active_key = institution_key
    row = profile_row or get_profile_row(institution_key)
    if row and row.get("encryption_salt"):
        _active_fernet = derive_fernet(pin, row["encryption_salt"])
    else:
        _active_fernet = None


def clear_active_session():
    global _active_key, _active_fernet
    _active_key = None
    _active_fernet = None


def encrypt_text(value: str) -> str:
    if _active_fernet is None or not value:
        return value
    return _active_fernet.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_text(value: str) -> str:
    if _active_fernet is None or not value:
        return value
    try:
        return _active_fernet.decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, Exception):
        return value  # legacy plaintext row, or content this key can't open — degrade, don't crash


def encrypt_file_bytes(data: bytes) -> bytes:
    if _active_fernet is None:
        return data
    return _active_fernet.encrypt(data)


def decrypt_file_bytes(data: bytes) -> bytes:
    if _active_fernet is None:
        return data
    try:
        return _active_fernet.decrypt(data)
    except (InvalidToken, ValueError):
        return data


def decrypt_message_row(row: dict) -> dict:
    """Applied to every message dict before it's ever sent to the frontend."""
    row = dict(row)
    row["subject"] = decrypt_text(row.get("subject") or "")
    row["body"] = decrypt_text(row.get("body") or "")
    return row


def attach_attachment_counts(conn, rows: list) -> list:
    """
    v2.9.4: adds an "attachment_count" field to each message dict, so the
    dashboard/inbox/registre lists can show "📎 N fichiers" and expand to
    the full list only when there's more than one — without every list
    endpoint re-deriving "old vs new message" logic itself (that's
    get_message_attachments()'s job; this is the lightweight COUNT-only
    sibling for list views, which never need the full file list).
    """
    if not rows:
        return rows
    ids = [r["id"] for r in rows]
    placeholders = ",".join("?" * len(ids))
    counted = {r["message_id"]: r["c"] for r in conn.execute(
        f"SELECT message_id, COUNT(*) c FROM message_attachments "
        f"WHERE message_id IN ({placeholders}) GROUP BY message_id", ids
    ).fetchall()}
    for row in rows:
        row["attachment_count"] = counted.get(row["id"], 1 if row.get("file_path") else 0)
    return rows


# --------------------------------------------------------------------------- #
# Page routes
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/manifest.json")
def manifest():
    return send_from_directory(app.static_folder, "manifest.json",
                                mimetype="application/manifest+json")


@app.route("/api/network-qr.png")
def api_network_qr():
    """
    Generates a QR code encoding this device's LAN URL, so a phone can
    open TASHIL by scanning instead of typing an IP address by hand.
    """
    if not _QRCODE_AVAILABLE:
        abort(501)  # Not Implemented — dependency missing on this build
    url = f"http://{get_lan_ip()}:5000/"
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# v2.9.3: static path the TASHIL SCANNER mobile app's .apk is expected at
# — the Android app itself (native Kotlin) is a separate project, not yet
# built; this page is the PC-side landing spot for it, so that dropping a
# future tashil-scanner.apk file in /static/downloads/ "just works" with
# no further backend change.
SCANNER_APK_PATH = os.path.join(app.static_folder, "downloads", "tashil-scanner.apk")


@app.route("/api/scanner/qr.png")
def api_scanner_qr():
    """Same pattern as /api/network-qr.png — a QR encoding this device's
    LAN URL to the APK download route below, so a phone on the same
    Wi-Fi can scan instead of typing anything."""
    if not _QRCODE_AVAILABLE:
        abort(501)
    url = f"http://{get_lan_ip()}:5000/api/scanner/apk"
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/api/scanner/status", methods=["GET"])
def api_scanner_status():
    """Lets the frontend show an honest "pas encore disponible" state
    instead of a QR code / download button that would 404 when scanned
    or clicked, for as long as TASHIL SCANNER (separate Kotlin project)
    hasn't shipped an .apk yet."""
    available = os.path.isfile(SCANNER_APK_PATH)
    return jsonify({
        "available": available,
        "size_bytes": os.path.getsize(SCANNER_APK_PATH) if available else 0,
    })


@app.route("/api/scanner/apk", methods=["GET"])
def api_scanner_apk():
    if not os.path.isfile(SCANNER_APK_PATH):
        return jsonify({"error": "TASHIL SCANNER n'est pas encore disponible sur cet appareil."}), 404
    return send_file(SCANNER_APK_PATH, as_attachment=True, download_name="tashil-scanner.apk",
                      mimetype="application/vnd.android.package-archive")


# --------------------------------------------------------------------------- #
# API — Meta / directories
# --------------------------------------------------------------------------- #
@app.route("/api/meta", methods=["GET"])
def api_meta():
    return jsonify({
        "wilayas": WILAYAS,
        "institution_types": INSTITUTION_TYPES,
        "lan_url": f"http://{get_lan_ip()}:5000/",
        "app_version": APP_VERSION,
        "github_repo": GITHUB_REPO,
        "realtime": socketio is not None,   # v2.9.0: lets the UI pick socket mode vs legacy polling
    })


@app.route("/api/institutions", methods=["GET"])
def api_institutions():
    return jsonify({"institutions": INSTITUTIONS_DIRECTORY})


@app.route("/api/institutions/onboarding", methods=["GET"])
def api_institutions_onboarding():
    wilaya_code = request.args.get("wilaya_code", type=int)
    institution_type = request.args.get("institution_type", "")
    if wilaya_code is None or institution_type not in INSTITUTION_TYPES:
        return jsonify({"error": "Paramètres invalides."}), 400
    return jsonify({"institutions": get_onboarding_institutions(wilaya_code, institution_type)})


# --------------------------------------------------------------------------- #
# API — Session / multi-tenant profile management
# --------------------------------------------------------------------------- #
@app.route("/api/session", methods=["GET"])
def api_session():
    profiles = list_profiles()
    active = require_active_profile()
    return jsonify({
        "first_launch": len(profiles) == 0,
        "profiles": [
            {
                "institution_key": p["institution_key"],
                "institution_name": p["institution_name"],
                "wilaya_name": p["wilaya_name"],
                "institution_type": p["institution_type"],
                "role": p.get("role") or DEFAULT_ROLE,
                "pin_set": p["pin_hash"] is not None,
            }
            for p in profiles
        ],
        "active": profile_public_dict(active) if active else None,
    })


@app.route("/api/session/set-pin", methods=["POST"])
def api_session_set_pin():
    """Used once, for a profile that has no PIN yet (new onboarding, or a
    migrated legacy profile). Refuses to overwrite an existing PIN — use
    the (future) change-PIN flow for that, this endpoint is creation-only."""
    data = request.get_json(force=True)
    key = data.get("institution_key", "")
    pin = data.get("pin", "")

    if not re.fullmatch(r"\d{4,6}", pin):
        return jsonify({"error": "Le code PIN doit contenir 4 à 6 chiffres."}), 400

    row = get_profile_row(key)
    if row is None:
        return jsonify({"error": "Établissement introuvable."}), 404
    if row["pin_hash"] is not None:
        return jsonify({"error": "Un code PIN existe déjà pour ce profil."}), 400

    # A profile getting its first-ever PIN (migrated legacy profile) also
    # opts into encryption at rest from this point forward — old plaintext
    # rows/files stay readable (decrypt_text/decrypt_file_bytes fall back
    # gracefully when content isn't actually encrypted), new ones get
    # encrypted going forward.
    salt = generate_encryption_salt()
    with registry_db() as conn:
        conn.execute(
            "UPDATE profiles SET pin_hash = ?, encryption_salt = ? WHERE institution_key = ?",
            (generate_password_hash(pin), salt, key)
        )

    updated_row = get_profile_row(key)
    set_active_session(key, pin, updated_row)
    return jsonify({"ok": True, "profile": profile_public_dict(updated_row)})


def get_hardware_fingerprint() -> str:
    """
    v2.8.5: best-effort hardware identifier for automatic device
    pairing. Tries the Windows motherboard/product UUID first (stable
    across reinstalls, reboots, and even OS reinstalls on the same
    physical machine); falls back to a MAC-address-derived value
    (uuid.getnode()) on any platform where the Windows-specific command
    isn't available or fails — including this Linux development sandbox,
    where the fallback path is the only one ever exercised.

    ⚠️ Honesty note: the Windows path (wmic) could NOT be exercised in
    this sandbox — there is no Windows machine here to run it against.
    The fallback path was tested directly. wmic itself is also
    deprecated by Microsoft in newer Windows builds in favor of
    PowerShell's Get-CimInstance; if pairing behaves unexpectedly on a
    very recent Windows version, this is the first place to check.

    The raw fingerprint is never stored — only its SHA-256 hash (see
    api_session_unlock) — same privacy principle already applied to PINs.
    """
    try:
        if platform.system() == "Windows":
            output = subprocess.check_output(
                ["wmic", "csproduct", "get", "UUID"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode("utf-8", errors="ignore")
            lines = [l.strip() for l in output.splitlines() if l.strip() and "UUID" not in l.upper()]
            if lines and lines[0]:
                return lines[0]
    except Exception:
        pass  # wmic missing/deprecated/blocked — fall through to the generic fallback

    # Generic fallback: derived from the network interface's MAC address.
    # Weaker than a real motherboard UUID (changes if the network adapter
    # changes, and uuid.getnode() can fall back to a random value on some
    # systems if no MAC is readable at all) — documented, not hidden.
    return f"fallback-{uuid.getnode()}"


def hash_hardware_fingerprint(raw_fingerprint: str) -> str:
    return hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()


@app.route("/api/session/unlock", methods=["POST"])
def api_session_unlock():
    data = request.get_json(force=True)
    key = data.get("institution_key", "")
    pin = data.get("pin", "")

    row = get_profile_row(key)
    if row is None:
        return jsonify({"error": "Établissement introuvable."}), 404
    if row["pin_hash"] is None:
        return jsonify({"error": "Aucun code PIN défini pour ce profil.", "pin_not_set": True}), 400

    # v2.8.5: automatic hardware pairing, checked BEFORE the PIN. A
    # profile pairs itself to whatever machine first unlocks it
    # successfully — no manual serial-number entry. Once paired, any
    # OTHER machine attempting to unlock this profile is rejected
    # immediately, regardless of whether the PIN it supplied was
    # correct, so a stolen database file alone is useless without the
    # original paired hardware. Legitimate hardware changes (replacement
    # PC) go through /api/session/recover with the institution's own
    # serial_key, never through this endpoint.
    current_hash = hash_hardware_fingerprint(get_hardware_fingerprint())
    if row["paired_hardware_hash"] is not None and row["paired_hardware_hash"] != current_hash:
        return jsonify({
            "error": "Ce poste n'est pas autorisé pour cet établissement. "
                     "Utilisez la récupération avec la clé série de l'établissement "
                     "si ce poste est un remplacement légitime.",
            "hardware_mismatch": True,
        }), 403

    if not check_password_hash(row["pin_hash"], pin):
        return jsonify({"error": "Code PIN incorrect."}), 401

    if row["paired_hardware_hash"] is None:
        with registry_db() as conn:
            conn.execute("UPDATE profiles SET paired_hardware_hash = ? WHERE institution_key = ?",
                         (current_hash, key))
        row = get_profile_row(key)  # re-read so the returned/cached row reflects the new pairing

    set_active_session(key, pin, row)
    return jsonify({"ok": True, "profile": profile_public_dict(row)})


@app.route("/api/session/recover", methods=["POST"])
def api_session_recover():
    """
    v2.8.5: "Mot de passe oublié" recovery — verifies the INSTITUTION's
    own serial_key (shown to that institution at onboarding, and kept
    centrally in the ILINE TECH reference registry, see
    tools/generate_serial_registry.py) rather than any shared master
    key. Resets the PIN and re-pairs the current machine as this
    profile's authorized hardware — covering both "forgot PIN on the
    same machine" and "legitimate replacement machine" with one flow.

    ⚠️ Told to the user, not hidden: this resets ACCESS, not encrypted
    CONTENT. Changing the PIN changes the Fernet key derived from it
    (see derive_fernet) — any message/file this profile encrypted under
    the OLD PIN becomes permanently unreadable under the new one. This
    is the same tradeoff already documented for encryption at rest since
    v2.7.0, not a new limitation introduced here: a real encryption
    scheme that could be bypassed by a recovery flow wouldn't be real
    encryption. The response says so explicitly.
    """
    data = request.get_json(force=True)
    key = data.get("institution_key", "")
    submitted_serial = data.get("serial_key", "").strip()
    new_pin = data.get("new_pin", "")

    if not re.fullmatch(r"\d{4,6}", new_pin):
        return jsonify({"error": "Le nouveau code PIN doit contenir 4 à 6 chiffres."}), 400

    row = get_profile_row(key)
    if row is None:
        return jsonify({"error": "Établissement introuvable."}), 404

    # Constant-time comparison — this is a credential check, same care
    # as a password compare, even though serial_key isn't itself hashed
    # (it's meant to be looked up from the ILINE TECH registry by an
    # administrator, not memorized like a PIN).
    if not hmac.compare_digest(submitted_serial, row["serial_key"] or ""):
        return jsonify({"error": "Clé série invalide pour cet établissement."}), 401

    current_hash = hash_hardware_fingerprint(get_hardware_fingerprint())
    encryption_warning = row["encryption_salt"] is not None

    with registry_db() as conn:
        conn.execute(
            "UPDATE profiles SET pin_hash = ?, paired_hardware_hash = ? WHERE institution_key = ?",
            (generate_password_hash(new_pin), current_hash, key)
        )

    updated_row = get_profile_row(key)
    set_active_session(key, new_pin, updated_row)
    return jsonify({
        "ok": True,
        "profile": profile_public_dict(updated_row),
        "warning": (
            "Accès réinitialisé et ce poste ré-appairé. Les documents déjà "
            "chiffrés avec l'ancien code PIN restent définitivement "
            "illisibles — c'est le fonctionnement normal d'un vrai "
            "chiffrement, pas une erreur."
        ) if encryption_warning else None,
    })


@app.route("/api/session/lock", methods=["POST"])
def api_session_lock():
    """Locks the workspace (the 'logout' action) WITHOUT deleting any data —
    switching institutions must never show a previous institution's
    archives, but it also must never destroy them."""
    closing_key = _active_key
    clear_active_session()
    _ui_session_closed(closing_key)
    return jsonify({"ok": True})


def _perform_profile_deletion(key_to_delete: str, pin: str):
    """
    Shared by both delete routes below. Permanently deletes ONE profile:
    its isolated database, its entire archive folder (Courrier_Sortant +
    Courrier_Entrant), and its entry in the device's registry. Irreversible
    — requires that profile's OWN PIN as the actual authorization (a
    dismissible confirm() dialog alone is not enough protection for a
    destructive action against real archived documents). Returns a
    (response_dict, status_code) pair; never raises for an expected
    failure (wrong PIN, missing profile).
    """
    profile = get_profile_row(key_to_delete)
    if profile is None:
        return {"error": "Profil introuvable."}, 404
    if profile["pin_hash"] is None or not check_password_hash(profile["pin_hash"], pin):
        return {"error": "Code PIN incorrect."}, 401

    paths = profile_paths(key_to_delete)

    # Lock immediately if this happened to be the active session — no
    # further access to this profile from this point on, regardless of
    # whether file cleanup below fully succeeds.
    if _active_key == key_to_delete:
        clear_active_session()
        _ui_session_closed(key_to_delete)

    with registry_db() as conn:
        conn.execute("DELETE FROM profiles WHERE institution_key = ?", (key_to_delete,))

    try:
        if os.path.isdir(paths["folder"]):
            shutil.rmtree(paths["folder"])
    except OSError as exc:
        # The profile is already gone from the picker either way (registry
        # entry removed above) — but tell the user plainly if some files
        # couldn't be removed (e.g. one was open in another program),
        # rather than silently leaving orphaned data on disk unmentioned.
        return {
            "ok": True,
            "warning": f"Le profil a été retiré, mais certains fichiers n'ont pas pu être "
                       f"supprimés automatiquement ({exc}). Vous pouvez les supprimer "
                       f"manuellement dans le dossier de l'application si besoin."
        }, 200

    return {"ok": True}, 200


@app.route("/api/profile/delete", methods=["POST"])
def api_delete_profile():
    """Deletes the CURRENTLY ACTIVE (unlocked) profile — the existing
    "Zone dangereuse" flow in Paramètres. See _perform_profile_deletion."""
    if _active_key is None:
        return locked_response()
    data = request.get_json(force=True)
    body, status = _perform_profile_deletion(_active_key, data.get("pin", ""))
    return jsonify(body), status


@app.route("/api/profile/delete-locked", methods=["POST"])
def api_delete_profile_locked():
    """
    v2.9.2: deletes a profile picked from the LOCK-SCREEN establishment
    list, WITHOUT ever unlocking it into an active session first — the PIN
    entered here is checked directly against that profile's own stored
    hash and never activates its session or its encryption key. This is
    the same irreversible deletion as /api/profile/delete, just reachable
    one step earlier in the flow (the account picker, before a PIN would
    normally grant access), for cleaning up a test or obsolete
    establishment without first having to unlock it.
    ⚠️ Deliberately available while every profile is locked — a device
    with no active session must still be able to reach this screen.
    """
    data = request.get_json(force=True)
    key_to_delete = data.get("institution_key", "").strip()
    if not key_to_delete:
        return jsonify({"error": "Établissement non spécifié."}), 400
    body, status = _perform_profile_deletion(key_to_delete, data.get("pin", ""))
    return jsonify(body), status


# --------------------------------------------------------------------------- #
# API — Profile creation (onboarding)
# --------------------------------------------------------------------------- #
@app.route("/api/profile", methods=["POST"])
def api_save_profile():
    data = request.get_json(force=True)
    wilaya_code = int(data.get("wilaya_code"))
    institution_type = data.get("institution_type", "").strip()
    institution_name = data.get("institution_name", "").strip()
    requested_role = data.get("role", DEFAULT_ROLE).strip().upper() or DEFAULT_ROLE
    pin = data.get("pin", "")
    # v2.9.5: field renamed from original_pin (v2.9.3's PIN-based check) —
    # this is now a Worker device secret, not the local encryption PIN.
    # Only needed if the establishment is already claimed elsewhere.
    original_secret_key = data.get("original_secret_key", "")

    if not institution_name or institution_type not in INSTITUTION_TYPES:
        return jsonify({"error": "Champs invalides."}), 400
    if not re.fullmatch(r"\d{4,6}", pin):
        return jsonify({"error": "Le code PIN doit contenir 4 à 6 chiffres."}), 400

    wilaya_name = dict(WILAYAS).get(wilaya_code)
    if wilaya_name is None:
        return jsonify({"error": "Wilaya invalide."}), 400

    # v2.8.5/6: the server is the actual authority on which role is
    # valid — never trust a frontend lock alone. institution_name now
    # matters too: a polyclinic NAME under an EPSP is locked to
    # SECRETARIAT_POLYCLINIQUE regardless of what the client submitted,
    # even though its institution_type is "EPSP" like its head office.
    valid_roles = allowed_roles(institution_type, institution_name)
    role = requested_role if requested_role in valid_roles else valid_roles[0]

    key = make_institution_key(wilaya_code, institution_type, institution_name, role)
    serial_key = generate_serial_key(wilaya_code, institution_type, institution_name, role)
    salt = generate_encryption_salt()

    # v2.9.3, check 1/2 — LOCAL: this device's own registry.db already has
    # institution_key as a PRIMARY KEY, so a second local attempt would
    # otherwise surface as a raw, unfriendly sqlite3.IntegrityError.
    if get_profile_row(key) is not None:
        return jsonify({"error": "Cet établissement (avec ce rôle) est déjà configuré sur cet appareil. "
                                  "Sélectionnez-le depuis l'écran de verrouillage plutôt que d'en recréer un."}), 409

    # v2.9.5, check 2/2 — NETWORK-WIDE: institution_key is deterministic,
    # so a SECOND, DIFFERENT device could otherwise freely create its own
    # independent profile addressed the same way on the Worker Bridge —
    # corrupting delivery, which assumes bridge_slug(name, role)
    # identifies one establishment on the whole network. Enforced by the
    # Worker's own /register (see the Worker script's device-binding
    # section): this device's own secret is tried first; a 401 means the
    # Worker already has a DIFFERENT secret bound to this institution_id,
    # and the ORIGINAL device's secret must be supplied here to authorize
    # this additional one.
    # ⚠️ Honest limitation, same shape as the GitHub-era one it replaces:
    # without a Worker URL configured on THIS device yet (true for the
    # very first profile ever onboarded on a brand-new install —
    # provisioning normally happens afterwards, in Paramètres), there is
    # nothing to check against at this exact moment;
    # _ensure_worker_registration() closes that gap retroactively on the
    # first heartbeat once the Worker does get configured.
    cfg = get_bridge_config()
    adopted_secret = None
    if cfg and cfg["enabled"]:
        worker_id = bridge_slug(institution_name, role)
        status, resp = _worker_request(cfg["worker_url"], "POST", "/register", {
            "institution_id": worker_id, "secret_key": cfg["device_secret"],
            "hardware_id": get_hardware_fingerprint(),
        })
        if status == 401:
            if not original_secret_key:
                return jsonify({
                    "error": "Cet établissement est déjà enregistré sur le réseau TASHIL, sur un autre "
                             "appareil. Saisissez sa clé secrète d'origine (visible dans Paramètres sur "
                             "cet autre appareil) pour autoriser cet appareil supplémentaire.",
                    "requires_original_pin": True,
                }), 409
            retry_status, _ = _worker_request(cfg["worker_url"], "POST", "/register", {
                "institution_id": worker_id, "secret_key": original_secret_key,
                "hardware_id": get_hardware_fingerprint(),
            })
            if retry_status != 200:
                return jsonify({
                    "error": "Clé secrète d'origine incorrecte.",
                    "requires_original_pin": True,
                }), 401
            # Correct original secret: this device is now authorized for
            # this establishment's identity — it ADOPTS that secret as
            # its own device_secret going forward (see adopt_device_secret()
            # docstring), so every future Worker call from this device
            # (any institution it hosts) authenticates with it.
            adopted_secret = original_secret_key
        elif status != 200:
            return jsonify({"error": f"Impossible de vérifier le registre réseau (erreur Worker {status}). "
                                      f"Réessayez, ou vérifiez la connexion Internet."}), 502

    with registry_db() as conn:
        conn.execute("""
            INSERT INTO profiles (institution_key, wilaya_code, wilaya_name,
                                   institution_type, institution_name, serial_key,
                                   pin_hash, theme, encryption_salt, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'dark', ?, ?, ?)
        """, (key, wilaya_code, wilaya_name, institution_type, institution_name,
              serial_key, generate_password_hash(pin), salt, role, datetime.now().isoformat()))

    # Ensure the isolated storage folder + schema exist immediately
    with profile_db(key):
        pass

    # v2.9.5: an original_secret_key just confirmed correct above means
    # THIS device adopts it as its own standing Worker credential, so
    # every future call (this institution and any other hosted on this
    # device) authenticates consistently with it from now on.
    if adopted_secret:
        adopt_device_secret(adopted_secret)
        cfg = {**cfg, "device_secret": adopted_secret}
    if cfg and cfg["enabled"]:
        # Registration already succeeded above (either on the first try
        # with this device's own secret, or on retry with the adopted
        # one) — mark it so the heartbeat loop's catch-up doesn't
        # needlessly re-call /register for this profile.
        with registry_db() as conn:
            conn.execute("UPDATE profiles SET worker_registered = 1 WHERE institution_key = ?", (key,))

    updated_row = get_profile_row(key)
    set_active_session(key, pin, updated_row)
    return jsonify({"ok": True, "profile": profile_public_dict(updated_row)})


@app.route("/api/roles", methods=["GET"])
def api_roles():
    """v2.8.5/6: lets the onboarding form ask the server which roles are
    valid for a given institution type (+ name, since a polyclinic NAME
    under an EPSP has a different role set than the EPSP head office
    itself), rather than duplicating ROLE_RULES in JavaScript."""
    institution_type = request.args.get("institution_type", "")
    institution_name = request.args.get("institution_name", "") or None
    if institution_type not in INSTITUTION_TYPES:
        return jsonify({"error": "Type d'établissement invalide."}), 400
    roles = allowed_roles(institution_type, institution_name)
    return jsonify({"roles": roles, "locked": len(roles) == 1})


@app.route("/api/profile/theme", methods=["POST"])
def api_set_theme():
    if _active_key is None:
        return locked_response()
    data = request.get_json(force=True)
    theme = data.get("theme", "dark")
    if theme not in ("dark", "light"):
        return jsonify({"error": "Thème invalide."}), 400
    with registry_db() as conn:
        conn.execute("UPDATE profiles SET theme = ? WHERE institution_key = ?", (theme, _active_key))
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- #
# API — Dashboard (scoped to the active profile)
# --------------------------------------------------------------------------- #
@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    if _active_key is None:
        return locked_response()
    with profile_db(_active_key, commit=False) as conn:
        sent = conn.execute("SELECT COUNT(*) c FROM messages WHERE direction='sortant'").fetchone()["c"]
        received = conn.execute("SELECT COUNT(*) c FROM messages WHERE direction='entrant'").fetchone()["c"]
        # "En attente" = sent but not yet acknowledged by the recipient. Note:
        # previously this counted status='en_attente', a value nothing ever
        # actually inserted (every outgoing message is written with status
        # 'envoye') — so this counter silently showed 0 always. Redefined here
        # to mean what the dashboard label actually implies: outgoing messages
        # still awaiting an accusé de réception. total_sent stays an honest
        # all-time count regardless of acknowledgement state.
        pending = conn.execute(
            "SELECT COUNT(*) c FROM messages WHERE direction='sortant' AND status != 'accuse'"
        ).fetchone()["c"]
        recent = conn.execute("SELECT * FROM messages ORDER BY created_at DESC LIMIT 15").fetchall()
        recent = attach_attachment_counts(conn, [decrypt_message_row(r) for r in recent])

    return jsonify({
        "total_sent": sent,
        "total_received": received,
        "pending": pending,
        "recent": recent,
    })


# --------------------------------------------------------------------------- #
# API — Messaging (scoped to the active profile)
# --------------------------------------------------------------------------- #
@app.route("/api/messages", methods=["GET"])
def api_list_messages():
    if _active_key is None:
        return locked_response()
    direction = request.args.get("direction", "sortant")
    with profile_db(_active_key, commit=False) as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE direction = ? ORDER BY created_at DESC",
            (direction,)
        ).fetchall()
        rows = attach_attachment_counts(conn, [decrypt_message_row(r) for r in rows])

    # v2.8.4: consulting the inbox marks its unread entrant messages as
    # read — this is what actually clears the desktop system-tray badge
    # counter (see /api/messages/unread-count and desktop_launcher.py).
    # Deliberately a SEPARATE short connection, opened only after the
    # read-only SELECT above has already closed — same "never hold a
    # connection open longer than one clear step" pattern as the rest of
    # this file since the v2.8.1 SQLite fix.
    if direction == "entrant":
        with profile_db(_active_key) as conn:
            conn.execute("UPDATE messages SET is_read = 1 WHERE direction = 'entrant' AND is_read = 0")

    return jsonify({"messages": rows})


@app.route("/api/messages/unread-count", methods=["GET"])
def api_unread_count():
    """
    v2.8.4: how many received messages the active profile hasn't opened
    the inbox to see yet. Polled by desktop_launcher.py's background
    thread to drive the Windows system-tray badge and toast
    notifications — this endpoint itself has no OS-specific code in it,
    it's a plain count any client could poll.
    """
    if _active_key is None:
        return locked_response()
    with profile_db(_active_key, commit=False) as conn:
        count = conn.execute(
            "SELECT COUNT(*) c FROM messages WHERE direction = 'entrant' AND is_read = 0"
        ).fetchone()["c"]
    return jsonify({"unread": count})


@app.route("/api/messages/send", methods=["POST"])
def api_send_message():
    if _active_key is None:
        return locked_response()

    recipient = request.form.get("recipient", "").strip()
    # v2.8.5: two-level send form — Établissement -> Service. Left blank,
    # every send is routed to SECRETARIAT by default, matching the spec's
    # "si non spécifié, le courrier est orienté vers le SECRETARIAT".
    recipient_role = (request.form.get("service", "") or "").strip().upper() or DEFAULT_ROLE
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()
    # v2.9.4: multiple attachments — getlist("file") returns every file
    # under that field name; the frontend's <input multiple> appends them
    # all under the same "file" key, exactly like a single-file form did
    # before, so this is backward compatible with that older form too
    # (one file -> a list of one).
    uploaded_files = [f for f in request.files.getlist("file") if f and f.filename]

    if not recipient:
        return jsonify({"error": "Institution destinataire requise."}), 400
    if not uploaded_files:
        return jsonify({"error": "Au moins un fichier est requis."}), 400

    profile = get_profile_row(_active_key)
    sender = profile["institution_name"] if profile else "TASHIL"
    paths = profile_paths(_active_key)

    # v2.9.4: archive + validate EVERY file first, before touching the
    # database at all — if any one of them is empty/invalid, the whole
    # send fails cleanly with nothing partially written, same spirit as
    # the single-file v2.8.3 empty-upload check this replaces.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = sanitize(sender).replace(" ", "")[:30]
    archived_attachments = []  # [{"original_filename", "archived_path", "bytes"}, ...]
    for idx, file in enumerate(uploaded_files):
        # Read the original plaintext bytes ONCE. Only the SENDER's own
        # archived copy gets encrypted below, with the sender's own key —
        # any copy handed to a different security domain (local delivery,
        # Cloud Bridge) must use these original bytes, never the sender's
        # encrypted file, which a recipient has no way to decrypt
        # (different key/PIN).
        original_bytes = file.read()
        if not original_bytes:
            return jsonify({"error": f"Le fichier « {file.filename} » est vide (0 octet) — "
                                      f"l'envoi a probablement été interrompu. Réessayez."}), 400

        # v2.8.3: correct the filename's extension to match the file's
        # REAL bytes (magic-byte signature) rather than blindly trusting
        # whatever extension the client sent — see sniff_real_extension()
        # docstring. Safety net only, not the HEIC fix itself (frontend's
        # job, see normalizeImageForUpload) — just prevents a mislabeled
        # file from reaching a recipient under a name that lies about its
        # real format.
        original_filename = file.filename or "document"
        name_root, current_ext = os.path.splitext(original_filename)
        real_ext = sniff_real_extension(original_bytes, current_ext.lower())
        if real_ext != current_ext.lower():
            original_filename = f"{name_root}{real_ext}"

        safe_name = sanitize(secure_filename(original_filename) or "document")
        # idx suffix keeps archived filenames distinct when several
        # attachments in the same message happen to share a name.
        archived_name = f"{ts}_{tag}_{idx}_{safe_name}" if idx else f"{ts}_{tag}_{safe_name}"
        archived_path = os.path.join(paths["sortant"], archived_name)
        with open(archived_path, "wb") as f:
            f.write(encrypt_file_bytes(original_bytes))

        archived_attachments.append({
            "original_filename": original_filename,
            "archived_path": archived_path,
            "bytes": original_bytes,
        })

    # Short, isolated connection: open, write, commit, close — never held
    # open across the network calls (local-delivery file copy, Cloud
    # Bridge push) that happen further down in this route. This is the
    # crux of the "database is locked" fix: a slow network call must
    # never happen while a SQLite write transaction is still open,
    # because that's exactly the window where the background Cloud
    # Bridge poll (or heartbeat) can collide with it.
    first = archived_attachments[0]
    with profile_db(_active_key) as conn:
        conn.execute("BEGIN IMMEDIATE")  # v2.9.0: SELECT (tracking) then INSERT -> take the write lock first
        # v2.8.2: defense in depth on top of next_tracking_number()'s own
        # existence check — if two sends somehow land on the exact same
        # microsecond-scale race and still produce the same candidate
        # (never observed, but not worth assuming impossible), retry with
        # a freshly generated number instead of failing the whole send.
        for attempt in range(3):
            tracking = next_tracking_number(conn, "sortant", _active_key)
            try:
                cur = conn.execute("""
                    INSERT INTO messages (direction, tracking_number, sender_institution,
                                           recipient_institution, subject, body, file_path,
                                           file_original_name, status, delivery_method, created_at)
                    VALUES ('sortant', ?, ?, ?, ?, ?, ?, ?, 'envoye', NULL, ?)
                """, (tracking, sender, recipient, encrypt_text(subject), encrypt_text(body),
                      first["archived_path"], first["original_filename"], datetime.now().isoformat()))
                break
            except sqlite3.IntegrityError:
                if attempt == 2:
                    raise
                continue
        # v2.9.4: one message_attachments row per file, INCLUDING the
        # first — see get_message_attachments()'s docstring on why the
        # legacy messages.file_path column above only ever mirrors it.
        new_message_id = cur.lastrowid
        for order, att in enumerate(archived_attachments):
            conn.execute(
                "INSERT INTO message_attachments (message_id, file_path, file_original_name, sort_order) "
                "VALUES (?, ?, ?, ?)",
                (new_message_id, att["archived_path"], att["original_filename"], order)
            )

    # --------------------------------------------------------------- #
    # Local delivery: if the recipient happens to be another profile
    # registered on THIS SAME DEVICE, actually deliver the message into
    # its inbox (own isolated database + archive). This does NOT reach
    # a different computer on the network — that is a separate feature
    # (LAN push / Cloud Bridge) not yet built. See STATE.md.
    # --------------------------------------------------------------- #
    delivered_locally = False
    recipient_profile = find_local_profile_by_recipient(recipient, recipient_role, exclude_key=_active_key)
    if recipient_profile is not None:
        try:
            recipient_key = recipient_profile["institution_key"]
            recipient_paths = profile_paths(recipient_key)

            # v2.9.4: copy EVERY attachment's original (plaintext) bytes
            # into the recipient's own archive folder. Plaintext,
            # deliberately — see the encryption scope limitation
            # documented above set_active_session(): we don't have the
            # recipient's PIN/key at this point (they're locked), so we
            # cannot encrypt on their behalf.
            recipient_attachments = []
            for att in archived_attachments:
                recipient_archived_path = os.path.join(
                    recipient_paths["entrant"], os.path.basename(att["archived_path"]))
                with open(recipient_archived_path, "wb") as f:
                    f.write(att["bytes"])
                recipient_attachments.append({
                    "archived_path": recipient_archived_path,
                    "original_filename": att["original_filename"],
                })
            recipient_first = recipient_attachments[0]

            recipient_tracking = tracking
            try:
                with profile_db(recipient_key) as recipient_conn:
                    recipient_conn.execute("BEGIN IMMEDIATE")
                    rcur = recipient_conn.execute("""
                        INSERT INTO messages (direction, tracking_number, sender_institution,
                                               recipient_institution, subject, body, file_path,
                                               file_original_name, status, delivery_method, is_read,
                                               sender_institution_key, created_at)
                        VALUES ('entrant', ?, ?, ?, ?, ?, ?, ?, 'envoye', 'local', 0, ?, ?)
                    """, (recipient_tracking, sender, recipient, subject, body,
                          recipient_first["archived_path"], recipient_first["original_filename"],
                          _active_key, datetime.now().isoformat()))
                    recipient_message_id = rcur.lastrowid
                    for order, att in enumerate(recipient_attachments):
                        recipient_conn.execute(
                            "INSERT INTO message_attachments (message_id, file_path, file_original_name, sort_order) "
                            "VALUES (?, ?, ?, ?)",
                            (recipient_message_id, att["archived_path"], att["original_filename"], order)
                        )
            except sqlite3.IntegrityError:
                # Extremely rare tracking-number collision across two
                # independent institution databases — disambiguate and retry.
                recipient_tracking = f"{tracking}-{uuid.uuid4().hex[:4].upper()}"
                with profile_db(recipient_key) as recipient_conn:
                    recipient_conn.execute("BEGIN IMMEDIATE")
                    rcur = recipient_conn.execute("""
                        INSERT INTO messages (direction, tracking_number, sender_institution,
                                               recipient_institution, subject, body, file_path,
                                               file_original_name, status, delivery_method, is_read,
                                               sender_institution_key, created_at)
                        VALUES ('entrant', ?, ?, ?, ?, ?, ?, ?, 'envoye', 'local', 0, ?, ?)
                    """, (recipient_tracking, sender, recipient, subject, body,
                          recipient_first["archived_path"], recipient_first["original_filename"],
                          _active_key, datetime.now().isoformat()))
                    recipient_message_id = rcur.lastrowid
                    for order, att in enumerate(recipient_attachments):
                        recipient_conn.execute(
                            "INSERT INTO message_attachments (message_id, file_path, file_original_name, sort_order) "
                            "VALUES (?, ?, ?, ?)",
                            (recipient_message_id, att["archived_path"], att["original_filename"], order)
                        )
            delivered_locally = True
        except Exception:
            # Never fail the whole send just because local delivery hit an
            # issue — the sender's own record above is already saved.
            delivered_locally = False

    # --------------------------------------------------------------- #
    # Cloud Bridge fallback: only attempted when no local profile matched
    # (a local match always takes precedence — see find_local_profile_by_name
    # docstring). Never fails the overall send; the sender's own record is
    # already safely saved regardless of bridge outcome. Note the GitHub
    # network call happens here with NO SQLite connection open at all.
    # --------------------------------------------------------------- #
    delivered_via_bridge = False
    bridge_attempted = False
    if not delivered_locally:
        bridge_cfg = get_bridge_config()
        if bridge_cfg and bridge_cfg["enabled"]:
            bridge_attempted = True
            try:
                delivered_via_bridge = push_to_worker_bridge(
                    bridge_cfg, recipient, recipient_role, sender, profile["role"] if profile else DEFAULT_ROLE,
                    _active_key, subject, body, tracking,
                    [{"bytes": att["bytes"], "original_filename": att["original_filename"]}
                     for att in archived_attachments]
                )
            except Exception:
                delivered_via_bridge = False

            if not delivered_via_bridge:
                # v2.8.9: "Erreur GitHub (0)" and other transient network
                # failures no longer leave this document permanently
                # stuck "En attente" with no further attempt — it's
                # queued for automatic retry on the next poll cycle
                # (~20s later), reading the archived file(s) fresh from
                # disk at retry time rather than duplicating their bytes
                # into the queue now. v2.9.4: "attachments" (plural, a
                # list of {file_path, file_original_name}) replaces the
                # old singular file_path/file_original_name pair —
                # _retry_pending_message_push() reads this new shape.
                with profile_db(_active_key) as queue_conn:
                    _queue_pending_push(queue_conn, "message", {
                        "recipient": recipient,
                        "recipient_role": recipient_role,
                        "sender": sender,
                        "sender_role": profile["role"] if profile else DEFAULT_ROLE,
                        "sender_institution_key": _active_key,
                        "subject": subject,
                        "body": body,
                        "tracking": tracking,
                        "attachments": [{"file_path": att["archived_path"],
                                          "file_original_name": att["original_filename"]}
                                         for att in archived_attachments],
                    })

    delivery_method = "local" if delivered_locally else ("bridge" if delivered_via_bridge else None)
    if delivery_method:
        with profile_db(_active_key) as method_conn:
            method_conn.execute("UPDATE messages SET delivery_method = ? WHERE tracking_number = ?",
                                 (delivery_method, tracking))

    return jsonify({
        "ok": True,
        "tracking_number": tracking,
        "delivered_locally": delivered_locally,
        "recipient_has_local_profile": recipient_profile is not None,
        "bridge_attempted": bridge_attempted,
        "delivered_via_bridge": delivered_via_bridge,
    })


@app.route("/api/messages/<int:message_id>/download", methods=["GET"])
def api_download_message(message_id):
    if _active_key is None:
        return locked_response()
    with profile_db(_active_key, commit=False) as conn:
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            abort(404)
        attachments = get_message_attachments(conn, row)

    # v2.9.4: ?attachment=<id> picks WHICH file, for a message with
    # several — attachment_id 0 is always either the legacy single-file
    # column (old messages) or the first upload (new messages), so an
    # OLD link/bookmark with no ?attachment= at all keeps working exactly
    # as before, unchanged.
    requested_id = request.args.get("attachment", type=int, default=None)
    chosen = None
    for att in attachments:
        if requested_id is None or att["attachment_id"] == requested_id:
            chosen = att
            break
    if chosen is None or not os.path.exists(chosen["file_path"]):
        abort(404)

    # decrypt_file_bytes is safe to call unconditionally: files written by
    # local delivery (a different security domain — see api_send_message)
    # are genuinely plaintext, and Fernet.decrypt() on non-Fernet bytes
    # raises InvalidToken, which decrypt_file_bytes catches and returns
    # the original bytes unchanged. The ciphertext format itself is the
    # only "is this encrypted" flag needed — no separate per-file marker.
    with open(chosen["file_path"], "rb") as f:
        raw = f.read()
    plaintext = decrypt_file_bytes(raw)

    # v2.9.1: ?inline=1 serves the SAME bytes for the in-app preview modal
    # (PDF.js / mammoth.js / <img>) instead of forcing a download — same
    # decryption, same access check, just a different Content-Disposition
    # and a real mimetype guess so the browser renders it instead of
    # saving it.
    inline = request.args.get("inline") == "1"
    guessed_type, _ = mimetypes.guess_type(chosen["file_original_name"] or "")
    return send_file(BytesIO(plaintext), as_attachment=not inline,
                      download_name=chosen["file_original_name"] or "document",
                      mimetype=guessed_type if inline else None)


@app.route("/api/messages/<int:message_id>/attachments", methods=["GET"])
def api_message_attachments(message_id):
    """v2.9.4: lists a message's attachments (id + filename), so the
    frontend can render one 👁️/📥 pair per file instead of assuming
    there is exactly one."""
    if _active_key is None:
        return locked_response()
    with profile_db(_active_key, commit=False) as conn:
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            return jsonify({"error": "Message introuvable."}), 404
        attachments = get_message_attachments(conn, row)
    return jsonify({"attachments": [
        {"attachment_id": a["attachment_id"], "file_original_name": a["file_original_name"]}
        for a in attachments
    ]})


@app.route("/api/messages/<int:message_id>/status", methods=["POST"])
def api_update_message_status(message_id):
    if _active_key is None:
        return locked_response()
    data = request.get_json(force=True)
    status = data.get("status", "").strip()
    if status not in ("envoye", "recu", "accuse", "en_attente"):
        return jsonify({"error": "Statut invalide."}), 400

    with profile_db(_active_key) as conn:
        conn.execute("BEGIN IMMEDIATE")  # v2.9.0: SELECT then UPDATE
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            return jsonify({"error": "Message introuvable."}), 404

        conn.execute("UPDATE messages SET status = ? WHERE id = ?", (status, message_id))
        updated = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        updated = decrypt_message_row(updated)
        row_dict = dict(row)

    # Read-receipt routing happens AFTER the connection above is closed —
    # it opens its own short-lived connection(s) to a *different* profile's
    # database (route_read_receipt), and may make a Cloud Bridge network
    # call. Never do either of those while still holding this connection.
    if status == "accuse" and row_dict["direction"] == "entrant":
        route_read_receipt(row_dict)

    return jsonify({"ok": True, "message": updated})


def route_read_receipt(message_row):
    """
    Notifies the ORIGINAL SENDER that their document was acknowledged —
    instantly if they're a profile on this same device (delivery_method
    == 'local'), or via a small receipt object pushed through the Cloud
    Bridge otherwise. Never raises: a receipt that can't be delivered
    isn't worth failing the accusé action itself over — the requester's
    own local status update already succeeded regardless.

    v2.8.7: prefers the exact sender_institution_key stored on the
    message (added this version) over name-based matching — fixes a
    real bug (STATE.md v2.8.5 §22.9) where a receipt silently failed to
    route back whenever the sender's role wasn't the default one, or
    several role-specific profiles shared that institution name, since
    name-only matching couldn't tell them apart. Falls back to the old
    name-based lookup for messages received before this column existed
    (sender_institution_key is NULL on those).
    """
    tracking = message_row["tracking_number"]
    sender_name = message_row["sender_institution"] or ""
    sender_key = message_row.get("sender_institution_key")
    delivery_method = message_row.get("delivery_method")

    try:
        if delivery_method == "local":
            if sender_key:
                with profile_db(sender_key) as sender_conn:
                    sender_conn.execute(
                        "UPDATE messages SET status = 'accuse' "
                        "WHERE tracking_number = ? AND direction = 'sortant'",
                        (tracking,)
                    )
            else:
                sender_profile = find_local_profile_by_recipient(sender_name, exclude_key=_active_key)
                if sender_profile is not None:
                    with profile_db(sender_profile["institution_key"]) as sender_conn:
                        sender_conn.execute(
                            "UPDATE messages SET status = 'accuse' "
                            "WHERE tracking_number = ? AND direction = 'sortant'",
                            (tracking,)
                        )
        elif delivery_method == "bridge":
            cfg = get_bridge_config()
            if cfg and cfg["enabled"]:
                acknowledger = get_profile_row(_active_key)
                acknowledger_name = acknowledger["institution_name"] if acknowledger else "?"
                own_worker_id = bridge_slug(acknowledger_name, acknowledger["role"] if acknowledger else DEFAULT_ROLE)
                # v2.9.5: sender_worker_id (not the old sender_key/
                # sender_institution_key) is the address the Worker
                # actually understands — see messages.sender_worker_id's
                # own migration comment. NULL for any message imported
                # before this column existed (necessarily a pre-v2.9.5,
                # GitHub-era bridge message) — nothing to route a Worker
                # receipt to for those; push_worker_receipt() still
                # cleans up the accuser's own copy either way.
                sender_worker_id = message_row.get("sender_worker_id")
                receipt_sent = push_worker_receipt(cfg, own_worker_id, tracking, sender_worker_id, acknowledger_name)
                if not receipt_sent:
                    # v2.8.9: same auto-retry treatment as a failed
                    # message send — a transient network failure here
                    # previously meant the accusé silently never made it
                    # back to the sender, with no further attempt ever made.
                    with profile_db(_active_key) as queue_conn:
                        _queue_pending_push(queue_conn, "receipt", {
                            "recipient_own_worker_id": own_worker_id,
                            "sender_worker_id": sender_worker_id,
                            "tracking": tracking,
                            "acknowledger_name": acknowledger_name,
                        })
    except Exception:
        pass  # see docstring — a failed receipt never blocks the accusé itself


def push_worker_receipt(cfg: dict, own_worker_id: str, tracking: str,
                        sender_worker_id: str, acknowledger_name: str) -> bool:
    """
    v2.9.5: one POST /accuse replaces the GitHub-era's separate
    receipt-push — the Worker itself both deletes the ACCUSING device's
    own KV copy of this message (see the module docstring on the new
    "delete on accusé, not on import" lifecycle) and drops a small
    receipt for the sender in the same call. own_worker_id is the
    CURRENTLY ACTIVE profile's own Worker address (bridge_slug of its
    name+role) — its secret authenticates and scopes the deletion to
    only ITS OWN copy. sender_worker_id can be None for a message that
    predates sender_worker_id being recorded (see route_read_receipt) —
    the Worker still deletes the accuser's own copy in that case, it
    just has nowhere to route a receipt to.
    """
    worker_url, secret = cfg["worker_url"], cfg["device_secret"]
    payload = {
        "institution_id": own_worker_id,
        "secret_key": secret,
        "tracking": tracking,
        "sender_institution_id": sender_worker_id,
        "acknowledged_by": acknowledger_name,
    }
    status, _ = _worker_request(worker_url, "POST", "/accuse", payload)
    return status == 200


def _delete_message_and_files(conn, message_id: int) -> bool:
    """Shared by the single and bulk delete routes below. Must be called
    with `conn` already inside a BEGIN IMMEDIATE transaction on the
    caller's own connection. v2.9.4: cleans up EVERY attachment (via
    get_message_attachments — old single-file messages included, not
    just rows that have message_attachments entries), not only a single
    legacy file_path. Returns False if the message doesn't exist."""
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    if row is None:
        return False
    attachments = get_message_attachments(conn, row)
    conn.execute("DELETE FROM message_attachments WHERE message_id = ?", (message_id,))
    conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    for att in attachments:
        if att["file_path"] and os.path.exists(att["file_path"]):
            try:
                os.remove(att["file_path"])
            except OSError:
                pass  # DB record is already gone; a leftover file is not fatal
    return True


@app.route("/api/messages/<int:message_id>", methods=["DELETE"])
def api_delete_message(message_id):
    if _active_key is None:
        return locked_response()
    with profile_db(_active_key) as conn:
        conn.execute("BEGIN IMMEDIATE")  # v2.9.0: SELECT then DELETE
        if not _delete_message_and_files(conn, message_id):
            return jsonify({"error": "Message introuvable."}), 404
    return jsonify({"ok": True})


@app.route("/api/messages/bulk-delete", methods=["POST"])
def api_bulk_delete_messages():
    """
    v2.9.4: Activité Récente's multi-select "Supprimer la sélection".
    Each message is deleted in its OWN short BEGIN IMMEDIATE transaction
    (looping this route's own single-delete helper) rather than one giant
    transaction holding the write lock for the whole batch — same
    short-transaction principle as everywhere else in this file, so a
    large selection never blocks the background Cloud Bridge loop (or a
    concurrent send) for longer than one row at a time.
    """
    if _active_key is None:
        return locked_response()
    data = request.get_json(force=True)
    ids = data.get("ids", [])
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "Aucun document sélectionné."}), 400

    deleted, not_found = 0, 0
    for message_id in ids:
        try:
            message_id = int(message_id)
        except (TypeError, ValueError):
            not_found += 1
            continue
        with profile_db(_active_key) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if _delete_message_and_files(conn, message_id):
                deleted += 1
            else:
                not_found += 1

    return jsonify({"ok": True, "deleted": deleted, "not_found": not_found})


# --------------------------------------------------------------------------- #
# API — Registry (Administration), scoped to the active profile
# --------------------------------------------------------------------------- #
@app.route("/api/registre", methods=["GET"])
def api_registre():
    if _active_key is None:
        return locked_response()
    direction = request.args.get("direction", "tous")
    with profile_db(_active_key, commit=False) as conn:
        if direction == "tous":
            rows = conn.execute("SELECT * FROM messages ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM messages WHERE direction = ? ORDER BY created_at DESC",
                (direction,)
            ).fetchall()
        rows = attach_attachment_counts(conn, [decrypt_message_row(r) for r in rows])
    return jsonify({"entries": rows})


# --------------------------------------------------------------------------- #
# API — Cloud Bridge configuration & manual poll
# --------------------------------------------------------------------------- #
@app.route("/api/bridge/network-test", methods=["GET"])
def api_bridge_network_test():
    """
    Tests reachability of a Worker URL's public /health route — no
    secret_key needed (that route takes none), so this separates "the
    Worker itself is unreachable / wrong URL / blocked by a firewall"
    from "my secret_key is wrong", which otherwise look identical from
    the config form's point of view.

    v2.9.6 bug fix: this previously ONLY ever tested the already-SAVED
    worker_url — so clicking "Tester la connexion" on the setup form,
    which sits above the URL field, before ever clicking "Créer la
    connexion initiale" to save it, always reported "Aucune URL de
    Worker configurée." regardless of what was typed in the box right
    below it (this is what was actually happening in the reported bug —
    not a CORS issue: this whole call is same-origin browser→Flask, and
    the Flask→Worker leg is server-side Python, which CORS, a
    browser-only mechanism, never applies to). An optional ?worker_url=
    query param now lets the frontend test an UNSAVED value typed in the
    form; omitted (or blank), it falls back to the saved config exactly
    as before.
    """
    typed_url = (request.args.get("worker_url") or "").strip().rstrip("/")
    if typed_url:
        worker_url = typed_url
    else:
        cfg = get_bridge_config()
        if not cfg:
            return jsonify({"ok": False, "elapsed_ms": 0, "message": "Aucune URL de Worker configurée.", "hint": ""})
        worker_url = cfg["worker_url"]

    start = time.monotonic()
    status, data = _worker_request(worker_url, "GET", "/health", _max_retries=0)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if status == 200 and data.get("ok"):
        return jsonify({"ok": True, "elapsed_ms": elapsed_ms,
                         "message": "Connexion au Cloudflare Worker Bridge réussie."})

    error_message = data.get("error", f"Statut HTTP {status}" if status else "réseau indisponible")
    hint = ""
    if status == 0:
        hint = ("Worker injoignable — vérifiez l'URL (Paramètres), la connexion Internet de cette "
                "machine, ou un éventuel pare-feu/proxy d'entreprise.")
    elif status == 404:
        hint = "URL jointe mais la route /health répond 404 — vérifiez que c'est bien l'URL du Worker TASHIL."
    return jsonify({"ok": False, "elapsed_ms": elapsed_ms, "message": error_message, "hint": hint})


@app.route("/api/bridge/config", methods=["GET"])
def api_bridge_get_config():
    cfg = get_bridge_config()
    device_secret = ensure_device_secret()  # always generated, even with no worker_url yet (see docstring)
    if cfg is None:
        return jsonify({"configured": False, "enabled": False, "device_secret": device_secret})
    return jsonify({
        "configured": bool(cfg["worker_url"]),
        "enabled": bool(cfg["enabled"]),
        "worker_url": cfg["worker_url"],
        # v2.9.5: unlike the GitHub token, device_secret IS sent back —
        # the person needs to read/copy it to authorize a second device
        # for the same establishment (see api_save_profile's
        # original_secret_key flow). Same threat model as everything
        # else behind an unlocked session: this route already requires
        # one implicitly through the rest of the Paramètres screen.
        "device_secret": device_secret,
    })


def _validate_and_save_worker_config(worker_url: str):
    """
    Shared by both the manual entry form AND the QR/pasted-code import
    path. Returns (status_code, body_dict). Does the (slow) network call
    BEFORE opening any SQLite connection — the write itself is a single
    short INSERT/UPDATE.
    """
    worker_url = (worker_url or "").strip().rstrip("/")
    if not worker_url:
        return 400, {"error": "L'URL du Worker Cloudflare est requise."}
    # http:// is accepted ONLY for localhost/127.0.0.1 — a deliberate
    # allowance for testing against `wrangler dev` (Cloudflare's own
    # local Worker emulator, which serves over plain HTTP), never for a
    # real deployment: every actual Cloudflare Worker URL is HTTPS-only.
    is_local_dev = worker_url.startswith("http://127.0.0.1") or worker_url.startswith("http://localhost")
    if not worker_url.startswith("https://") and not is_local_dev:
        return 400, {"error": "L'URL du Worker doit commencer par https:// "
                               "(http:// n'est accepté que pour 127.0.0.1/localhost, en développement)."}

    status, data = _worker_request(worker_url, "GET", "/health", _max_retries=1)
    if status == 0:
        return 502, {"error": f"Impossible de contacter ce Worker : {data.get('error', 'réseau indisponible')}"}
    if status != 200 or not data.get("ok"):
        return 400, {"error": "Cette URL ne répond pas comme un Worker TASHIL valide "
                               "(la route /health n'a pas répondu correctement)."}

    ensure_device_secret()  # guarantees one exists before this device ever calls the Worker for real
    with registry_db() as conn:
        conn.execute("""
            INSERT INTO bridge_config (id, worker_url, enabled, updated_at)
            VALUES (1, ?, 1, ?)
            ON CONFLICT(id) DO UPDATE SET
                worker_url=excluded.worker_url, enabled=1, updated_at=excluded.updated_at
        """, (worker_url, datetime.now().isoformat()))

    return 200, {"ok": True}


@app.route("/api/bridge/config", methods=["POST"])
def api_bridge_save_config():
    data = request.get_json(force=True)
    status, body = _validate_and_save_worker_config(data.get("worker_url", ""))
    return jsonify(body), status


# --------------------------------------------------------------------------- #
# Provisioning code / QR — lets a SECOND device pick up an ALREADY-VERIFIED
# bridge configuration without anyone retyping owner/repo/token by hand.
#
# ⚠️ This is convenience for TRANSFERRING a real credential between two
# devices you control in person — it does not change the underlying
# security model. The code/QR contains the actual token in the clear
# (base64 is encoding, not encryption); treat a screenshot or photo of it
# exactly like you'd treat the token itself. It is generated only for an
# already-unlocked session that already configured the bridge, and is
# never cached or logged server-side beyond the single response.
# --------------------------------------------------------------------------- #
def build_provisioning_code(cfg: dict) -> str:
    payload = {"worker_url": cfg["worker_url"], "device_secret": cfg["device_secret"]}
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def parse_provisioning_code(code: str) -> dict:
    payload = json.loads(base64.b64decode(code.strip().encode("ascii")).decode("utf-8"))
    if not isinstance(payload, dict) or "device_secret" not in payload:
        raise ValueError("malformed provisioning payload")
    return payload


@app.route("/api/bridge/provisioning-code", methods=["GET"])
def api_bridge_provisioning_code():
    if _active_key is None:
        return locked_response()
    cfg = get_bridge_config()
    if not cfg or not cfg["enabled"]:
        return jsonify({"error": "Le Cloud Bridge n'est pas encore configuré sur cet appareil."}), 400
    return jsonify({"code": build_provisioning_code(cfg)})


@app.route("/api/bridge/provisioning-qr.png", methods=["GET"])
def api_bridge_provisioning_qr():
    if _active_key is None:
        return locked_response()
    if not _QRCODE_AVAILABLE:
        abort(501)
    cfg = get_bridge_config()
    if not cfg or not cfg["enabled"]:
        abort(404)
    img = qrcode.make(build_provisioning_code(cfg))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/api/bridge/decode-qr-image", methods=["POST"])
def api_bridge_decode_qr_image():
    """
    Decodes a QR code from an uploaded image file (drag-and-drop or file
    picker) — for someone who can't use a phone camera or copy/paste text
    directly, e.g. they saved/screenshotted the QR and transferred the
    image file itself. Returns just the decoded text; the frontend feeds
    it into the same /api/bridge/import-code flow as a manually pasted
    code, so the exact same private-repo verification applies either way.

    Uses pyzbar + Pillow rather than OpenCV: an earlier version of this
    endpoint used opencv-python-headless, which imported successfully in
    every local test but failed to import at all in a real built exe
    (confirmed by the user — "Le décodage d'image QR n'est pas disponible
    sur ce build"), with no way to tell why from the generic message
    alone. Pillow is already a proven-working dependency in this exact
    build (the provisioning QR generation feature already uses it
    successfully), and pyzbar is a much smaller, simpler native
    dependency than OpenCV — lower packaging risk. If this import STILL
    fails, _QR_DECODE_IMPORT_ERROR captures the real reason instead of
    another dead-end "not available" message.
    """
    if not _QR_DECODE_AVAILABLE:
        detail = f" (détail technique : {_QR_DECODE_IMPORT_ERROR})" if _QR_DECODE_IMPORT_ERROR else ""
        return jsonify({"error": f"Le décodage d'image QR n'est pas disponible sur ce build.{detail}"}), 501

    file = request.files.get("image")
    if not file or file.filename == "":
        return jsonify({"error": "Aucune image fournie."}), 400

    try:
        from PIL import Image
        img = Image.open(BytesIO(file.read()))
        img = img.convert("RGB")

        results = _zbar_decode(img)
        if not results:
            # Real-world images (screenshots, angled phone photos) can be
            # too small or low-contrast for zbar's finder-pattern detection
            # on the first pass — a simple upscale often resolves it.
            upscaled = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
            results = _zbar_decode(upscaled)

        if not results:
            return jsonify({"error": "Aucun QR code détecté dans cette image. "
                                      "Essayez une image plus nette ou de meilleure résolution."}), 400

        decoded_text = results[0].data.decode("utf-8")
        return jsonify({"code": decoded_text})
    except Exception as exc:
        return jsonify({"error": f"Échec du décodage : {exc}"}), 500


@app.route("/api/bridge/import-code", methods=["POST"])
def api_bridge_import_code():
    data = request.get_json(force=True)
    code = data.get("code", "").strip()
    if not code:
        return jsonify({"error": "Code de provisioning vide."}), 400
    try:
        payload = parse_provisioning_code(code)
    except Exception:
        return jsonify({"error": "Code de provisioning invalide ou corrompu."}), 400

    status, body = _validate_and_save_worker_config(payload.get("worker_url", ""))
    if status == 200 and payload.get("device_secret"):
        # v2.9.5: THE whole point of importing a provisioning code is to
        # adopt the ORIGINATING device's secret — without this, the new
        # device would keep its own independently generated one and every
        # /register it attempts for an establishment the first device
        # already claimed would still hit the same 401 this code was
        # meant to avoid.
        adopt_device_secret(payload["device_secret"])
    return jsonify(body), status


@app.route("/api/bridge/disable", methods=["POST"])
def api_bridge_disable():
    with registry_db() as conn:
        conn.execute("UPDATE bridge_config SET enabled = 0 WHERE id = 1")
    return jsonify({"ok": True})


# v2.9.5: _delete_bridge_entry_or_queue()/_retry_pending_bridge_cleanup()
# (GitHub-era: a DELETE on a consumed message that failed got queued in
# bridge_pending_cleanup for retry) have no Worker equivalent needed —
# messages are deleted synchronously by the Worker itself inside /accuse,
# server-side, and anything never accused at all is still cleaned up on
# its own by MESSAGE_TTL_SECONDS. The bridge_pending_cleanup TABLE is
# left in the schema, unused, rather than risk a destructive DROP.
# --------------------------------------------------------------------------- #
# Auto-retry queue for FAILED OUTGOING pushes (v2.8.9) — a message send or
# a read-receipt whose Cloud Bridge push failed (a transient network blip
# that outlasted _worker_request's own retries). Rather than leaving the
# document stuck "En attente" (orange) forever with no further attempt,
# it's queued here and retried automatically on the next poll cycle
# (~20s later, see the frontend's background timer) — no user action
# needed. v2.9.5: a successful retry needs no separate cleanup step of
# its own — a retried SEND simply reaches the Worker, which stores it
# exactly as a first-try send would have; a retried RECEIPT reaches
# /accuse, which deletes the accuser's own KV copy synchronously, same
# as a first-try accusé.
# --------------------------------------------------------------------------- #
def _queue_pending_push(conn, kind: str, payload: dict):
    conn.execute(
        "INSERT INTO bridge_pending_push (kind, payload, created_at) VALUES (?, ?, ?)",
        (kind, json.dumps(payload), datetime.now().isoformat())
    )


def _flush_pending_pushes(key: str, cfg: dict) -> int:
    """
    Retries every queued push, oldest first (returns how many succeeded).
    v2.9.0: the queue is READ in one short connection, each retry then runs
    its Worker call with NO connection open, and each outcome is written in
    its own short transaction. v2.9.5: `cfg` is the Worker bridge config
    dict, replacing the GitHub owner/repo/token triple.
    """
    with profile_db(key, commit=False) as conn:
        pending = [dict(r) for r in conn.execute("SELECT * FROM bridge_pending_push ORDER BY id ASC").fetchall()]
    flushed = 0
    for row in pending:
        if _active_key != key:      # session locked/switched meanwhile: stop, retry next time
            break
        try:
            payload = json.loads(row["payload"])
        except Exception:
            _db_write(key, "DELETE FROM bridge_pending_push WHERE id = ?", (row["id"],))
            continue  # corrupt queue entry — nothing useful to retry, drop it

        success = False
        if row["kind"] == "message":
            success = _retry_pending_message_push(payload, cfg, key)
        elif row["kind"] == "receipt":
            success = push_worker_receipt(
                cfg, payload["recipient_own_worker_id"], payload["tracking"],
                payload.get("sender_worker_id"), payload["acknowledger_name"]
            )

        if success:
            _db_write(key, "DELETE FROM bridge_pending_push WHERE id = ?", (row["id"],))
            flushed += 1
        else:
            _db_write(key, "UPDATE bridge_pending_push SET attempts = attempts + 1 WHERE id = ?", (row["id"],))
    return flushed


def _retry_pending_message_push(payload: dict, cfg: dict, key: str) -> bool:
    """
    Rebuilds and retries a queued message send. Reads each archived file
    fresh from disk (no duplicated bytes in the queue) and decrypts it with
    the active session key — this only ever runs while that same profile is
    unlocked. v2.9.0: the delivery_method update goes through _db_write on
    the profile `key` (no second connection racing the caller's).
    v2.9.4: payload["attachments"] (a list) replaces the old singular
    payload["file_path"]/["file_original_name"] pair — the old shape is
    still read as a one-item fallback, in case a queue entry written by a
    pre-v2.9.4 build is still sitting here across an upgrade.
    v2.9.5: `cfg` is now the Worker bridge config dict ({worker_url,
    device_secret, enabled}); payload["sender_role"] (added in v2.9.5)
    falls back to DEFAULT_ROLE for any entry queued by a pre-v2.9.5 build.
    """
    attachment_specs = payload.get("attachments") or [
        {"file_path": payload["file_path"], "file_original_name": payload["file_original_name"]}
    ]
    attachments = []
    for spec in attachment_specs:
        try:
            with open(spec["file_path"], "rb") as f:
                raw = f.read()
            attachments.append({"bytes": decrypt_file_bytes(raw),
                                 "original_filename": spec["file_original_name"]})
        except OSError:
            return False  # one archived file missing/moved — nothing complete to retry with

    success = push_to_worker_bridge(
        cfg, payload["recipient"], payload["recipient_role"], payload["sender"],
        payload.get("sender_role", DEFAULT_ROLE), payload.get("sender_institution_key"),
        payload["subject"], payload["body"], payload["tracking"], attachments
    )
    if success:
        _db_write(key, "UPDATE messages SET delivery_method = 'bridge' WHERE tracking_number = ?",
                  (payload["tracking"],))
    return success


# --------------------------------------------------------------------------- #
# "Établissements connectés" (v2.8.0) — presence directory.
# v2.9.5: GET /presence on the Worker replaces the whole GitHub-era
# directory/ folder mechanism — KV's own expirationTtl (90s, set in
# _send_worker_heartbeat) means a device that stops announcing itself
# simply stops appearing in the list, automatically, with nothing for
# TASHIL to track, compare timestamps against, or let the person
# manually clear (see api_bridge_directory below: the v2.9.1 single-
# delete/"Vider la liste" actions have no equivalent anymore — there is
# nothing stale left to clean, by construction).
#
# v2.9.3's network-wide duplicate-registration guard (the
# "registrations/<key>.json" ledger) is likewise superseded entirely by
# the Worker's own /register + device binding (see the Cloudflare Worker
# Bridge section and api_save_profile below) — one mechanism doing the
# same job, not two.
# --------------------------------------------------------------------------- #
def _ensure_worker_registration(cfg: dict, profile: dict):
    """
    v2.9.5: self-healing catch-up, run once per heartbeat cycle — mirrors
    the GitHub-era _ensure_registration_claimed()'s role. Covers a profile
    created before the Worker URL was configured (provisioning normally
    happens in Paramètres, AFTER the first profile is onboarded — nothing
    to register against yet at that exact moment) or a /register call that
    failed at onboarding time (a network hiccup). profiles.worker_registered
    tracks whether THIS device already knows it succeeded, so a healthy
    network doesn't re-call /register every single heartbeat for nothing.
    """
    if profile.get("worker_registered"):
        return
    worker_id = bridge_slug(profile["institution_name"], profile.get("role") or DEFAULT_ROLE)
    status, _ = _worker_request(cfg["worker_url"], "POST", "/register", {
        "institution_id": worker_id, "secret_key": cfg["device_secret"],
        "hardware_id": get_hardware_fingerprint(),
    })
    if status == 200:
        _db_write(profile["institution_key"],
                  "UPDATE profiles SET worker_registered = 1 WHERE institution_key = ?",
                  (profile["institution_key"],))
    # A 401 here means this device's OWN secret doesn't match whatever is
    # already bound to this institution_id on the Worker — nothing to
    # retry automatically (this is exactly the case api_save_profile's
    # original_secret_key flow exists to resolve, once, with the person's
    # help); left unregistered, retried again next heartbeat in case the
    # secret gets adopted correctly in the meantime.


def _send_worker_heartbeat(cfg: dict, profile: dict):
    """v2.9.5: one POST /heartbeat — the Worker sets the 90s KV TTL
    itself (PRESENCE_TTL_SECONDS in the Worker script); nothing for the
    client to manage. Addressed by bridge_slug(name, role), same as
    every other Worker call for this profile."""
    worker_id = bridge_slug(profile["institution_name"], profile.get("role") or DEFAULT_ROLE)
    _worker_request(cfg["worker_url"], "POST", "/heartbeat", {
        "institution_id": worker_id, "secret_key": cfg["device_secret"],
        "display_name": profile["institution_name"],
        "wilaya_name": profile["wilaya_name"], "institution_type": profile["institution_type"],
    })


@app.route("/api/bridge/directory", methods=["GET"])
def api_bridge_directory():
    if _active_key is None:
        return locked_response()
    cfg = get_bridge_config()
    if not cfg or not cfg["enabled"]:
        return jsonify({"bridge_enabled": False, "institutions": []})

    status, data = _worker_request(cfg["worker_url"], "GET", "/presence")
    if status != 200:
        return jsonify({"error": f"Erreur Worker ({status})."}), 502
    records = data.get("institutions", [])

    # v2.9.1: DEDUPLICATION, kept unchanged from the GitHub-era logic —
    # every role/profile at the same institution (DIRECTEUR, DRH, DAS,
    # SECRETARIAT_DIRECTION... each addressed separately — see
    # bridge_slug) still announces its own heartbeat, so the SAME
    # establishment name can appear more than once in the raw /presence
    # list. Grouped here by institution_name: one row per establishment,
    # keeping the MOST RECENT last_seen among its roles.
    #
    # v2.9.5: online/offline filtering itself is GONE — every entry
    # /presence returns is, by construction, within the Worker's own 90s
    # presence TTL (an expired KV key is simply absent from the list),
    # so there is no "online: false" case left to compute; everything
    # shown here is inherently online right now.
    grouped = {}
    for record in records:
        name = record.get("display_name", "?")
        last_seen = datetime.fromisoformat(record["last_seen"])
        if name not in grouped:
            grouped[name] = {
                "institution_name": name,
                "institution_type": record.get("institution_type", ""),
                "wilaya_name": record.get("wilaya_name", ""),
                "last_seen": record["last_seen"],
                "_last_seen_dt": last_seen,
                "entry_count": 0,
            }
        elif last_seen > grouped[name]["_last_seen_dt"]:
            grouped[name]["institution_type"] = record.get("institution_type", "")
            grouped[name]["wilaya_name"] = record.get("wilaya_name", "")
            grouped[name]["last_seen"] = record["last_seen"]
            grouped[name]["_last_seen_dt"] = last_seen
        grouped[name]["entry_count"] += 1

    institutions = [
        {"institution_name": g["institution_name"], "institution_type": g["institution_type"],
         "wilaya_name": g["wilaya_name"], "last_seen": g["last_seen"], "online": True,
         "entry_count": g["entry_count"]}
        for g in grouped.values()
    ]
    institutions.sort(key=lambda i: i["institution_name"])
    return jsonify({"bridge_enabled": True, "institutions": institutions})


# v2.9.5: the v2.9.1 single-delete ("🗑️" per row) and "Vider la liste"
# routes are REMOVED — with the GitHub directory/ folder, a stale entry
# lingered forever until manually deleted; with the Worker's 90s presence
# TTL, nothing lingers in the first place. There is no equivalent action
# left to perform: a listed establishment is, by definition, online right
# now, and anything offline has already vanished on its own. The
# corresponding 🗑️/"Vider la liste" buttons are removed from the
# Établissements view (see templates/index.html and app.js).


# --------------------------------------------------------------------------- #
# v2.9.1 — Diagnostic & Santé du système (Paramètres).
#
# Every check here is READ-ONLY and safe to run at any time, including
# while the Cloud Bridge loop is polling in the background — none of them
# hold a long-lived connection or interfere with an in-progress send.
# --------------------------------------------------------------------------- #
@app.route("/api/health", methods=["GET"])
def api_health():
    """Server & WebSocket status. Deliberately available even while LOCKED
    (a diagnostic screen should work before you can even unlock a profile —
    e.g. to check whether the server process itself is healthy)."""
    return jsonify({
        "ok": True,
        "app_version": APP_VERSION,
        "flask_ok": True,               # this route answering IS the Flask check
        "socketio_available": socketio is not None,
        "socketio_active": socketio is not None,  # threading mode has no separate "started" state to check
        "active_profile": _active_key is not None,
    })


@app.route("/api/diagnostics/sqlite", methods=["GET"])
def api_diagnostics_sqlite():
    """PRAGMA quick_check + on-disk size of the CURRENTLY UNLOCKED profile's
    own database. Deliberately does not touch registry.db or other
    profiles' files — a diagnostic screen should never require exposing
    which OTHER establishments exist on this device."""
    if _active_key is None:
        return locked_response()
    paths = profile_paths(_active_key)
    db_path = paths["db"]
    try:
        size_bytes = os.path.getsize(db_path)
    except OSError:
        size_bytes = 0

    try:
        with profile_db(_active_key, commit=False) as conn:
            result = conn.execute("PRAGMA quick_check;").fetchone()
        quick_check = result[0] if result else "erreur"
        healthy = quick_check == "ok"
    except sqlite3.Error as e:
        quick_check, healthy = str(e), False

    return jsonify({"ok": True, "quick_check": quick_check, "healthy": healthy,
                    "db_size_bytes": size_bytes, "db_path": db_path})


@app.route("/api/diagnostics/bridge-status", methods=["GET"])
def api_diagnostics_bridge_status():
    """
    v2.9.5: replaces the GitHub-era rate-limit display — the Cloudflare
    Worker Bridge has no shared, rationed quota to show, so there is
    nothing equivalent to display a NUMBER for. Instead: a live
    Connecté/Déconnecté check against the Worker's public, unauthenticated
    /health route (no secret_key involved — this checks reachability, not
    credentials, same split as api_bridge_network_test above).
    """
    if _active_key is None:
        return locked_response()
    cfg = get_bridge_config()
    if not cfg or not cfg["enabled"]:
        return jsonify({"ok": True, "bridge_enabled": False, "connected": False})

    status, data = _worker_request(cfg["worker_url"], "GET", "/health", _max_retries=0)
    connected = status == 200 and data.get("ok") is True
    return jsonify({"ok": True, "bridge_enabled": True, "connected": connected,
                    "worker_url": cfg["worker_url"]})


@app.route("/api/maintenance/vacuum", methods=["POST"])
def api_maintenance_vacuum():
    """VACUUM + ANALYZE on the active profile's database only.
    ⚠️ VACUUM cannot run inside a transaction and rewrites the whole file —
    it needs to be the only writer for its duration. It is run on its own
    short-lived connection (not through the profile_db()/BEGIN IMMEDIATE
    helpers used everywhere else in this file, which would conflict with
    it) with the existing 30 s busy_timeout as the only concurrency guard:
    if the background Bridge loop is mid-write, this WAITS up to 30 s
    rather than fail immediately, and reports a clear error if it still
    can't get in. Not fully lock-free by design — VACUUM never is."""
    if _active_key is None:
        return locked_response()
    key = _active_key
    paths = profile_paths(key)
    try:
        size_before = os.path.getsize(paths["db"])
        conn = sqlite3.connect(paths["db"], timeout=DB_TIMEOUT_SECONDS)
        try:
            conn.execute("VACUUM;")
            conn.execute("ANALYZE;")
            conn.commit()
        finally:
            conn.close()
        size_after = os.path.getsize(paths["db"])
    except sqlite3.Error as e:
        return jsonify({"error": f"Échec de l'optimisation : {e}"}), 500

    return jsonify({"ok": True, "size_before_bytes": size_before, "size_after_bytes": size_after,
                    "reclaimed_bytes": max(0, size_before - size_after)})


@app.route("/api/maintenance/clear-cache", methods=["POST"])
def api_maintenance_clear_cache():
    """
    v2.9.5: explicitly LOCAL-only maintenance — purges TASHIL_DATA/tmp/
    (a scratch folder this app itself may write incomplete/temporary
    files into, e.g. an interrupted HEIC->JPEG normalization or QR decode
    temp file) and VACUUMs registry.db (compacts the file on disk — never
    deletes a row; the device-wide list of profiles/bridge_config is
    untouched). Deliberately does NOT touch archives/ or any profile's
    own tashil.db (that is real data, and already has its own dedicated
    "Optimiser la base de données" action for the ACTIVE profile).
    There is nothing left to clean on the Cloudflare side: the Worker
    purges a message's KV entries itself the moment it's accused (see
    the Worker's /accuse), and MESSAGE_TTL_SECONDS is its own automatic
    safety net for anything that never gets accused — neither needs, or
    offers, a client-triggered cleanup call.
    """
    tmp_dir = os.path.join(os.path.expanduser("~"), "TASHIL_DATA", "tmp")
    freed_bytes, removed = 0, 0
    if os.path.isdir(tmp_dir):
        cutoff = time.time() - 3600  # only files idle for over an hour — never touch a file mid-write
        for name in os.listdir(tmp_dir):
            fpath = os.path.join(tmp_dir, name)
            try:
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    freed_bytes += os.path.getsize(fpath)
                    os.remove(fpath)
                    removed += 1
            except OSError:
                continue  # a file that vanished or is locked mid-use — skip, not fatal

    registry_vacuumed = False
    try:
        registry_path = os.path.join(os.path.expanduser("~"), "TASHIL_DATA", "registry.db")
        if os.path.isfile(registry_path):
            conn = sqlite3.connect(registry_path, timeout=DB_TIMEOUT_SECONDS)
            try:
                conn.execute("VACUUM;")
                conn.commit()
            finally:
                conn.close()
            registry_vacuumed = True
    except sqlite3.Error:
        pass  # non-fatal — the tmp purge above already ran and is reported regardless

    return jsonify({"ok": True, "files_removed": removed, "freed_bytes": freed_bytes,
                    "registry_vacuumed": registry_vacuumed})


# --------------------------------------------------------------------------- #
# v2.9.0 — Cloud Bridge poll, now run by a SERVER-SIDE loop + local realtime.
#
# What changed and why:
#  * The poll used to be triggered by the browser every 20 s and held ONE
#    SQLite connection (with an open write transaction after the first
#    INSERT) across dozens of GitHub calls. Any foreground write (send,
#    accusé, delete) then waited on it -> "database is locked".
#    Now: network phases run with NO connection open; every DB step is a
#    short, isolated transaction (BEGIN IMMEDIATE).
#  * The loop runs in a background thread (10 s by default), so it does not
#    depend on the UI being open/visible, and pushes an event to the UI
#    through Flask-SocketIO as soon as something is imported.
#  * Directory listings use ETag (304 = free) and heartbeats are sent every
#    60 s, not on every cycle, to protect the shared GitHub quota.
# ⚠️ Local-first limit, unchanged: the socket only connects this process to
# ITS OWN UI. Delivery between two different PCs still travels through the
# GitHub bridge, so the latency floor is BRIDGE_POLL_SECONDS.
# --------------------------------------------------------------------------- #
BRIDGE_POLL_SECONDS = max(5, int(os.environ.get("TASHIL_BRIDGE_POLL_SECONDS", "10")))
HEARTBEAT_EVERY_SECONDS = 60
_POLL_LOCK = threading.Lock()
_last_heartbeat = {}          # institution_key -> time.monotonic() of last beat
_bridge_loop_started = False


def _emit_ui(key, event: str, payload: dict = None):
    """Notify the UI(s) connected to this profile's room. Never raises."""
    if socketio is None or key is None:
        return
    try:
        socketio.emit(event, payload or {}, to=key)
    except Exception:
        app.logger.exception("socket emit failed (%s)", event)


def _ui_session_closed(key):
    """Called when a profile is locked/deleted: tell its UI, empty its room,
    and drop per-session caches so nothing leaks into the next profile."""
    _last_heartbeat.pop(key, None)
    if socketio is not None and key:
        _emit_ui(key, "session_locked")
        try:
            socketio.close_room(key)
        except Exception:
            pass


if socketio is not None:
    @socketio.on("connect")
    def _on_socket_connect():
        # Always accept: the lock screen must be able to connect. Nothing is
        # delivered until the client joins a room (see below).
        return True

    @socketio.on("join_room")
    def _on_join_room(_data=None):
        # The client NEVER chooses its room: the server derives it from the
        # unlocked profile, otherwise any device on the LAN could subscribe
        # to another service's notifications.
        key = _active_key
        if key is None:
            return {"ok": False, "locked": True}
        for r in list(rooms()):
            if r != request.sid and r != key:
                leave_room(r)
        join_room(key)
        return {"ok": True}


def _session_is(key, fernet) -> bool:
    return _active_key == key and _active_fernet is fernet


def run_bridge_poll(notify: bool = False) -> dict:
    """One poll cycle for the CURRENTLY ACTIVE profile. Safe to call
    repeatedly; a second concurrent call returns {"busy": True}.
    notify=True (background loop) also pushes socket events; the manual
    route passes False because its HTTP response already carries the result."""
    if not _POLL_LOCK.acquire(blocking=False):
        return {"ok": True, "busy": True, "bridge_enabled": True, "new_messages": 0, "receipts": []}
    try:
        return _run_bridge_poll_locked(notify)
    finally:
        _POLL_LOCK.release()


def _run_bridge_poll_locked(notify: bool) -> dict:
    key, fernet = _active_key, _active_fernet   # snapshot: the session can change under us
    if key is None:
        return {"ok": True, "locked": True, "bridge_enabled": False, "new_messages": 0, "receipts": []}

    cfg = get_bridge_config()
    if not cfg or not cfg["enabled"]:
        return {"ok": True, "bridge_enabled": False, "new_messages": 0, "receipts": []}

    profile = get_profile_row(key)
    if profile is None:
        return {"ok": True, "bridge_enabled": False, "new_messages": 0, "receipts": []}
    paths = profile_paths(key)
    own_worker_id = bridge_slug(profile["institution_name"], profile.get("role") or DEFAULT_ROLE)

    # 1) Retry failed outgoing pushes (no connection held during the network call).
    flushed = _flush_pending_pushes(key, cfg)

    # 2) Presence heartbeat + registration catch-up — every
    # HEARTBEAT_EVERY_SECONDS, not every cycle (same cadence as before;
    # the Worker's own 90s presence TTL relies on this staying regular).
    now_m = time.monotonic()
    last = _last_heartbeat.get(key)
    if last is None or now_m - last >= HEARTBEAT_EVERY_SECONDS:
        try:
            _send_worker_heartbeat(cfg, profile)
            _ensure_worker_registration(cfg, profile)
        except Exception:
            pass
        _last_heartbeat[key] = now_m

    # 3) List what is addressed to us — ONE call (GET /poll) returns
    # every pending message's metadata (not attachment content yet).
    # v2.9.5: unlike the GitHub Bridge, a message is NOT removed here on
    # import — it stays in the Worker's KV (within its TTL safety net)
    # until the person explicitly clicks "Accusé" (see route_read_receipt
    # / push_worker_receipt). So /poll can keep returning the SAME
    # message on every cycle until then; the already_have check below is
    # what keeps that from re-importing it locally more than once.
    poll_status, poll_data = _worker_request(
        cfg["worker_url"], "GET", "/poll", query={"institution_id": own_worker_id, "secret_key": cfg["device_secret"]})
    if poll_status != 200:
        return {"error": f"Erreur Worker ({poll_status}).", "error_status": poll_status}

    # 4) Import new messages: network first, then ONE short write each.
    imported = []
    for meta in poll_data.get("messages", []):
        if not _session_is(key, fernet):
            break
        tracking = meta.get("tracking_number")
        if not tracking:
            continue

        with profile_db(key, commit=False) as rconn:
            already_have = rconn.execute(
                "SELECT 1 FROM messages WHERE tracking_number = ?", (tracking,)).fetchone()
        if already_have:
            continue  # already imported in an earlier cycle; still sits in KV until accused

        attachment_specs = meta.get("attachments") or []
        if not attachment_specs:
            continue  # malformed entry with no attachment info at all — nothing to import

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = sanitize(meta.get("sender_institution", "DISTANT")).replace(" ", "")[:30]
        downloaded = []  # [{"local_path", "original_filename"}, ...]
        all_attachments_ok = True
        for a_idx, spec in enumerate(attachment_specs):
            fetch_status, fetch_data = _worker_request(
                cfg["worker_url"], "GET", "/fetch-attachment",
                query={"institution_id": own_worker_id, "secret_key": cfg["device_secret"],
                       "tracking": tracking, "index": a_idx})
            if fetch_status != 200 or "content_base64" not in fetch_data:
                all_attachments_ok = False
                break
            try:
                file_bytes = base64.b64decode(fetch_data["content_base64"])
            except (ValueError, TypeError):
                all_attachments_ok = False
                break

            if not _session_is(key, fernet):   # locked/switched mid-download: never write with the wrong key
                all_attachments_ok = False
                break
            safe_name = sanitize(spec.get("file_original_name", "document"))
            suffix = "" if a_idx == 0 else f"_{a_idx}"
            local_path = os.path.join(paths["entrant"], f"{ts}_{tag}{suffix}_{safe_name}")
            try:
                with open(local_path, "wb") as f:
                    f.write(encrypt_file_bytes(file_bytes))
            except OSError:
                all_attachments_ok = False
                break
            downloaded.append({"local_path": local_path, "original_filename": spec.get("file_original_name", "document")})

        if not all_attachments_ok:
            # Partial download — clean up whatever DID land locally rather
            # than leaving an orphaned file with no message row pointing
            # to it. The entry is untouched on the Worker (nothing was
            # ever deleted there pre-accusé) — the next poll just retries.
            for d in downloaded:
                try:
                    os.remove(d["local_path"])
                except OSError:
                    pass
            continue
        if not _session_is(key, fernet):
            break

        first = downloaded[0]
        try:
            with profile_db(key) as wconn:
                wconn.execute("BEGIN IMMEDIATE")
                wcur = wconn.execute("""
                    INSERT INTO messages (direction, tracking_number, sender_institution,
                                           recipient_institution, subject, body, file_path,
                                           file_original_name, status, delivery_method, is_read,
                                           sender_institution_key, sender_worker_id, created_at)
                    VALUES ('entrant', ?, ?, ?, ?, ?, ?, ?, 'envoye', 'bridge', 0, ?, ?, ?)
                """, (tracking, meta.get("sender_institution", "?"),
                      meta.get("recipient_institution", profile["institution_name"]),
                      encrypt_text(meta.get("subject", "")), encrypt_text(meta.get("body", "")),
                      first["local_path"], first["original_filename"],
                      meta.get("sender_institution_key"), meta.get("sender_institution_id"),
                      meta.get("created_at", datetime.now().isoformat())))
                new_msg_id = wcur.lastrowid
                for order, d in enumerate(downloaded):
                    wconn.execute(
                        "INSERT INTO message_attachments (message_id, file_path, file_original_name, sort_order) "
                        "VALUES (?, ?, ?, ?)",
                        (new_msg_id, d["local_path"], d["original_filename"], order)
                    )
        except sqlite3.IntegrityError:
            for d in downloaded:
                try:
                    os.remove(d["local_path"])
                except OSError:
                    pass
            continue

        imported.append({"tracking_number": tracking, "sender": meta.get("sender_institution", "?")})
        if notify:
            _emit_ui(key, "new_document", imported[-1])
        # No delete here — see the v2.9.5 note above handlePoll's call.
        # Cleanup happens exclusively in push_worker_receipt()/handleAccuse,
        # the moment the person clicks "Accusé" in the TASHIL UI.

    # 5) Apply read receipts — ONE call (GET /poll-receipts); the Worker
    # itself removes each receipt as it's returned (not a permanent log).
    receipts_applied = []
    rcpt_status, rcpt_data = _worker_request(
        cfg["worker_url"], "GET", "/poll-receipts",
        query={"institution_id": own_worker_id, "secret_key": cfg["device_secret"]})
    if rcpt_status == 200:
        for receipt in rcpt_data.get("receipts", []):
            if _active_key != key:
                break
            tracking = receipt.get("tracking_number")
            if not tracking:
                continue
            applied = False
            with profile_db(key) as wconn:
                wconn.execute("BEGIN IMMEDIATE")
                sent_row = wconn.execute(
                    "SELECT status FROM messages WHERE tracking_number = ? AND direction = 'sortant'",
                    (tracking,)).fetchone()
                if sent_row is not None and sent_row["status"] != "accuse":
                    wconn.execute(
                        "UPDATE messages SET status = 'accuse' WHERE tracking_number = ? AND direction = 'sortant'",
                        (tracking,))
                    applied = True
            if applied:
                item = {"tracking_number": tracking, "acknowledged_by": receipt.get("acknowledged_by", "?")}
                receipts_applied.append(item)
                if notify:
                    _emit_ui(key, "receipt_update", item)

    if notify and flushed:
        _emit_ui(key, "sync_update", {"flushed": flushed})   # a stuck "En attente" document just left

    return {"ok": True, "bridge_enabled": True, "new_messages": len(imported),
            "receipts": receipts_applied, "flushed": flushed}


@app.route("/api/bridge/poll", methods=["POST"])
def api_bridge_poll():
    """Manual / fallback poll (🔄 button). The background loop does the
    regular work; this returns the same summary shape as before."""
    if _active_key is None:
        return locked_response()
    result = run_bridge_poll(notify=False)
    if result.get("error"):
        return jsonify({"error": result["error"]}), 502
    return jsonify(result)


def _bridge_loop():
    failures = 0
    while True:
        delay = BRIDGE_POLL_SECONDS
        try:
            if _active_key is not None:
                result = run_bridge_poll(notify=True)
                failures = failures + 1 if result.get("error") else 0
        except Exception:
            app.logger.exception("bridge loop")
            failures += 1
        if failures:   # exponential back-off while GitHub/network is failing
            delay = min(120, BRIDGE_POLL_SECONDS * (2 ** min(failures, 4)))
        time.sleep(delay)


def start_bridge_loop():
    global _bridge_loop_started
    if _bridge_loop_started or os.environ.get("TASHIL_DISABLE_BRIDGE_LOOP") == "1":
        return
    _bridge_loop_started = True
    threading.Thread(target=_bridge_loop, name="tashil-bridge-loop", daemon=True).start()


# Started at import time so it also runs when the app is imported by the
# desktop launcher (desktop_launcher.py) and not only via `python app.py`.
start_bridge_loop()


if __name__ == "__main__":
    print(f"TASHIL DOCUMENT HUB — Web Edition v{APP_VERSION}")
    print(f"Local  : http://127.0.0.1:5000/")
    print(f"Réseau : http://{get_lan_ip()}:5000/  (accessible depuis un téléphone sur le même Wi-Fi)")
    if socketio is not None:
        socketio.run(app, host="0.0.0.0", port=5000, debug=False,
                     use_reloader=False, allow_unsafe_werkzeug=True)
    else:
        app.run(host="0.0.0.0", port=5000, debug=False)
