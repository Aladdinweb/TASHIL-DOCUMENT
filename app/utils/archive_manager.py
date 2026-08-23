# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — archive_manager.py

Isolated local archive routing. EVERY file that is sent or received —
including phone-bridge scans — is copied into a standardized, timestamped
location under C:\\TASHIL\\TASHIL_ARCHIVES\\ so nothing is ever only
in-memory or only in the DB.

Naming convention: YYYYMMDD_HHMMSS_[INSTITUTION]_[FILENAME]
"""

import os
import re
import shutil
from datetime import datetime

from app.config import ARCHIVE_SORTANT, ARCHIVE_ENTRANT
from app.utils.database import get_profile


def _ensure_archive_dirs():
    os.makedirs(ARCHIVE_SORTANT, exist_ok=True)
    os.makedirs(ARCHIVE_ENTRANT, exist_ok=True)


def _sanitize(name: str) -> str:
    """Strip characters that are unsafe for Windows filenames."""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip() or "document"


def _current_institution_tag() -> str:
    profile = get_profile()
    if profile is None:
        return "TASHIL"
    raw = profile["institution_name"] or profile["institution_type"] or "TASHIL"
    return _sanitize(raw).replace(" ", "")[:30]


def _timestamped_name(original_filename: str, institution_tag: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_original = _sanitize(os.path.basename(original_filename))
    return f"{ts}_{institution_tag}_{safe_original}"


def archive_outgoing_file(source_path: str) -> str:
    """
    Copies a file selected for sending (drag-and-drop or file picker) into
    Courrier_Sortant with a standardized name. Returns the archived path.
    """
    _ensure_archive_dirs()
    institution_tag = _current_institution_tag()
    new_name = _timestamped_name(source_path, institution_tag)
    dest_path = os.path.join(ARCHIVE_SORTANT, new_name)
    shutil.copy2(source_path, dest_path)
    return dest_path


def archive_incoming_file(source_path: str, sender_institution: str = "") -> str:
    """
    Copies a downloaded/received file into Courrier_Entrant with a
    standardized name. Returns the archived path.
    """
    _ensure_archive_dirs()
    tag = _sanitize(sender_institution) if sender_institution else "EXTERNE"
    new_name = _timestamped_name(source_path, tag)
    dest_path = os.path.join(ARCHIVE_ENTRANT, new_name)
    shutil.copy2(source_path, dest_path)
    return dest_path


def save_incoming_from_phone(original_filename: str, file_bytes: bytes) -> str:
    """
    Used by phone_bridge.py: writes raw bytes pushed from a phone scan
    directly into Courrier_Sortant (it becomes an outgoing attachment
    once the user confirms sending it from the Envoi tab).
    """
    _ensure_archive_dirs()
    institution_tag = _current_institution_tag()
    new_name = _timestamped_name(original_filename, f"{institution_tag}_PHONE")
    dest_path = os.path.join(ARCHIVE_SORTANT, new_name)
    with open(dest_path, "wb") as f:
        f.write(file_bytes)
    return dest_path


def list_archive(direction: str) -> list[str]:
    """Returns the list of archived file paths for 'sortant' or 'entrant'."""
    _ensure_archive_dirs()
    folder = ARCHIVE_SORTANT if direction == "sortant" else ARCHIVE_ENTRANT
    return sorted(
        (os.path.join(folder, f) for f in os.listdir(folder)
         if os.path.isfile(os.path.join(folder, f))),
        reverse=True
    )


def get_archive_stats() -> dict:
    """Quick counts for the Dashboard cards."""
    _ensure_archive_dirs()
    sortant_count = len([f for f in os.listdir(ARCHIVE_SORTANT)
                          if os.path.isfile(os.path.join(ARCHIVE_SORTANT, f))])
    entrant_count = len([f for f in os.listdir(ARCHIVE_ENTRANT)
                          if os.path.isfile(os.path.join(ARCHIVE_ENTRANT, f))])
    return {"total_sortant": sortant_count, "total_entrant": entrant_count}
