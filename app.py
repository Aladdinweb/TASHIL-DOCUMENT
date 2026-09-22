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
import hashlib
import hmac
import base64
import uuid
import platform
import subprocess
from io import BytesIO
from datetime import datetime
from contextlib import contextmanager

from flask import (Flask, request, jsonify, send_from_directory,
                    send_file, render_template, abort)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

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
APP_VERSION = "2.8.7"
GITHUB_REPO = "Aladdinweb/TASHIL-ES"  # used by the in-app OTA update checker

app = Flask(__name__,
            template_folder=os.path.join(APP_ROOT, "templates"),
            static_folder=os.path.join(APP_ROOT, "static"))
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64MB upload cap


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
    "EPH": ["DRH", "DAS", ROLE_SECRETARIAT_DIRECTION, ROLE_SECRETARIAT_GENERAL],
    "CHU": ["DRH", "DAS", ROLE_SECRETARIAT_DIRECTION, ROLE_SECRETARIAT_GENERAL],
    "EHU": ["DRH", "DAS", ROLE_SECRETARIAT_DIRECTION, ROLE_SECRETARIAT_GENERAL],
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
# ⚠️ Only Oran (wilaya 31) has a real, user-confirmed hierarchy below —
# every other wilaya still falls back to the single generic
# "EPSP <Wilaya>" head-office option with no satellites, exactly as
# before v2.8.7, until its own real EPSP breakdown is provided the same
# way. Guessing a hierarchy for a wilaya without confirmed data would
# risk misrouting real administrative/medical correspondence — worse
# than temporarily offering only the generic head-office option, which
# every "Autre (saisir manuellement)" fallback already covers today.
_EPSP_HIERARCHY = {
    31: {
        "EPSP ES SENIA": [
            "POLYCLINIQUE ES SENIA",
            "POLYCLINIQUE AADL AIN BEIDA MABROUK LOUCIF",
            "POLYCLINIQUE AIN BEIDA 1",
            "POLYCLINIQUE AIN BEIDA 2",
            "POLYCLINIQUE SIDI MAAROUF",
            "POLYCLINIQUE SIDI CHAHMI",
            "POLYCLINIQUE EL KERMA",
            "SALLE DE SOIN TERMINUS",
        ],
        "EPSP SEDDIKIA": [  # also known locally as "Front de Mer"
            "POLYCLINIQUE AKID LOTFI",
            "POLYCLINIQUE SEDDIKIA",
            "POLYCLINIQUE GAMBETTA",
        ],
        "EPSP ARZEW": [
            "POLYCLINIQUE ARZEW",
            "POLYCLINIQUE BETHIOUA",
            "POLYCLINIQUE GDYEL",
        ],
        "EPSP BOUTLELIS": [
            "POLYCLINIQUE MISSERGHIN",
            "POLYCLINIQUE BOUTLELIS",
        ],
    }
}
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
def _open_sqlite_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bridge_pending_cleanup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_path TEXT NOT NULL,
            sha TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


@contextmanager
def profile_db(institution_key: str, commit: bool = True):
    conn = get_profile_db(institution_key)
    try:
        yield conn
        if commit:
            conn.commit()
    finally:
        conn.close()


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
GITHUB_API_BASE = "https://api.github.com"


def _github_request(method: str, url_or_path: str, token: str, json_body: dict = None):
    """
    Minimal GitHub REST API client using urllib only. Accepts either a
    path (starting with '/') or a full URL (as returned in listing
    responses' 'url' field) — both are used by the polling logic below.
    Returns (status_code, parsed_json_or_empty_dict).

    Explicitly uses certifi's CA bundle for SSL verification rather than
    relying on urllib's default context. This is a real, known issue with
    PyInstaller-frozen Windows executables: the frozen exe often can't
    locate the OS certificate store the way a normal Python installation
    does, producing "SSL: CERTIFICATE_VERIFY_FAILED — unable to get local
    issuer certificate" even when the network connection itself is fine.
    Bundling and pointing at certifi's own cacert.pem sidesteps that
    entirely — confirmed as the cause via a real error report.
    """
    import urllib.request
    import urllib.error
    import ssl

    url = url_or_path if url_or_path.startswith("http") else f"{GITHUB_API_BASE}{url_or_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "TASHIL-DOCUMENT-HUB",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = json.dumps(json_body).encode("utf-8") if json_body is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    ssl_context = ssl.create_default_context(cafile=certifi.where()) if _CERTIFI_AVAILABLE else None

    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl_context) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw.decode("utf-8")) if raw else {})
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except Exception:
            payload = {}
        return e.code, payload
    except Exception as exc:
        return 0, {"message": str(exc)}


