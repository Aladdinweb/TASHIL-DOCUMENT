# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — theme.py
Centralized color palette and typography for Dark/Light modes.
"""

FONT_FAMILY = "Segoe UI"

FONTS = {
    "title": (FONT_FAMILY, 22, "bold"),
    "subtitle": (FONT_FAMILY, 15, "bold"),
    "body": (FONT_FAMILY, 13),
    "small": (FONT_FAMILY, 11),
    "button": (FONT_FAMILY, 13, "bold"),
}

COULEURS = {
    "Dark": {
        "bg": "#0F1419",
        "sidebar": "#161B22",
        "card": "#1C2128",
        "card_border": "#2D333B",
        "primary": "#00A651",       # Algerian green
        "primary_hover": "#00c261",
        "accent": "#D21034",        # Algerian red
        "text": "#E6EDF3",
        "text_muted": "#8B949E",
        "success": "#3FB950",
        "warning": "#D29922",
        "danger": "#F85149",
        "input_bg": "#0D1117",
    },
    "Light": {
        "bg": "#F5F7FA",
        "sidebar": "#FFFFFF",
        "card": "#FFFFFF",
        "card_border": "#E2E8F0",
        "primary": "#00A651",
        "primary_hover": "#008f45",
        "accent": "#D21034",
        "text": "#1A202C",
        "text_muted": "#64748B",
        "success": "#22863A",
        "warning": "#B08800",
        "danger": "#CB2431",
        "input_bg": "#F1F5F9",
    },
}


def get_palette(mode: str) -> dict:
    """Return the color dict for the given appearance mode ('Dark' or 'Light')."""
    return COULEURS.get(mode, COULEURS["Dark"])
