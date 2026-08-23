# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — config.py
Branding, wilayas, institution types, global constants.
Copyright ILINE TECH 2026 BY FERAK ALADDIN
"""

APP_NAME = "TASHIL"
APP_FULL_NAME = "TASHIL DOCUMENT HUB"
APP_VERSION = "1.0.0"
APP_FLAG = "🇩🇿"
EXECUTABLE_NAME = "TASHIL_DOCUMENT.exe"

GITHUB_OWNER = "Aladdinweb"
GITHUB_REPO = "TASHIL-Hub"
GITHUB_API_RELEASES = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

# Root archive folder (CRUCIAL — always under C:\TASHIL)
ARCHIVE_ROOT = r"C:\TASHIL\TASHIL_ARCHIVES"
ARCHIVE_SORTANT = r"C:\TASHIL\TASHIL_ARCHIVES\Courrier_Sortant"
ARCHIVE_ENTRANT = r"C:\TASHIL\TASHIL_ARCHIVES\Courrier_Entrant"

# Local app data (profile, db, config) — separate from archive
APP_DATA_DIR = r"C:\TASHIL\AppData"
DB_PATH = r"C:\TASHIL\AppData\tashil.db"
PROFILE_PATH = r"C:\TASHIL\AppData\profile.json"

# 58 Algerian wilayas (code, name)
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

# Institution types
INSTITUTION_TYPES = ["EPSP", "EPH", "CHU", "EHU", "Polyclinique"]

# Notification defaults
NOTIF_SOUND_ENABLED_DEFAULT = True
NOTIF_TOAST_ENABLED_DEFAULT = True

# Phone bridge
PHONE_BRIDGE_PORT = 8842

# Languages
LANGUAGES = ["Français", "العربية"]
