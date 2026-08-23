# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — database.py
SQLite schema init. MUST be called BEFORE ctk.CTk() to avoid black-screen bugs.
"""

import os
import sqlite3
from datetime import datetime

from app.config import DB_PATH, APP_DATA_DIR

_connection = None


def get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        _connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA foreign_keys = ON")
    return _connection


def initialize_database() -> None:
    """Create all tables if they don't exist yet. Idempotent — safe to call every launch."""
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            wilaya_code INTEGER NOT NULL,
            wilaya_name TEXT NOT NULL,
            institution_type TEXT NOT NULL,
            institution_name TEXT NOT NULL,
            serial_key TEXT NOT NULL,
            language TEXT DEFAULT 'Français',
            appearance_mode TEXT DEFAULT 'Dark',
            notif_toast INTEGER DEFAULT 1,
            notif_sound INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            direction TEXT NOT NULL,               -- 'sortant' or 'entrant'
            tracking_number TEXT UNIQUE NOT NULL,
            sender_institution TEXT,
            recipient_institution TEXT,
            subject TEXT,
            body TEXT,
            file_path TEXT,
            file_original_name TEXT,
            status TEXT DEFAULT 'en_attente',       -- en_attente, envoye, recu, echec
            is_read INTEGER DEFAULT 0,
            source TEXT DEFAULT 'pc',               -- 'pc' or 'phone_bridge'
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS registre_courrier (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_number TEXT UNIQUE NOT NULL,
            type_courrier TEXT NOT NULL,            -- 'entrant' or 'sortant'
            institution_partenaire TEXT,
            objet TEXT,
            date_enregistrement TEXT NOT NULL,
            message_id INTEGER,
            FOREIGN KEY (message_id) REFERENCES messages(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS phone_bridge_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            original_name TEXT NOT NULL,
            received_at TEXT NOT NULL,
            consumed INTEGER DEFAULT 0
        )
    """)

    conn.commit()


def is_first_launch() -> bool:
    """True if no profile row exists yet -> triggers the onboarding wizard."""
    conn = get_connection()
    row = conn.execute("SELECT id FROM profile WHERE id = 1").fetchone()
    return row is None


def save_profile(wilaya_code, wilaya_name, institution_type, institution_name, serial_key) -> None:
    conn = get_connection()
    conn.execute("""
        INSERT INTO profile (id, wilaya_code, wilaya_name, institution_type,
                              institution_name, serial_key, created_at)
        VALUES (1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            wilaya_code=excluded.wilaya_code,
            wilaya_name=excluded.wilaya_name,
            institution_type=excluded.institution_type,
            institution_name=excluded.institution_name,
            serial_key=excluded.serial_key
    """, (wilaya_code, wilaya_name, institution_type, institution_name,
          serial_key, datetime.now().isoformat()))
    conn.commit()


def get_profile() -> sqlite3.Row | None:
    conn = get_connection()
    return conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()


def update_profile_field(field: str, value) -> None:
    allowed = {"language", "appearance_mode", "notif_toast", "notif_sound",
               "institution_name"}
    if field not in allowed:
        raise ValueError(f"Champ non autorisé: {field}")
    conn = get_connection()
    conn.execute(f"UPDATE profile SET {field} = ? WHERE id = 1", (value,))
    conn.commit()


def next_tracking_number(direction: str) -> str:
    """Generate a sequential-looking tracking number, e.g. TASHIL-S-2026-000042."""
    conn = get_connection()
    prefix = "S" if direction == "sortant" else "E"
    year = datetime.now().year
    count = conn.execute(
        "SELECT COUNT(*) as c FROM messages WHERE direction = ?", (direction,)
    ).fetchone()["c"]
    return f"TASHIL-{prefix}-{year}-{count + 1:06d}"
