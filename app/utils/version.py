# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — version.py
Single source of truth for the app version. Patched automatically by CI.
"""

VERSION = "1.0.0"
BUILD_CHANNEL = "stable"


def get_version() -> str:
    return VERSION
