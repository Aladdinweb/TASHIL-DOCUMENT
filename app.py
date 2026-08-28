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
from io import BytesIO
from datetime import datetime

from flask import (Flask, request, jsonify, send_from_directory,
                    send_file, render_template, abort)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

try:
    import qrcode
    _QRCODE_AVAILABLE = True
except ImportError:
    _QRCODE_AVAILABLE = False

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
APP_VERSION = "2.3.1"
GITHUB_REPO = "Aladdinweb/TASHIL-ES"  # used by the in-app OTA update checker

app = Flask(__name__,
            template_folder=os.path.join(APP_ROOT, "templates"),
            static_folder=os.path.join(APP_ROOT, "static"))
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64MB upload cap

INSTITUTION_TYPES = ["EPSP", "EPH", "CHU", "EHU", "Polyclinique"]
_TYPE_CODES = {"EPSP": "EP", "EPH": "EH", "CHU": "CU", "EHU": "HU", "Polyclinique": "PC"}
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
_REAL_ESSENIA_POLYCLINICS = [
    "POLYCLINIQUE ES SENIA",
    "POLYCLINIQUE AADL AIN BEIDA MABROUK LOUCIF",
    "POLYCLINIQUE AIN BEIDA 1",
    "POLYCLINIQUE AIN BEIDA 2",
    "POLYCLINIQUE SIDI MAAROUF",
    "POLYCLINIQUE SIDI CHAHMI",
    "POLYCLINIQUE EL KERMA",
]
_CHU_WILAYAS = {"Alger", "Oran", "Constantine", "Annaba", "Tlemcen", "Sétif",
                "Batna", "Blida", "Béjaïa", "Sidi Bel Abbès", "Tizi Ouzou"}

def _build_institutions_directory():
    entries = list(_REAL_ESSENIA_POLYCLINICS)
    for _, wilaya_name in WILAYAS:
        entries.append(f"EPSP {wilaya_name}")
        entries.append(f"EPH {wilaya_name}")
        entries.append(f"Polyclinique {wilaya_name}")
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
    (31, "EPSP"): list(_REAL_ESSENIA_POLYCLINICS),
    (31, "Polyclinique"): list(_REAL_ESSENIA_POLYCLINICS),
    (31, "EPH"): ["EPH AIN TURCK"],
    (31, "CHU"): ["CHU ORAN"],
    (31, "EHU"): ["EHU ORAN"],
}

def get_onboarding_institutions(wilaya_code: int, institution_type: str):
    known = _ONBOARDING_KNOWN.get((wilaya_code, institution_type))
    if known:
        return list(known)
    wilaya_name = dict(WILAYAS).get(wilaya_code)
    if wilaya_name is None:
        return []
    return [f"{institution_type} {wilaya_name}"]


# --------------------------------------------------------------------------- #
# Registry DB — the master list of institution profiles on this device.
# Lives OUTSIDE any profile folder, at ~/TASHIL_DATA/registry.db.
# --------------------------------------------------------------------------- #
def get_registry_db():
    conn = sqlite3.connect(REGISTRY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_registry_db():
    conn = get_registry_db()
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
    conn.commit()
    conn.close()


init_registry_db()


def sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip() or "document"


def make_institution_key(wilaya_code: int, institution_type: str, institution_name: str) -> str:
    type_code = _TYPE_CODES.get(institution_type, "XX")
    slug = re.sub(r'[^A-Za-z0-9]+', '_', institution_name.strip().upper()).strip('_')
    base_key = f"{wilaya_code:02d}_{type_code}_{slug}"[:80]

    conn = get_registry_db()
    key = base_key
    suffix = 2
    while conn.execute("SELECT 1 FROM profiles WHERE institution_key = ?", (key,)).fetchone():
        key = f"{base_key}_{suffix}"
        suffix += 1
    conn.close()
    return key


def generate_serial_key(wilaya_code, institution_type, institution_name) -> str:
    secret = b"ILINE-TECH-2026-FERAK-ALADDIN-TASHIL-DOCUMENT-HUB"
    type_code = _TYPE_CODES.get(institution_type, "XX")
    salt = datetime.now().strftime("%Y%m%d")
    payload = f"{wilaya_code:02d}|{type_code}|{institution_name.upper()}|{salt}"
    digest = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).digest()
    body_hex = digest.hex()[:4].upper()
    checksum = base64.b32encode(digest[:3]).decode("utf-8")[:4]
    return f"TSH-{wilaya_code:02d}-{type_code}-{body_hex}-{checksum}"