def get_bridge_config():
    with registry_db(commit=False) as conn:
        row = conn.execute("SELECT * FROM bridge_config WHERE id = 1").fetchone()
    return dict(row) if row else None


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


def push_to_bridge(cfg: dict, recipient_name: str, recipient_role: str, sender_name: str,
                    sender_institution_key: str, subject: str,
                    body: str, tracking: str, file_bytes: bytes, original_filename: str) -> bool:
    owner, repo, token = cfg["github_owner"], cfg["github_repo"], cfg["github_token"]
    key = bridge_slug(recipient_name, recipient_role)

    file_ext = os.path.splitext(original_filename)[1]
    attachment_repo_path = f"bridge/{key}/{tracking}{file_ext}"
    meta_repo_path = f"bridge/{key}/{tracking}.json"

    meta = {
        "tracking_number": tracking,
        "sender_institution": sender_name,
        "sender_institution_key": sender_institution_key,
        "recipient_institution": recipient_name,
        "recipient_role": recipient_role,
        "subject": subject,
        "body": body,
        "file_original_name": original_filename,
        "attachment_path_in_repo": attachment_repo_path,
        "created_at": datetime.now().isoformat(),
    }

    # file_bytes are the ORIGINAL plaintext (see api_send_message) — never
    # the sender's own encrypted archive copy, which only the sender's key
    # could ever open. The Cloud Bridge itself provides no encryption of
    # its own (see the module-level security note above); the recipient
    # applies its own encryption independently when it later imports this.
    file_b64 = base64.b64encode(file_bytes).decode("utf-8")

    meta_b64 = base64.b64encode(
        json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("utf-8")

    status_meta, _ = _github_request(
        "PUT", f"/repos/{owner}/{repo}/contents/{meta_repo_path}", token,
        {"message": f"TASHIL bridge: {tracking} (metadata)", "content": meta_b64}
    )
    status_file, _ = _github_request(
        "PUT", f"/repos/{owner}/{repo}/contents/{attachment_repo_path}", token,
        {"message": f"TASHIL bridge: {tracking} (attachment)", "content": file_b64}
    )
    return status_meta in (200, 201) and status_file in (200, 201)


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
    clear_active_session()
    return jsonify({"ok": True})


@app.route("/api/profile/delete", methods=["POST"])
def api_delete_profile():
    """
    Permanently deletes the CURRENTLY ACTIVE profile: its isolated database,
    its entire archive folder (Courrier_Sortant + Courrier_Entrant), and its
    entry in the device's registry. Irreversible — requires the profile's
    own PIN to be re-entered as the actual authorization (a dismissible
    confirm() dialog alone is not enough protection for a destructive
    action against real archived documents).
    """
    if _active_key is None:
        return locked_response()

    data = request.get_json(force=True)
    pin = data.get("pin", "")

    profile = get_profile_row(_active_key)
    if profile is None:
        clear_active_session()
        return jsonify({"error": "Profil introuvable."}), 404
    if profile["pin_hash"] is None or not check_password_hash(profile["pin_hash"], pin):
        return jsonify({"error": "Code PIN incorrect."}), 401

    key_to_delete = _active_key
    paths = profile_paths(key_to_delete)

    # Lock immediately — no further access to this profile from this point
    # on, regardless of whether file cleanup below fully succeeds.
    clear_active_session()

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
        return jsonify({
            "ok": True,
            "warning": f"Le profil a été retiré, mais certains fichiers n'ont pas pu être "
                       f"supprimés automatiquement ({exc}). Vous pouvez les supprimer "
                       f"manuellement dans le dossier de l'application si besoin."
        })

    return jsonify({"ok": True})


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
        recent = [decrypt_message_row(r) for r in recent]

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
        rows = [decrypt_message_row(r) for r in rows]

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
    file = request.files.get("file")

    if not recipient:
        return jsonify({"error": "Institution destinataire requise."}), 400
    if not file or file.filename == "":
        return jsonify({"error": "Un fichier est requis."}), 400

    profile = get_profile_row(_active_key)
    sender = profile["institution_name"] if profile else "TASHIL"
    paths = profile_paths(_active_key)

    # Read the original plaintext bytes ONCE. Only the SENDER's own
    # archived copy gets encrypted below, with the sender's own key — any
    # copy handed to a different security domain (local delivery, Cloud
    # Bridge) must use these original bytes, never the sender's encrypted
    # file, which a recipient has no way to decrypt (different key/PIN).
    original_bytes = file.read()

    # v2.8.3: reject a genuinely empty upload outright rather than
    # silently archiving a 0-byte file that would later show as
    # "corrupted" with no indication of why. This can't catch every
    # possible network-level truncation (the server only ever sees what
    # actually arrived), but an empty body specifically — an interrupted
    # or failed upload — is easy to detect and worth failing loudly.
    if not original_bytes:
        return jsonify({"error": "Le fichier reçu est vide (0 octet) — "
                                  "l'envoi a probablement été interrompu. Réessayez."}), 400

    # v2.8.3: correct the filename's extension to match the file's REAL
    # bytes (magic-byte signature) rather than blindly trusting whatever
    # extension the client sent — see sniff_real_extension() docstring.
    # This is a safety net, not the actual HEIC fix (that's the
    # frontend's job, see static/js/app.js normalizeImageForUpload) —
    # it only prevents a mislabeled file from reaching a recipient under
    # a name that lies about what format it actually is.
    original_filename = file.filename or "document"
    name_root, current_ext = os.path.splitext(original_filename)
    real_ext = sniff_real_extension(original_bytes, current_ext.lower())
    if real_ext != current_ext.lower():
        original_filename = f"{name_root}{real_ext}"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = sanitize(sender).replace(" ", "")[:30]
    safe_name = sanitize(secure_filename(original_filename) or "document")
    archived_name = f"{ts}_{tag}_{safe_name}"
    archived_path = os.path.join(paths["sortant"], archived_name)
    with open(archived_path, "wb") as f:
        f.write(encrypt_file_bytes(original_bytes))

    # Short, isolated connection: open, write, commit, close — never held
    # open across the network calls (local-delivery file copy, Cloud
    # Bridge push) that happen further down in this route. This is the
    # crux of the "database is locked" fix: a slow network call must
    # never happen while a SQLite write transaction is still open,
    # because that's exactly the window where the background Cloud
    # Bridge poll (or heartbeat) can collide with it.
    with profile_db(_active_key) as conn:
        # v2.8.2: defense in depth on top of next_tracking_number()'s own
        # existence check — if two sends somehow land on the exact same
        # microsecond-scale race and still produce the same candidate
        # (never observed, but not worth assuming impossible), retry with
        # a freshly generated number instead of failing the whole send.
        for attempt in range(3):
            tracking = next_tracking_number(conn, "sortant", _active_key)
            try:
                conn.execute("""
                    INSERT INTO messages (direction, tracking_number, sender_institution,
                                           recipient_institution, subject, body, file_path,
                                           file_original_name, status, delivery_method, created_at)
                    VALUES ('sortant', ?, ?, ?, ?, ?, ?, ?, 'envoye', NULL, ?)
                """, (tracking, sender, recipient, encrypt_text(subject), encrypt_text(body),
                      archived_path, original_filename, datetime.now().isoformat()))
                break
            except sqlite3.IntegrityError:
                if attempt == 2:
                    raise
                continue

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
            recipient_archived_path = os.path.join(recipient_paths["entrant"], archived_name)
            # Plaintext, deliberately — see the encryption scope limitation
            # documented above set_active_session(): we don't have the
            # recipient's PIN/key at this point (they're locked), so we
            # cannot encrypt on their behalf. This writes the ORIGINAL
            # bytes, never the sender's encrypted copy (which only the
            # sender's own key could ever open).
            with open(recipient_archived_path, "wb") as f:
                f.write(original_bytes)

            recipient_tracking = tracking
            try:
                with profile_db(recipient_key) as recipient_conn:
                    recipient_conn.execute("""
                        INSERT INTO messages (direction, tracking_number, sender_institution,
                                               recipient_institution, subject, body, file_path,
                                               file_original_name, status, delivery_method, is_read,
                                               sender_institution_key, created_at)
                        VALUES ('entrant', ?, ?, ?, ?, ?, ?, ?, 'envoye', 'local', 0, ?, ?)
                    """, (recipient_tracking, sender, recipient, subject, body,
                          recipient_archived_path, original_filename, _active_key, datetime.now().isoformat()))
            except sqlite3.IntegrityError:
                # Extremely rare tracking-number collision across two
                # independent institution databases — disambiguate and retry.
                recipient_tracking = f"{tracking}-{uuid.uuid4().hex[:4].upper()}"
                with profile_db(recipient_key) as recipient_conn:
                    recipient_conn.execute("""
                        INSERT INTO messages (direction, tracking_number, sender_institution,
                                               recipient_institution, subject, body, file_path,
                                               file_original_name, status, delivery_method, is_read,
                                               sender_institution_key, created_at)
                        VALUES ('entrant', ?, ?, ?, ?, ?, ?, ?, 'envoye', 'local', 0, ?, ?)
                    """, (recipient_tracking, sender, recipient, subject, body,
                          recipient_archived_path, original_filename, _active_key, datetime.now().isoformat()))
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
                delivered_via_bridge = push_to_bridge(
                    bridge_cfg, recipient, recipient_role, sender, _active_key, subject, body,
                    tracking, original_bytes, original_filename
                )
            except Exception:
                delivered_via_bridge = False

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
    if row is None or not row["file_path"] or not os.path.exists(row["file_path"]):
        abort(404)

    # decrypt_file_bytes is safe to call unconditionally: files written by
    # local delivery (a different security domain — see api_send_message)
    # are genuinely plaintext, and Fernet.decrypt() on non-Fernet bytes
    # raises InvalidToken, which decrypt_file_bytes catches and returns
    # the original bytes unchanged. The ciphertext format itself is the
    # only "is this encrypted" flag needed — no separate per-file marker.
    with open(row["file_path"], "rb") as f:
        raw = f.read()
    plaintext = decrypt_file_bytes(raw)

    return send_file(BytesIO(plaintext), as_attachment=True,
                      download_name=row["file_original_name"] or "document")


@app.route("/api/messages/<int:message_id>/status", methods=["POST"])
def api_update_message_status(message_id):
    if _active_key is None:
        return locked_response()
    data = request.get_json(force=True)
    status = data.get("status", "").strip()
    if status not in ("envoye", "recu", "accuse", "en_attente"):
        return jsonify({"error": "Statut invalide."}), 400

    with profile_db(_active_key) as conn:
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
                push_receipt_to_bridge(cfg, sender_name, sender_key, tracking, acknowledger_name)
    except Exception:
        pass  # see docstring — a failed receipt never blocks the accusé itself


def push_receipt_to_bridge(cfg: dict, sender_name: str, sender_key: str, tracking: str, acknowledger_name: str) -> bool:
    owner, repo, token = cfg["github_owner"], cfg["github_repo"], cfg["github_token"]
    # v2.8.7: address the receipt using the sender's exact
    # institution_key when known — this is one of the addresses the
    # sender's OWN poll loop already checks (see api_bridge_poll's
    # keys_to_check, which includes bridge_slug(profile["institution_key"])),
    # so no change is needed on the polling side. Falls back to the old
    # name-based address (role-blind) for messages that predate this column.
    key = bridge_slug(sender_key) if sender_key else bridge_slug(sender_name)
    receipt_path = f"bridge/{key}/receipts/{tracking}.json"
    payload = {
        "type": "receipt",
        "tracking_number": tracking,
        "acknowledged_by": acknowledger_name,
        "acknowledged_at": datetime.now().isoformat(),
    }
    payload_b64 = base64.b64encode(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ).decode("utf-8")
    status, _ = _github_request(
        "PUT", f"/repos/{owner}/{repo}/contents/{receipt_path}", token,
        {"message": f"TASHIL bridge: receipt for {tracking}", "content": payload_b64}
    )
    return status in (200, 201)


@app.route("/api/messages/<int:message_id>", methods=["DELETE"])
def api_delete_message(message_id):
    if _active_key is None:
        return locked_response()
    with profile_db(_active_key) as conn:
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            return jsonify({"error": "Message introuvable."}), 404

        file_path = row["file_path"]
        conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass  # DB record is already gone; a leftover file is not fatal

    return jsonify({"ok": True})


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
        rows = [decrypt_message_row(r) for r in rows]
    return jsonify({"entries": rows})


# --------------------------------------------------------------------------- #
# API — Cloud Bridge configuration & manual poll
# --------------------------------------------------------------------------- #
@app.route("/api/bridge/network-test", methods=["GET"])
def api_bridge_network_test():
    """
    Diagnostic-only, no token/repo needed: checks whether THIS machine can
    reach api.github.com over HTTPS at all — separates "GitHub itself is
    unreachable / blocked by a firewall or proxy" from "the repo/token
    configuration is wrong", which otherwise look identical from the
    config form's point of view. Deliberately sends NO Authorization
    header (unlike _github_request) — this checks pure network/SSL
    reachability, not credentials.
    """
    import time
    import urllib.request
    import urllib.error
    import ssl

    ssl_context = ssl.create_default_context(cafile=certifi.where()) if _CERTIFI_AVAILABLE else None
    req = urllib.request.Request(
        "https://api.github.com/zen",
        headers={"User-Agent": "TASHIL-DOCUMENT-HUB", "Accept": "application/vnd.github+json"},
    )

    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as resp:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return jsonify({"ok": True, "elapsed_ms": elapsed_ms,
                             "message": "Connexion à api.github.com réussie."})
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        error_message = str(exc)
        hint = ""
        if "CERTIFICATE_VERIFY_FAILED" in error_message:
            hint = ("Problème de certificat SSL — souvent causé par un antivirus/pare-feu "
                    "qui inspecte le trafic HTTPS, ou un proxy d'entreprise.")
        elif "timed out" in error_message.lower():
            hint = "Délai dépassé — le pare-feu bloque probablement la connexion sortante."
        elif "Name or service not known" in error_message or "getaddrinfo failed" in error_message:
            hint = "Résolution DNS échouée — vérifiez la connexion Internet de cette machine."
        elif "Connection refused" in error_message:
            hint = "Connexion refusée — un pare-feu local ou réseau bloque probablement le port 443."

        return jsonify({"ok": False, "elapsed_ms": elapsed_ms, "message": error_message, "hint": hint})


@app.route("/api/bridge/config", methods=["GET"])
def api_bridge_get_config():
    cfg = get_bridge_config()
    if cfg is None:
        return jsonify({"configured": False, "enabled": False})
    return jsonify({
        "configured": bool(cfg["github_owner"] and cfg["github_repo"] and cfg["github_token"]),
        "enabled": bool(cfg["enabled"]),
        "github_owner": cfg["github_owner"],
        "github_repo": cfg["github_repo"],
        # github_token deliberately never sent back to the frontend
    })


def _validate_and_save_bridge_config(owner: str, repo: str, token: str):
    """
    Shared by both the manual entry form AND the QR/pasted-code import path
    — guarantees the private-repo safety check applies identically no
    matter how the credentials arrived. Returns (status_code, body_dict).

    Deliberately does the (slow) GitHub network call BEFORE opening any
    SQLite connection — the write itself is a single short INSERT/UPDATE.
    """
    if not owner or not repo or not token:
        return 400, {"error": "Propriétaire, dépôt et jeton GitHub sont tous requis."}

    status, repo_info = _github_request("GET", f"/repos/{owner}/{repo}", token)
    if status == 0:
        return 502, {"error": f"Impossible de contacter GitHub : {repo_info.get('message', 'réseau indisponible')}"}
    if status == 401:
        return 401, {"error": "Jeton GitHub invalide ou expiré."}
    if status == 404:
        return 404, {"error": "Dépôt introuvable (ou le jeton n'y a pas accès)."}
    if status != 200:
        return 502, {"error": f"Erreur GitHub inattendue ({status})."}

    if repo_info.get("private") is not True:
        return 400, {
            "error": "Ce dépôt est PUBLIC. TASHIL refuse d'y transmettre des documents. "
                     "Utilisez un dépôt privé dédié."
        }

    with registry_db() as conn:
        conn.execute("""
            INSERT INTO bridge_config (id, github_owner, github_repo, github_token, enabled, updated_at)
            VALUES (1, ?, ?, ?, 1, ?)
            ON CONFLICT(id) DO UPDATE SET
                github_owner=excluded.github_owner, github_repo=excluded.github_repo,
                github_token=excluded.github_token, enabled=1, updated_at=excluded.updated_at
        """, (owner, repo, token, datetime.now().isoformat()))

    return 200, {"ok": True, "private_verified": True}


@app.route("/api/bridge/config", methods=["POST"])
def api_bridge_save_config():
    data = request.get_json(force=True)
    owner = data.get("github_owner", "").strip()
    repo = data.get("github_repo", "").strip()
    token = data.get("github_token", "").strip()
    status, body = _validate_and_save_bridge_config(owner, repo, token)
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
    payload = {
        "github_owner": cfg["github_owner"],
        "github_repo": cfg["github_repo"],
        "github_token": cfg["github_token"],
    }
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def parse_provisioning_code(code: str) -> dict:
    payload = json.loads(base64.b64decode(code.strip().encode("ascii")).decode("utf-8"))
    if not isinstance(payload, dict) or "github_token" not in payload:
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

    status, body = _validate_and_save_bridge_config(
        payload.get("github_owner", ""), payload.get("github_repo", ""), payload.get("github_token", "")
    )
    return jsonify(body), status


@app.route("/api/bridge/disable", methods=["POST"])
def api_bridge_disable():
    with registry_db() as conn:
        conn.execute("UPDATE bridge_config SET enabled = 0 WHERE id = 1")
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- #
# Retry-on-delete-failure (v2.7.0): if a GitHub DELETE call fails right
# after a message/receipt was successfully imported (rare transient
# network issue), the entry is queued in bridge_pending_cleanup instead
# of silently left behind — because once imported, its tracking_number is
# already known locally, so future polls would otherwise skip re-checking
# it entirely, and the stray copy would linger in the repo unnoticed.
# --------------------------------------------------------------------------- #
def _queue_bridge_cleanup(conn, url_or_path: str, sha: str):
    conn.execute(
        "INSERT INTO bridge_pending_cleanup (repo_path, sha, created_at) VALUES (?, ?, ?)",
        (url_or_path, sha, datetime.now().isoformat())
    )


def _delete_bridge_entry_or_queue(conn, owner: str, repo: str, token: str, url_or_path: str, sha: str):
    """
    Note: the GitHub DELETE call below happens WHILE `conn` (passed in by
    the caller) may still be open for the current poll cycle — this
    mirrors the original design and is fine under WAL: readers elsewhere
    are not blocked by it, and a same-process write from the same
    connection is not the kind of cross-connection contention WAL/
    busy_timeout are guarding against. The queuing INSERT itself, right
    below, is a fast local write with no network in between.
    """
    status, _ = _github_request("DELETE", url_or_path, token,
                                 {"message": "TASHIL bridge: consumed", "sha": sha})
    if status not in (200, 204):
        _queue_bridge_cleanup(conn, url_or_path, sha)


def _retry_pending_bridge_cleanup(conn, owner: str, repo: str, token: str):
    pending = conn.execute("SELECT * FROM bridge_pending_cleanup").fetchall()
    for row in pending:
        status, _ = _github_request("DELETE", row["repo_path"], token,
                                     {"message": "TASHIL bridge: retried cleanup", "sha": row["sha"]})
        if status in (200, 204):
            conn.execute("DELETE FROM bridge_pending_cleanup WHERE id = ?", (row["id"],))


# --------------------------------------------------------------------------- #
# "Établissements connectés" (v2.8.0) — presence directory.
#
# ⚠️ Real design constraint, worth understanding: the bridge repo has no
# built-in registry of institutions — a folder under bridge/<address>/
# only exists once someone has actually SENT a message there. There was
# no way to answer "which institutions are configured/active on the
# network" from the existing structure alone. This adds an explicit
# heartbeat: each unlocked device periodically writes its own presence
# file to directory/<institution_key>.json, piggybacked on the existing
# bridge poll cycle (no extra timer). "Connecté" here means "has recently
# written a heartbeat" — a device that's been closed for a while will
# correctly show as offline once its last heartbeat goes stale, not
# because anything failed, simply because it stopped announcing itself.
# --------------------------------------------------------------------------- #
_HEARTBEAT_STALE_AFTER_SECONDS = 180  # ~4 missed 45s poll cycles


def _send_heartbeat(owner: str, repo: str, token: str, profile: dict):
    payload = {
        "institution_key": profile["institution_key"],
        "institution_name": profile["institution_name"],
        "institution_type": profile["institution_type"],
        "wilaya_name": profile["wilaya_name"],
        "last_seen": datetime.now().isoformat(),
    }
    payload_b64 = base64.b64encode(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ).decode("utf-8")
    path = f"directory/{profile['institution_key']}.json"

    # Need the current sha to update an existing file — GitHub's Contents
    # API rejects an overwrite without it. A fresh heartbeat file has none.
    status, existing = _github_request("GET", f"/repos/{owner}/{repo}/contents/{path}", token)
    body = {"message": f"TASHIL heartbeat: {profile['institution_name']}", "content": payload_b64}
    if status == 200 and "sha" in existing:
        body["sha"] = existing["sha"]

    _github_request("PUT", f"/repos/{owner}/{repo}/contents/{path}", token, body)


@app.route("/api/bridge/directory", methods=["GET"])
def api_bridge_directory():
    if _active_key is None:
        return locked_response()
    cfg = get_bridge_config()
    if not cfg or not cfg["enabled"]:
        return jsonify({"bridge_enabled": False, "institutions": []})

    owner, repo, token = cfg["github_owner"], cfg["github_repo"], cfg["github_token"]
    status, listing = _github_request("GET", f"/repos/{owner}/{repo}/contents/directory", token)
    if status == 404:
        return jsonify({"bridge_enabled": True, "institutions": []})
    if status != 200:
        return jsonify({"error": f"Erreur GitHub ({status})."}), 502

    now = datetime.now()
    institutions = []
    for entry in listing:
        if not entry["name"].endswith(".json"):
            continue
        file_status, content = _github_request("GET", entry["url"], token)
        if file_status != 200 or "content" not in content:
            continue
        try:
            record = json.loads(base64.b64decode(content["content"]).decode("utf-8"))
            last_seen = datetime.fromisoformat(record["last_seen"])
        except (ValueError, KeyError):
            continue

        age_seconds = (now - last_seen).total_seconds()
        institutions.append({
            "institution_key": record.get("institution_key", ""),
            "institution_name": record.get("institution_name", "?"),
            "institution_type": record.get("institution_type", ""),
            "wilaya_name": record.get("wilaya_name", ""),
            "last_seen": record["last_seen"],
            "online": age_seconds <= _HEARTBEAT_STALE_AFTER_SECONDS,
        })

    institutions.sort(key=lambda i: (not i["online"], i["institution_name"]))
    return jsonify({"bridge_enabled": True, "institutions": institutions})


@app.route("/api/bridge/poll", methods=["POST"])
def api_bridge_poll():
    """
    Checks the Cloud Bridge repo for new messages AND read-receipts
    addressed to the CURRENTLY ACTIVE profile. Downloads/imports anything
    found into that profile's own isolated database + archive, applies
    any receipts to the matching sent items, then removes consumed
    entries from the bridge repo — retrying any cleanup that failed on a
    previous poll first. Safe to call repeatedly — already-seen tracking
    numbers are skipped.

    This function's SQLite connection (via profile_db()) is held open for
    the whole poll, interleaved with many GitHub network calls — that
    part of the original design is unchanged here. What changes with
    v2.8.1 is that this connection now runs in WAL mode with a 5s
    busy_timeout, same as every other connection in the app: a
    foreground request (e.g. a send, or opening the Registre) that needs
    the SAME profile's database while a poll is mid-flight now waits up
    to 5 seconds and proceeds, instead of failing immediately with
    "database is locked". The context manager also guarantees this
    connection is always closed — even if a GitHub call raises or a
    network timeout occurs partway through — so a failed poll can never
    leak a held-open connection into the next request.
    """
    if _active_key is None:
        return locked_response()

    cfg = get_bridge_config()
    if not cfg or not cfg["enabled"]:
        return jsonify({"ok": True, "bridge_enabled": False, "new_messages": 0, "receipts": []})

    profile = get_profile_row(_active_key)
    owner, repo, token = cfg["github_owner"], cfg["github_repo"], cfg["github_token"]
    paths = profile_paths(_active_key)

    with profile_db(_active_key) as conn:
        # Retry any deletions that failed on a previous poll BEFORE
        # processing new entries (see queue_bridge_cleanup / feature note).
        _retry_pending_bridge_cleanup(conn, owner, repo, token)

        # Announce presence for "Établissements connectés" — piggybacked
        # here rather than a separate timer, so it costs no extra GitHub
        # API budget beyond what polling already uses.
        try:
            _send_heartbeat(owner, repo, token, profile)
        except Exception:
            pass  # a missed heartbeat just means this device looks offline a bit longer, not a real failure

        # A sender may have addressed this institution by its plain name
        # (v2.8.5: now role-aware for non-SECRETARIAT roles), or by its
        # exact routing ID (institution_key, always role-specific by
        # construction) — check every form so no addressing style
        # silently gets lost. Deduplicated by set() since some of these
        # can normalize to the same slug (e.g. a SECRETARIAT profile's
        # plain-name slug is unchanged from pre-v2.8.5).
        profile_role = profile.get("role") or DEFAULT_ROLE
        keys_to_check = {
            bridge_slug(profile["institution_name"], profile_role),
            bridge_slug(profile["institution_key"]),
        }

        json_entries = []
        receipt_entries = []
        for key in keys_to_check:
            status, listing = _github_request("GET", f"/repos/{owner}/{repo}/contents/bridge/{key}", token)
            if status == 200:
                json_entries.extend(f for f in listing if f["name"].endswith(".json"))
            elif status != 404:
                return jsonify({"error": f"Erreur GitHub ({status})."}), 502

            r_status, r_listing = _github_request(
                "GET", f"/repos/{owner}/{repo}/contents/bridge/{key}/receipts", token
            )
            if r_status == 200:
                receipt_entries.extend(f for f in r_listing if f["name"].endswith(".json"))
            elif r_status != 404:
                return jsonify({"error": f"Erreur GitHub ({r_status})."}), 502

        new_count = 0
        for entry in json_entries:
            meta_status, meta_content = _github_request("GET", entry["url"], token)
            if meta_status != 200 or "content" not in meta_content:
                continue
            try:
                meta = json.loads(base64.b64decode(meta_content["content"]).decode("utf-8"))
            except (ValueError, KeyError):
                continue

            already_have = conn.execute(
                "SELECT 1 FROM messages WHERE tracking_number = ?", (meta["tracking_number"],)
            ).fetchone()
            if already_have:
                # Already imported on a previous poll — if cleanup failed
                # that time, _retry_pending_bridge_cleanup above already
                # handles it.
                continue

            attach_status, attach_content = _github_request(
                "GET", f"/repos/{owner}/{repo}/contents/{meta['attachment_path_in_repo']}", token
            )
            if attach_status != 200 or "content" not in attach_content:
                continue
            file_bytes = base64.b64decode(attach_content["content"])

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            tag = sanitize(meta.get("sender_institution", "DISTANT")).replace(" ", "")[:30]
            safe_name = sanitize(meta.get("file_original_name", "document"))
            local_path = os.path.join(paths["entrant"], f"{ts}_{tag}_{safe_name}")
            try:
                # Encrypts with THIS profile's own active key, if it has
                # encryption enabled — safe no-op otherwise. We're the
                # recipient and unlocked right now, so (unlike local
                # delivery) applying our own encryption here is correct.
                with open(local_path, "wb") as f:
                    f.write(encrypt_file_bytes(file_bytes))
            except OSError:
                continue

            conn.execute("""
                INSERT INTO messages (direction, tracking_number, sender_institution,
                                       recipient_institution, subject, body, file_path,
                                       file_original_name, status, delivery_method, is_read,
                                       sender_institution_key, created_at)
                VALUES ('entrant', ?, ?, ?, ?, ?, ?, ?, 'envoye', 'bridge', 0, ?, ?)
            """, (meta["tracking_number"], meta.get("sender_institution", "?"),
                  meta.get("recipient_institution", profile["institution_name"]),
                  encrypt_text(meta.get("subject", "")), encrypt_text(meta.get("body", "")),
                  local_path, meta.get("file_original_name", "document"),
                  meta.get("sender_institution_key"),
                  meta.get("created_at", datetime.now().isoformat())))
            new_count += 1

            # Clean up consumed entries so the bridge queue doesn't grow
            # forever — queue for retry instead of silently dropping if
            # the delete itself fails (see _retry_pending_bridge_cleanup).
            _delete_bridge_entry_or_queue(conn, owner, repo, token, entry["url"], entry["sha"])
            _delete_bridge_entry_or_queue(
                conn, owner, repo, token,
                f"/repos/{owner}/{repo}/contents/{meta['attachment_path_in_repo']}",
                attach_content["sha"]
            )

        receipts_applied = []
        for entry in receipt_entries:
            r_status, r_content = _github_request("GET", entry["url"], token)
            if r_status != 200 or "content" not in r_content:
                continue
            try:
                receipt = json.loads(base64.b64decode(r_content["content"]).decode("utf-8"))
            except (ValueError, KeyError):
                continue

            tracking = receipt.get("tracking_number")
            if tracking:
                sent_row = conn.execute(
                    "SELECT * FROM messages WHERE tracking_number = ? AND direction = 'sortant'", (tracking,)
                ).fetchone()
                if sent_row is not None and sent_row["status"] != "accuse":
                    conn.execute(
                        "UPDATE messages SET status = 'accuse' WHERE tracking_number = ? AND direction = 'sortant'",
                        (tracking,)
                    )
                    receipts_applied.append({
                        "tracking_number": tracking,
                        "acknowledged_by": receipt.get("acknowledged_by", "?"),
                    })

            # Consume the receipt regardless, so it never sits in the queue forever.
            _delete_bridge_entry_or_queue(conn, owner, repo, token, entry["url"], entry["sha"])

    return jsonify({
        "ok": True,
        "bridge_enabled": True,
        "new_messages": new_count,
        "receipts": receipts_applied,
    })


if __name__ == "__main__":
    print(f"TASHIL DOCUMENT HUB — Web Edition v{APP_VERSION}")
    print(f"Local  : http://127.0.0.1:5000/")
    print(f"Réseau : http://{get_lan_ip()}:5000/  (accessible depuis un téléphone sur le même Wi-Fi)")
    app.run(host="0.0.0.0", port=5000, debug=False)
