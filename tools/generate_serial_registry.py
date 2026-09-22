# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — tools/generate_serial_registry.py
Copyright ILINE TECH 2026 BY FERAK ALADDIN

v2.8.5 — Generates the national ILINE TECH reference registry of every
institution's recovery serial_key.

⚠️ v2.8.5.1 fix: the first version of this script covered ONLY DSP and
EPSP — a real gap found in production, since Polycliniques, EPH, and
CHU are also real, onboardable institution types (SECRETARIAT-only) with
no way to recover a forgotten PIN if they're missing from this registry.
Now covers every type in app.py's INSTITUTION_TYPES: DSP (2 roles),
EPSP (4 roles), EPH and generic Polyclinique (1 role each, per wilaya),
CHU (1 role, only for wilayas that have one), PLUS every REAL, specif-
ically-named Oran polyclinic (app.py's _REAL_ESSENIA_POLYCLINICS) under
its own name — since those are the ones actually onboarded in practice,
not the generic "Polyclinique <Wilaya>" placeholder.

⚠️⚠️⚠️ READ BEFORE RUNNING — THIS FILE'S OUTPUT IS SENSITIVE ⚠️⚠️⚠️

The exported registry is, in aggregate, a "skeleton key" list for the
entire national network: anyone holding it can reset the PIN and take
over any institution's poste via /api/session/recover. This is exactly
the concentration-of-risk problem this project already refused once,
for a single shared admin password (see STATE.md v2.5.0, section 13.1)
— an aggregated *export* of per-institution keys carries the same risk
if it isn't handled with real care, even though each individual key
only ever unlocks ONE institution.

Concretely, this means:
  1. NEVER commit the generated .xlsx/.md files to git — TASHIL-DOCUMENT
     is a PUBLIC repository. Add them to .gitignore if you keep this
     script's output anywhere near the repo working directory.
  2. NEVER email this file or put it on a shared drive without access
     control. Treat it like you'd treat a spreadsheet of every
     institution's admin password, because that's functionally what it
     is for the "forgot PIN" flow.
  3. Set a REAL, private TASHIL_HMAC_SECRET (see app.py) before running
     this script for anything beyond local testing. Without it, this
     script falls back to the SAME default secret already sitting in
     app.py's public source — meaning the "secret" issued has zero
     actual secrecy from anyone who reads the public repo.
  4. This script is meant to be run ONCE by ILINE TECH centrally, ahead
     of field deployment — not distributed to individual postes, and
     not bundled into the Windows .exe (it is deliberately absent from
     tashil_web.spec).

Usage:
    export TASHIL_HMAC_SECRET="a-real-private-secret-never-committed"
    python tools/generate_serial_registry.py [--output-dir DIR]

Requires openpyxl (already a project dependency via requirements.txt's
transitive needs is NOT guaranteed — install separately if missing:
    pip install openpyxl
"""

import argparse
import os
import sys
from datetime import datetime

# Make the project root (one level up from tools/) importable so this
# script can reuse the EXACT SAME functions app.py uses for real
# onboarding — WILAYAS, allowed_roles(), generate_serial_key() — rather
# than re-implementing (and risking silently diverging from) that logic.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import app as tashil_app  # noqa: E402


SECURITY_BANNER = (
    "⚠️ DOCUMENT CONFIDENTIEL — REGISTRE DE RÉCUPÉRATION ILINE TECH ⚠️  "
    "Ne jamais publier, commiter sur un dépôt Git, ou partager sans "
    "contrôle d'accès. Chaque clé série permet de réinitialiser l'accès "
    "de l'établissement correspondant."
)


def build_registry_rows():
    """
    Returns a list of dicts, one per (institution, role) combination:
    wilaya_code, wilaya_name, institution_type, institution_name, role,
    serial_key. Uses the real generate_serial_key() from app.py, so a
    row here is guaranteed to match what /api/profile will actually
    store when that institution is really onboarded on its own machine
    — as long as TASHIL_HMAC_SECRET is set identically in both places.
    """
    rows = []
    for wilaya_code, wilaya_name in tashil_app.WILAYAS:
        # DSP — one per wilaya, matches the app's own onboarding directory
        # naming ("DSP <Wilaya>"), which every wilaya gets automatically.
        dsp_name = f"DSP {wilaya_name}"
        for role in tashil_app.allowed_roles("DSP"):
            rows.append({
                "wilaya_code": wilaya_code,
                "wilaya_name": wilaya_name,
                "institution_type": "DSP",
                "institution_name": dsp_name,
                "role": role,
                "serial_key": tashil_app.generate_serial_key(wilaya_code, "DSP", dsp_name, role),
            })

        # v2.8.7: a wilaya has SEVERAL distinct EPSPs, each with its own
        # head office and its own attached satellite structures
        # (polyclinics, salles de soin) — see app.py's _EPSP_HIERARCHY,
        # the single source of truth this script reuses directly rather
        # than duplicating. ⚠️ Only Oran (wilaya 31) has a real,
        # confirmed breakdown; every other wilaya still falls back to
        # the single generic "EPSP <Wilaya>" head-office placeholder —
        # the SAME convention the app itself uses in its own onboarding
        # directory (get_onboarding_institutions).
        epsp_hierarchy = tashil_app._EPSP_HIERARCHY.get(wilaya_code)
        if epsp_hierarchy:
            for epsp_name, satellites in epsp_hierarchy.items():
                for role in tashil_app.allowed_roles("EPSP", epsp_name):
                    rows.append({
                        "wilaya_code": wilaya_code, "wilaya_name": wilaya_name,
                        "institution_type": "EPSP", "institution_name": epsp_name, "role": role,
                        "serial_key": tashil_app.generate_serial_key(wilaya_code, "EPSP", epsp_name, role),
                    })
                for sat_name in satellites:
                    for role in tashil_app.allowed_roles("EPSP", sat_name):
                        rows.append({
                            "wilaya_code": wilaya_code, "wilaya_name": wilaya_name,
                            "institution_type": "EPSP", "institution_name": sat_name, "role": role,
                            "serial_key": tashil_app.generate_serial_key(wilaya_code, "EPSP", sat_name, role),
                        })
        else:
            epsp_name = f"EPSP {wilaya_name}"
            for role in tashil_app.allowed_roles("EPSP", epsp_name):
                rows.append({
                    "wilaya_code": wilaya_code, "wilaya_name": wilaya_name,
                    "institution_type": "EPSP", "institution_name": epsp_name, "role": role,
                    "serial_key": tashil_app.generate_serial_key(wilaya_code, "EPSP", epsp_name, role),
                })

        # v2.8.7: EPH/CHU/EHU now get the same 4-role set as an EPSP
        # head office (DRH, DAS, SECRETARIAT_DIRECTION, SECRETARIAT_
        # GENERAL) instead of a single catch-all role — allowed_roles()
        # already reflects this, no special-casing needed here.
        eph_name = f"EPH {wilaya_name}"
        for role in tashil_app.allowed_roles("EPH"):
            rows.append({
                "wilaya_code": wilaya_code, "wilaya_name": wilaya_name,
                "institution_type": "EPH", "institution_name": eph_name, "role": role,
                "serial_key": tashil_app.generate_serial_key(wilaya_code, "EPH", eph_name, role),
            })

        if wilaya_name in tashil_app._CHU_WILAYAS:
            chu_name = f"CHU {wilaya_name}"
            for role in tashil_app.allowed_roles("CHU"):
                rows.append({
                    "wilaya_code": wilaya_code, "wilaya_name": wilaya_name,
                    "institution_type": "CHU", "institution_name": chu_name, "role": role,
                    "serial_key": tashil_app.generate_serial_key(wilaya_code, "CHU", chu_name, role),
                })
    return rows


def write_markdown(rows, path):
    lines = [
        f"# {SECURITY_BANNER}",
        "",
        f"**Généré le :** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Nombre d'entrées :** {len(rows)} "
        f"(DSP ; EPSP — plusieurs sièges réels par wilaya + leurs "
        f"polycliniques/salles de soin rattachées ; EPH/CHU avec "
        f"DRH/DAS/Secrétariat Direction/Secrétariat Général)",
        "",
        "⚠️ Voir l'en-tête de `generate_serial_registry.py` pour les "
        "consignes de sécurité complètes avant toute diffusion de ce fichier.",
        "",
        "| Wilaya | Type | Établissement | Rôle | Clé série |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['wilaya_code']:02d} - {r['wilaya_name']} | {r['institution_type']} | "
            f"{r['institution_name']} | {r['role']} | `{r['serial_key']}` |"
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_xlsx(rows, path):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        print("⚠️  openpyxl n'est pas installé — export Excel ignoré "
              "(le fichier Markdown a tout de même été généré).")
        print("    Installez-le avec : pip install openpyxl")
        return False

    wb = Workbook()
    ws = wb.active
    ws.title = "Registre ILINE TECH"

    # Security banner row, merged across all columns, impossible to miss
    ws.merge_cells("A1:E1")
    banner_cell = ws["A1"]
    banner_cell.value = SECURITY_BANNER
    banner_cell.font = Font(bold=True, color="FFFFFF", size=11)
    banner_cell.fill = PatternFill(start_color="C0392B", end_color="C0392B", fill_type="solid")
    banner_cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 40

    headers = ["Wilaya", "Type", "Établissement", "Rôle", "Clé série"]
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=2, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
        cell.font = Font(bold=True, color="FFFFFF")

    for i, r in enumerate(rows, start=3):
        ws.cell(row=i, column=1, value=f"{r['wilaya_code']:02d} - {r['wilaya_name']}")
        ws.cell(row=i, column=2, value=r["institution_type"])
        ws.cell(row=i, column=3, value=r["institution_name"])
        ws.cell(row=i, column=4, value=r["role"])
        key_cell = ws.cell(row=i, column=5, value=r["serial_key"])
        key_cell.font = Font(name="Consolas")

    widths = [18, 10, 26, 14, 24]
    for col, width in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + col)].width = width

    ws.freeze_panes = "A3"
    wb.save(path)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="registry_export",
                         help="Dossier de sortie (créé si absent). Ne jamais pointer vers un dossier suivi par Git.")
    args = parser.parse_args()

    if not os.environ.get("TASHIL_HMAC_SECRET"):
        print("⚠️  TASHIL_HMAC_SECRET n'est pas défini — ce script utilise le secret "
              "PAR DÉFAUT, qui est PUBLIC (visible dans app.py sur GitHub). Les clés "
              "générées maintenant n'auront AUCUNE valeur de sécurité réelle tant "
              "qu'un vrai secret n'est pas configuré, identiquement, sur ce script "
              "ET sur chaque poste qui onboardera réellement ces établissements.")
        print()

    os.makedirs(args.output_dir, exist_ok=True)
    rows = build_registry_rows()

    md_path = os.path.join(args.output_dir, "registre_serial_keys_ILINE_TECH.md")
    write_markdown(rows, md_path)
    print(f"✅ Markdown généré : {md_path}")

    xlsx_path = os.path.join(args.output_dir, "registre_serial_keys_ILINE_TECH.xlsx")
    if write_xlsx(rows, xlsx_path):
        print(f"✅ Excel généré    : {xlsx_path}")

    print(f"\nTotal : {len(rows)} entrées ({len(tashil_app.WILAYAS)} wilayas).")
    print("\n⚠️  RAPPEL : ne jamais commiter ce dossier sur le dépôt Git public.")


if __name__ == "__main__":
    main()
