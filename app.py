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
import uuid
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
APP_VERSION = "2.4.0"
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


def next_tracking_number(conn, direction: str, institution_key: str) -> str:
    """
    Tracking numbers now embed a short institution code (derived from the
    wilaya+type prefix of institution_key) so that a number generated by
    one institution's database doesn't collide with an unrelated message
    already present in another institution's database when a message is
    delivered locally (see find_local_profile_by_name / api_send_message).
    """
    prefix = "S" if direction == "sortant" else "E"
    year = datetime.now().year
    count = conn.execute(
        "SELECT COUNT(*) as c FROM messages WHERE direction = ?", (direction,)
    ).fetchone()["c"]
    short = "".join(institution_key.split("_")[:2]) or "XX"
    return f"TASHIL-{short}-{prefix}-{year}-{count + 1:06d}"


def find_local_profile_by_name(institution_name: str, exclude_key: str = None):
    """
    Looks for another profile registered on THIS device whose institution
    name matches the given recipient string (case/whitespace-insensitive).
    Used to deliver a message locally when both sender and recipient are
    profiles on the same machine. Returns None if no match — this does
    NOT reach across a network to a different computer; see the honesty
    note in api_send_message().
    """
    conn = get_registry_db()
    rows = conn.execute("SELECT * FROM profiles").fetchall()
    conn.close()
    target = institution_name.strip().casefold()
    for row in rows:
        if row["institution_key"] == exclude_key:
            continue
        if row["institution_name"].strip().casefold() == target:
            return dict(row)
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
    """
    import urllib.request
    import urllib.error

    url = url_or_path if url_or_path.startswith("http") else f"{GITHUB_API_BASE}{url_or_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "TASHIL-DOCUMENT-HUB",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = json.dumps(json_body).encode("utf-8") if json_body is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
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
    conn = get_registry_db()
    row = conn.execute("SELECT * FROM bridge_config WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else None


def bridge_slug(institution_name: str) -> str:
    """
    Normalizes an institution name into a stable Cloud Bridge address.
    ⚠️ Name-only, no wilaya/type disambiguation — two different real
    institutions that happen to share an identical name would collide on
    the same bridge folder. Same limitation as local delivery matching
    (find_local_profile_by_name) for consistency; worth revisiting if the
    recipient picker ever becomes a structured Wilaya+Type+Name selection
    instead of free text.
    """
    return re.sub(r'[^A-Za-z0-9]+', '_', institution_name.strip().upper()).strip('_')[:80]


def push_to_bridge(cfg: dict, recipient_name: str, sender_name: str, subject: str,
                    body: str, tracking: str, file_path: str, original_filename: str) -> bool:
    owner, repo, token = cfg["github_owner"], cfg["github_repo"], cfg["github_token"]
    key = bridge_slug(recipient_name)

    file_ext = os.path.splitext(original_filename)[1]
    attachment_repo_path = f"bridge/{key}/{tracking}{file_ext}"
    meta_repo_path = f"bridge/{key}/{tracking}.json"

    meta = {
        "tracking_number": tracking,
        "sender_institution": sender_name,
        "recipient_institution": recipient_name,
        "subject": subject,
        "body": body,
        "file_original_name": original_filename,
        "attachment_path_in_repo": attachment_repo_path,
        "created_at": datetime.now().isoformat(),
    }

    try:
        with open(file_path, "rb") as f:
            file_b64 = base64.b64encode(f.read()).decode("utf-8")
    except OSError:
        return False

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
    tracking = next_tracking_number(conn, "sortant", _active_key)
    conn.execute("""
        INSERT INTO messages (direction, tracking_number, sender_institution,
                               recipient_institution, subject, body, file_path,
                               file_original_name, status, created_at)
        VALUES ('sortant', ?, ?, ?, ?, ?, ?, ?, 'envoye', ?)
    """, (tracking, sender, recipient, subject, body, archived_path,
          file.filename, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    # --------------------------------------------------------------- #
    # Local delivery: if the recipient happens to be another profile
    # registered on THIS SAME DEVICE, actually deliver the message into
    # its inbox (own isolated database + archive). This does NOT reach
    # a different computer on the network — that is a separate feature
    # (LAN push / Cloud Bridge) not yet built. See STATE.md.
    # --------------------------------------------------------------- #
    delivered_locally = False
    recipient_profile = find_local_profile_by_name(recipient, exclude_key=_active_key)
    if recipient_profile is not None:
        try:
            recipient_key = recipient_profile["institution_key"]
            recipient_paths = profile_paths(recipient_key)
            recipient_archived_path = os.path.join(recipient_paths["entrant"], archived_name)
            shutil.copy2(archived_path, recipient_archived_path)

            recipient_conn = get_profile_db(recipient_key)
            recipient_tracking = tracking
            try:
                recipient_conn.execute("""
                    INSERT INTO messages (direction, tracking_number, sender_institution,
                                           recipient_institution, subject, body, file_path,
                                           file_original_name, status, created_at)
                    VALUES ('entrant', ?, ?, ?, ?, ?, ?, ?, 'envoye', ?)
                """, (recipient_tracking, sender, recipient, subject, body,
                      recipient_archived_path, file.filename, datetime.now().isoformat()))
            except sqlite3.IntegrityError:
                # Extremely rare tracking-number collision across two
                # independent institution databases — disambiguate and retry.
                recipient_tracking = f"{tracking}-{uuid.uuid4().hex[:4].upper()}"
                recipient_conn.execute("""
                    INSERT INTO messages (direction, tracking_number, sender_institution,
                                           recipient_institution, subject, body, file_path,
                                           file_original_name, status, created_at)
                    VALUES ('entrant', ?, ?, ?, ?, ?, ?, ?, 'envoye', ?)
                """, (recipient_tracking, sender, recipient, subject, body,
                      recipient_archived_path, file.filename, datetime.now().isoformat()))
            recipient_conn.commit()
            recipient_conn.close()
            delivered_locally = True
        except Exception:
            # Never fail the whole send just because local delivery hit an
            # issue — the sender's own record above is already saved.
            delivered_locally = False

    # --------------------------------------------------------------- #
    # Cloud Bridge fallback: only attempted when no local profile matched
    # (a local match always takes precedence — see find_local_profile_by_name
    # docstring). Never fails the overall send; the sender's own record is
    # already safely saved regardless of bridge outcome.
    # --------------------------------------------------------------- #
    delivered_via_bridge = False
    bridge_attempted = False
    if not delivered_locally:
        bridge_cfg = get_bridge_config()
        if bridge_cfg and bridge_cfg["enabled"]:
            bridge_attempted = True
            try:
                delivered_via_bridge = push_to_bridge(
                    bridge_cfg, recipient, sender, subject, body,
                    tracking, archived_path, file.filename
                )
            except Exception:
                delivered_via_bridge = False

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


# --------------------------------------------------------------------------- #
# API — Cloud Bridge configuration & manual poll
# --------------------------------------------------------------------------- #
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


@app.route("/api/bridge/config", methods=["POST"])
def api_bridge_save_config():
    data = request.get_json(force=True)
    owner = data.get("github_owner", "").strip()
    repo = data.get("github_repo", "").strip()
    token = data.get("github_token", "").strip()

    if not owner or not repo or not token:
        return jsonify({"error": "Propriétaire, dépôt et jeton GitHub sont tous requis."}), 400

    status, repo_info = _github_request("GET", f"/repos/{owner}/{repo}", token)
    if status == 0:
        return jsonify({"error": f"Impossible de contacter GitHub : {repo_info.get('message', 'réseau indisponible')}"}), 502
    if status == 401:
        return jsonify({"error": "Jeton GitHub invalide ou expiré."}), 401
    if status == 404:
        return jsonify({"error": "Dépôt introuvable (ou le jeton n'y a pas accès)."}), 404
    if status != 200:
        return jsonify({"error": f"Erreur GitHub inattendue ({status})."}), 502

    if repo_info.get("private") is not True:
        return jsonify({
            "error": "Ce dépôt est PUBLIC. TASHIL refuse d'y transmettre des documents. "
                     "Utilisez un dépôt privé dédié."
        }), 400

    conn = get_registry_db()
    conn.execute("""
        INSERT INTO bridge_config (id, github_owner, github_repo, github_token, enabled, updated_at)
        VALUES (1, ?, ?, ?, 1, ?)
        ON CONFLICT(id) DO UPDATE SET
            github_owner=excluded.github_owner, github_repo=excluded.github_repo,
            github_token=excluded.github_token, enabled=1, updated_at=excluded.updated_at
    """, (owner, repo, token, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "private_verified": True})


@app.route("/api/bridge/disable", methods=["POST"])
def api_bridge_disable():
    conn = get_registry_db()
    conn.execute("UPDATE bridge_config SET enabled = 0 WHERE id = 1")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/bridge/poll", methods=["POST"])
def api_bridge_poll():
    """
    Checks the Cloud Bridge repo for new messages addressed to the
    CURRENTLY ACTIVE profile, downloads and inserts any found into that
    profile's own isolated database + archive, then removes the consumed
    entries from the bridge repo. Safe to call repeatedly — already-seen
    tracking numbers are skipped.
    """
    if _active_key is None:
        return locked_response()

    cfg = get_bridge_config()
    if not cfg or not cfg["enabled"]:
        return jsonify({"ok": True, "bridge_enabled": False, "new_messages": 0})

    profile = get_profile_row(_active_key)
    owner, repo, token = cfg["github_owner"], cfg["github_repo"], cfg["github_token"]
    key = bridge_slug(profile["institution_name"])

    status, listing = _github_request("GET", f"/repos/{owner}/{repo}/contents/bridge/{key}", token)
    if status == 404:
        return jsonify({"ok": True, "bridge_enabled": True, "new_messages": 0})
    if status != 200:
        return jsonify({"error": f"Erreur GitHub ({status})."}), 502

    json_entries = [f for f in listing if f["name"].endswith(".json")]
    conn = get_profile_db(_active_key)
    paths = profile_paths(_active_key)
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
            with open(local_path, "wb") as f:
                f.write(file_bytes)
        except OSError:
            continue

        conn.execute("""
            INSERT INTO messages (direction, tracking_number, sender_institution,
                                   recipient_institution, subject, body, file_path,
                                   file_original_name, status, created_at)
            VALUES ('entrant', ?, ?, ?, ?, ?, ?, ?, 'envoye', ?)
        """, (meta["tracking_number"], meta.get("sender_institution", "?"),
              meta.get("recipient_institution", profile["institution_name"]),
              meta.get("subject", ""), meta.get("body", ""), local_path,
              meta.get("file_original_name", "document"),
              meta.get("created_at", datetime.now().isoformat())))
        conn.commit()
        new_count += 1

        # Clean up consumed entries so the bridge queue doesn't grow forever
        _github_request("DELETE", entry["url"], token,
                         {"message": f"TASHIL bridge: consumed {meta['tracking_number']}",
                          "sha": entry["sha"]})
        _github_request("DELETE", f"/repos/{owner}/{repo}/contents/{meta['attachment_path_in_repo']}", token,
                         {"message": f"TASHIL bridge: consumed attachment {meta['tracking_number']}",
                          "sha": attach_content["sha"]})

    conn.close()
    return jsonify({"ok": True, "bridge_enabled": True, "new_messages": new_count})


if __name__ == "__main__":
    print(f"TASHIL DOCUMENT HUB — Web Edition v{APP_VERSION}")
    print(f"Local  : http://127.0.0.1:5000/")
    print(f"Réseau : http://{get_lan_ip()}:5000/  (accessible depuis un téléphone sur le même Wi-Fi)")
    app.run(host="0.0.0.0", port=5000, debug=False)
