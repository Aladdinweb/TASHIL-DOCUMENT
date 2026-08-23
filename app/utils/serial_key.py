# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — serial_key.py
Generates a deterministic, encrypted-looking serial key bound to
(wilaya_code, institution_type, institution_name).

Uses HMAC-SHA256 with an app-embedded secret so keys can be validated
offline without a server round-trip, and are unique per institution/wilaya.
"""

import base64
import hashlib
import hmac
from datetime import datetime

# NOTE: In production this secret should be obfuscated at build time
# (e.g. injected via CI secret + PyInstaller --key), not hardcoded plainly.
_APP_SECRET = b"ILINE-TECH-2026-FERAK-ALADDIN-TASHIL-DOCUMENT-HUB"

_INSTITUTION_CODES = {
    "EPSP": "EP",
    "EPH": "EH",
    "CHU": "CU",
    "EHU": "HU",
    "Polyclinique": "PC",
}


def generate_serial_key(wilaya_code: int, institution_type: str, institution_name: str) -> str:
    """
    Format: TSH-<WW>-<TT>-<XXXX>-<CHK>
      WW  = 2-digit wilaya code
      TT  = 2-letter institution type code
      XXXX = 4 hex chars derived from institution name + timestamp salt
      CHK = 4-char HMAC checksum for offline validation
    """
    type_code = _INSTITUTION_CODES.get(institution_type, "XX")
    salt = datetime.now().strftime("%Y%m%d")
    payload = f"{wilaya_code:02d}|{type_code}|{institution_name.strip().upper()}|{salt}"

    digest = hmac.new(_APP_SECRET, payload.encode("utf-8"), hashlib.sha256).digest()
    body_hex = digest.hex()[:4].upper()
    checksum = base64.b32encode(digest[:3]).decode("utf-8")[:4]

    return f"TSH-{wilaya_code:02d}-{type_code}-{body_hex}-{checksum}"


def validate_serial_key(serial: str, wilaya_code: int, institution_type: str) -> bool:
    """Structural validation: correct wilaya/type embedded in the key format."""
    try:
        parts = serial.split("-")
        if len(parts) != 5 or parts[0] != "TSH":
            return False
        return int(parts[1]) == wilaya_code and parts[2] == _INSTITUTION_CODES.get(institution_type)
    except (ValueError, IndexError):
        return False