def list_profiles():
    conn = get_registry_db()
    rows = conn.execute("SELECT * FROM profiles ORDER BY institution_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_profile_row(institution_key: str):
    conn = get_registry_db()
    row = conn.execute("SELECT * FROM profiles WHERE institution_key = ?", (institution_key,)).fetchone()
    conn.close()
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


def get_profile_db(institution_key: str):
    paths = profile_paths(institution_key)
    os.makedirs(paths["sortant"], exist_ok=True)
    os.makedirs(paths["entrant"], exist_ok=True)
    conn = sqlite3.connect(paths["db"])
    conn.row_factory = sqlite3.Row
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
    return conn


def next_tracking_number(conn, direction: str) -> str:
    prefix = "S" if direction == "sortant" else "E"
    year = datetime.now().year
    count = conn.execute(
        "SELECT COUNT(*) as c FROM messages WHERE direction = ?", (direction,)
    ).fetchone()["c"]
    return f"TASHIL-{prefix}-{year}-{count + 1:06d}"


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
        legacy_conn = sqlite3.connect(_LEGACY_DB_PATH)
        legacy_conn.row_factory = sqlite3.Row
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

    key = make_institution_key(wilaya_code, institution_type, institution_name)
    paths = profile_paths(key)
    os.makedirs(paths["folder"], exist_ok=True)
    os.makedirs(os.path.join(paths["folder"], "archives"), exist_ok=True)

    # Move (not copy) the legacy db and archive folders into the new location
    shutil.move(_LEGACY_DB_PATH, paths["db"])
    if os.path.isdir(_LEGACY_ARCHIVE_SORTANT):
        shutil.move(_LEGACY_ARCHIVE_SORTANT, paths["sortant"])
    if os.path.isdir(_LEGACY_ARCHIVE_ENTRANT):
        shutil.move(_LEGACY_ARCHIVE_ENTRANT, paths["entrant"])

    registry_conn = get_registry_db()
    registry_conn.execute("""
        INSERT INTO profiles (institution_key, wilaya_code, wilaya_name,
                               institution_type, institution_name, serial_key,
                               pin_hash, theme, created_at)
        VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
    """, (key, wilaya_code, wilaya_name, institution_type, institution_name,
          serial_key, theme, datetime.now().isoformat()))
    registry_conn.commit()
    registry_conn.close()
    legacy_conn.close()

    print(f"[migration] Legacy profile '{institution_name}' migrated to profiles/{key}/ "
          f"— a PIN must be set on first unlock.")


migrate_legacy_single_tenant_if_needed()


# --------------------------------------------------------------------------- #
# Active session — single in-memory value (see concurrency note at top).
# --------------------------------------------------------------------------- #
_active_key = None


def require_active_profile():
    """Returns the active profile's registry row, or None if locked."""
    if _active_key is None:
        return None
    return get_profile_row(_active_key)


def locked_response():
    return jsonify({"error": "Session verrouillée. Veuillez entrer votre code PIN.",
                     "locked": True}), 423


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

    conn = get_registry_db()
    conn.execute("UPDATE profiles SET pin_hash = ? WHERE institution_key = ?",
                 (generate_password_hash(pin), key))
    conn.commit()
    conn.close()

    global _active_key
    _active_key = key
    return jsonify({"ok": True, "profile": profile_public_dict(get_profile_row(key))})


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
    if not check_password_hash(row["pin_hash"], pin):
        return jsonify({"error": "Code PIN incorrect."}), 401

    global _active_key
    _active_key = key
    return jsonify({"ok": True, "profile": profile_public_dict(row)})


@app.route("/api/session/lock", methods=["POST"])
def api_session_lock():
    """Locks the workspace (the 'logout' action) WITHOUT deleting any data —
    switching institutions must never show a previous institution's
    archives, but it also must never destroy them."""
    global _active_key
    _active_key = None
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
    pin = data.get("pin", "")

    if not institution_name or institution_type not in INSTITUTION_TYPES:
        return jsonify({"error": "Champs invalides."}), 400
    if not re.fullmatch(r"\d{4,6}", pin):
        return jsonify({"error": "Le code PIN doit contenir 4 à 6 chiffres."}), 400

    wilaya_name = dict(WILAYAS).get(wilaya_code)
    if wilaya_name is None:
        return jsonify({"error": "Wilaya invalide."}), 400

    key = make_institution_key(wilaya_code, institution_type, institution_name)
    serial_key = generate_serial_key(wilaya_code, institution_type, institution_name)

    conn = get_registry_db()
    conn.execute("""
        INSERT INTO profiles (institution_key, wilaya_code, wilaya_name,
                               institution_type, institution_name, serial_key,
                               pin_hash, theme, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'dark', ?)
    """, (key, wilaya_code, wilaya_name, institution_type, institution_name,
          serial_key, generate_password_hash(pin), datetime.now().isoformat()))
    conn.commit()
    conn.close()

    # Ensure the isolated storage folder exists immediately
    get_profile_db(key).close()

    global _active_key
    _active_key = key
    return jsonify({"ok": True, "profile": profile_public_dict(get_profile_row(key))})


@app.route("/api/profile/theme", methods=["POST"])
def api_set_theme():
    if _active_key is None:
        return locked_response()
    data = request.get_json(force=True)
    theme = data.get("theme", "dark")
    if theme not in ("dark", "light"):
        return jsonify({"error": "Thème invalide."}), 400
    conn = get_registry_db()
    conn.execute("UPDATE profiles SET theme = ? WHERE institution_key = ?", (theme, _active_key))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- #
# API — Dashboard (scoped to the active profile)
# --------------------------------------------------------------------------- #
@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    if _active_key is None:
        return locked_response()
    conn = get_profile_db(_active_key)
    sent = conn.execute("SELECT COUNT(*) c FROM messages WHERE direction='sortant'").fetchone()["c"]
    received = conn.execute("SELECT COUNT(*) c FROM messages WHERE direction='entrant'").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) c FROM messages WHERE status='en_attente'").fetchone()["c"]
    recent = conn.execute("SELECT * FROM messages ORDER BY created_at DESC LIMIT 15").fetchall()
    conn.close()
    return jsonify({
        "total_sent": sent,
        "total_received": received,
        "pending": pending,
        "recent": [dict(r) for r in recent],
    })


