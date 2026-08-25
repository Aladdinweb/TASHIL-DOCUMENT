# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — WEB EDITION
Copyright ILINE TECH 2026 BY FERAK ALADDIN

A single Python backend that serves a normal responsive web page —
identical on Windows and on Android (Termux). No custom window chrome,
no manual widget positioning: the browser handles all layout.

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
from datetime import datetime

from flask import (Flask, request, jsonify, send_from_directory,
                    send_file, render_template, abort)
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------- #
# Paths — cross-platform, no admin rights required (works on Windows AND
# Termux/Android identically, unlike the old C:\TASHIL\... hardcoded paths).
# --------------------------------------------------------------------------- #
BASE_DIR = os.path.join(os.path.expanduser("~"), "TASHIL_DATA")
ARCHIVE_SORTANT = os.path.join(BASE_DIR, "archives", "Courrier_Sortant")
ARCHIVE_ENTRANT = os.path.join(BASE_DIR, "archives", "Courrier_Entrant")
DB_PATH = os.path.join(BASE_DIR, "tashil.db")

os.makedirs(ARCHIVE_SORTANT, exist_ok=True)
os.makedirs(ARCHIVE_ENTRANT, exist_ok=True)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
            template_folder=os.path.join(APP_ROOT, "templates"),
            static_folder=os.path.join(APP_ROOT, "static"))
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64MB upload cap

INSTITUTION_TYPES = ["EPSP", "EPH", "CHU", "EHU", "Polyclinique"]
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
# Database
# --------------------------------------------------------------------------- #
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            wilaya_code INTEGER NOT NULL,
            wilaya_name TEXT NOT NULL,
            institution_type TEXT NOT NULL,
            institution_name TEXT NOT NULL,
            serial_key TEXT NOT NULL,
            theme TEXT DEFAULT 'dark',
            created_at TEXT NOT NULL
        )
    """)
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
    conn.commit()
    conn.close()


init_db()


def sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip() or "document"


def get_profile():
    conn = get_db()
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else None


def next_tracking_number(direction: str) -> str:
    conn = get_db()
    prefix = "S" if direction == "sortant" else "E"
    year = datetime.now().year
    count = conn.execute(
        "SELECT COUNT(*) as c FROM messages WHERE direction = ?", (direction,)
    ).fetchone()["c"]
    conn.close()
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
# Page routes
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/manifest.json")
def manifest():
    return send_from_directory(app.static_folder, "manifest.json",
                                mimetype="application/manifest+json")


# --------------------------------------------------------------------------- #
# API — Profile / onboarding
# --------------------------------------------------------------------------- #
@app.route("/api/meta", methods=["GET"])
def api_meta():
    return jsonify({
        "wilayas": WILAYAS,
        "institution_types": INSTITUTION_TYPES,
        "lan_url": f"http://{get_lan_ip()}:5000/",
    })


@app.route("/api/profile", methods=["GET"])
def api_get_profile():
    profile = get_profile()
    return jsonify({"profile": profile, "first_launch": profile is None})


@app.route("/api/profile", methods=["POST"])
def api_save_profile():
    data = request.get_json(force=True)
    wilaya_code = int(data.get("wilaya_code"))
    institution_type = data.get("institution_type", "").strip()
    institution_name = data.get("institution_name", "").strip()

    if not institution_name or institution_type not in INSTITUTION_TYPES:
        return jsonify({"error": "Champs invalides."}), 400

    wilaya_name = dict(WILAYAS).get(wilaya_code)
    if wilaya_name is None:
        return jsonify({"error": "Wilaya invalide."}), 400

    import hashlib, hmac, base64
    secret = b"ILINE-TECH-2026-FERAK-ALADDIN-TASHIL-DOCUMENT-HUB"
    type_codes = {"EPSP": "EP", "EPH": "EH", "CHU": "CU", "EHU": "HU", "Polyclinique": "PC"}
    type_code = type_codes.get(institution_type, "XX")
    salt = datetime.now().strftime("%Y%m%d")
    payload = f"{wilaya_code:02d}|{type_code}|{institution_name.upper()}|{salt}"
    digest = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).digest()
    body_hex = digest.hex()[:4].upper()
    checksum = base64.b32encode(digest[:3]).decode("utf-8")[:4]
    serial_key = f"TSH-{wilaya_code:02d}-{type_code}-{body_hex}-{checksum}"

    conn = get_db()
    conn.execute("""
        INSERT INTO profile (id, wilaya_code, wilaya_name, institution_type,
                              institution_name, serial_key, created_at)
        VALUES (1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            wilaya_code=excluded.wilaya_code, wilaya_name=excluded.wilaya_name,
            institution_type=excluded.institution_type,
            institution_name=excluded.institution_name
    """, (wilaya_code, wilaya_name, institution_type, institution_name,
          serial_key, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"profile": get_profile()})


@app.route("/api/profile/theme", methods=["POST"])
def api_set_theme():
    data = request.get_json(force=True)
    theme = data.get("theme", "dark")
    if theme not in ("dark", "light"):
        return jsonify({"error": "Thème invalide."}), 400
    conn = get_db()
    conn.execute("UPDATE profile SET theme = ? WHERE id = 1", (theme,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- #
# API — Dashboard
# --------------------------------------------------------------------------- #
@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    conn = get_db()
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
# API — Messaging
# --------------------------------------------------------------------------- #
@app.route("/api/messages", methods=["GET"])
def api_list_messages():
    direction = request.args.get("direction", "sortant")
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM messages WHERE direction = ? ORDER BY created_at DESC",
        (direction,)
    ).fetchall()
    conn.close()
    return jsonify({"messages": [dict(r) for r in rows]})


@app.route("/api/messages/send", methods=["POST"])
def api_send_message():
    recipient = request.form.get("recipient", "").strip()
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()
    file = request.files.get("file")

    if not recipient:
        return jsonify({"error": "Institution destinataire requise."}), 400
    if not file or file.filename == "":
        return jsonify({"error": "Un fichier est requis."}), 400

    profile = get_profile()
    sender = profile["institution_name"] if profile else "TASHIL"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = sanitize(sender).replace(" ", "")[:30]
    safe_name = sanitize(secure_filename(file.filename) or "document")
    archived_name = f"{ts}_{tag}_{safe_name}"
    archived_path = os.path.join(ARCHIVE_SORTANT, archived_name)
    file.save(archived_path)

    tracking = next_tracking_number("sortant")
    conn = get_db()
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
    conn = get_db()
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    conn.close()
    if row is None or not row["file_path"] or not os.path.exists(row["file_path"]):
        abort(404)
    return send_file(row["file_path"], as_attachment=True,
                      download_name=row["file_original_name"] or "document")


# --------------------------------------------------------------------------- #
# API — Registry (Administration)
# --------------------------------------------------------------------------- #
@app.route("/api/registre", methods=["GET"])
def api_registre():
    direction = request.args.get("direction", "tous")
    conn = get_db()
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
    print(f"TASHIL DOCUMENT HUB — Web Edition")
    print(f"Local  : http://127.0.0.1:5000/")
    print(f"Réseau : http://{get_lan_ip()}:5000/  (accessible depuis un téléphone sur le même Wi-Fi)")
    app.run(host="0.0.0.0", port=5000, debug=False)