# --------------------------------------------------------------------------- #
# API — Messaging (scoped to the active profile)
# --------------------------------------------------------------------------- #
@app.route("/api/messages", methods=["GET"])
def api_list_messages():
    if _active_key is None:
        return locked_response()
    direction = request.args.get("direction", "sortant")
    conn = get_profile_db(_active_key)
    rows = conn.execute(
        "SELECT * FROM messages WHERE direction = ? ORDER BY created_at DESC",
        (direction,)
    ).fetchall()
    conn.close()
    return jsonify({"messages": [dict(r) for r in rows]})


@app.route("/api/messages/send", methods=["POST"])
def api_send_message():
    if _active_key is None:
        return locked_response()

    recipient = request.form.get("recipient", "").strip()
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

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = sanitize(sender).replace(" ", "")[:30]
    safe_name = sanitize(secure_filename(file.filename) or "document")
    archived_name = f"{ts}_{tag}_{safe_name}"
    archived_path = os.path.join(paths["sortant"], archived_name)
    file.save(archived_path)

    conn = get_profile_db(_active_key)
    tracking = next_tracking_number(conn, "sortant")
    conn.execute("""
        INSERT INTO messages (direction, tracking_number, sender_institution,
                               recipient_institution, subject, body, file_path,
                               file_original_name, status, created_at)
        VALUES ('sortant', ?, ?, ?, ?, ?, ?, ?, 'envoye', ?)
    """, (tracking, sender, recipient, subject, body, archived_path,
          file.filename, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "tracking_number": tracking})


@app.route("/api/messages/<int:message_id>/download", methods=["GET"])
def api_download_message(message_id):
    if _active_key is None:
        return locked_response()
    conn = get_profile_db(_active_key)
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    conn.close()
    if row is None or not row["file_path"] or not os.path.exists(row["file_path"]):
        abort(404)
    return send_file(row["file_path"], as_attachment=True,
                      download_name=row["file_original_name"] or "document")


@app.route("/api/messages/<int:message_id>/status", methods=["POST"])
def api_update_message_status(message_id):
    if _active_key is None:
        return locked_response()
    data = request.get_json(force=True)
    status = data.get("status", "").strip()
    if status not in ("envoye", "recu", "accuse", "en_attente"):
        return jsonify({"error": "Statut invalide."}), 400

    conn = get_profile_db(_active_key)
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "Message introuvable."}), 404

    conn.execute("UPDATE messages SET status = ? WHERE id = ?", (status, message_id))
    conn.commit()
    updated = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    conn.close()
    return jsonify({"ok": True, "message": dict(updated)})


@app.route("/api/messages/<int:message_id>", methods=["DELETE"])
def api_delete_message(message_id):
    if _active_key is None:
        return locked_response()
    conn = get_profile_db(_active_key)
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "Message introuvable."}), 404

    file_path = row["file_path"]
    conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()

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
    conn = get_profile_db(_active_key)
    if direction == "tous":
        rows = conn.execute("SELECT * FROM messages ORDER BY created_at DESC").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM messages WHERE direction = ? ORDER BY created_at DESC",
            (direction,)
        ).fetchall()
    conn.close()
    return jsonify({"entries": [dict(r) for r in rows]})


if __name__ == "__main__":
    print(f"TASHIL DOCUMENT HUB — Web Edition v{APP_VERSION}")
    print(f"Local  : http://127.0.0.1:5000/")
    print(f"Réseau : http://{get_lan_ip()}:5000/  (accessible depuis un téléphone sur le même Wi-Fi)")
    app.run(host="0.0.0.0", port=5000, debug=False)
