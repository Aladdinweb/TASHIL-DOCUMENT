# TASHIL: Smart Health Management System 🇩🇿
## Documentation de traçabilité — v1.1.38

**Copyright :** ILINE TECH 2026 BY FERAK ALADDIN
**Dépôt :** https://github.com/Aladdinweb/TASHIL-ES
**Date :** 2026-07-04

---

## But de ce fichier

Coller ce fichier au début d'une nouvelle conversation Claude
pour restaurer le contexte complet du projet instantanément.
Mettre à jour après chaque push.

---

## 1. Vue d'ensemble

- **Nom :** TASHIL — Smart Health Management System
- **Type :** Application Windows desktop (PyInstaller)
- **Stack :** Python 3.11 + CustomTkinter + SQLite
- **CI/CD :** GitHub Actions → Release automatique
- **Repo :** Aladdinweb/TASHIL-ES (branch: main)
- **EXE :** EPSP_CongeManager.exe
- **Version :** v1.1.38

---

## 2. Navigation — 2 onglets actifs

| Onglet | Module | Contenu |
|--------|--------|---------|
| Tableau de bord | vue_dashboard.py | Stats, annuaire, alertes |
| Administration | vue_administration.py | Messagerie, Rollover, Système |

### Modules supprimés (sur demande)
- ~~Employés~~ — supprimé v1.1.38
- ~~Congés~~ — supprimé v1.1.38
- ~~Reliquats~~ — supprimé v1.1.38
- ~~Bordereau~~ — supprimé v1.1.37
- ~~Tableau Service~~ — supprimé v1.1.37

### Administration — 4 sous-onglets
1. **Boîte d'envoi** — Messages inter-polycliniques
2. **Boîte de réception** — Messages reçus + badge non-lus
3. **Rollover & Branches** — Rollover 1er Mai + 7 polycliniques
4. **Système** — Infos, backup, réinitialisation

---

## 3. Architecture fichiers

```
TASHIL-ES/
├── main.py                    # Entrée, splash 🇩🇿, SmartHub
├── STATE.md                   # Ce fichier
├── epsp_conge.spec            # PyInstaller config
├── app/
│   ├── config.py              # Branding, institutions, services
│   ├── assets/
│   │   └── create_icon.py     # Icône médicale croix verte
│   ├── utils/
│   │   ├── database.py        # SQLite + backup auto
│   │   ├── version.py         # v1.1.0, patch CI auto
│   │   ├── migration.py       # Migrations schéma
│   │   ├── services.py        # Import depuis config.py
│   │   ├── deduction_engine.py # FIFO + rollover 1er Mai
│   │   ├── employes_dao.py    # CRUD (conservé pour DB)
│   │   ├── conges_dao.py      # CRUD (conservé pour DB)
│   │   ├── polycliniques_dao.py
│   │   ├── theme.py           # Palette COULEURS/POLICES
│   │   └── updater.py         # MAJ auto TEMP
│   └── views/
│       ├── app_principale.py  # Navigation 2 onglets
│       ├── vue_dashboard.py   # Dashboard thread-safe
│       ├── vue_administration.py # Admin pro 4 onglets
│       └── vue_activation.py  # Première config
└── .github/workflows/
    └── build_windows.yml
```

---

## 4. Règles IMMUABLES

### CustomTkinter place()
- width/height dans constructeur UNIQUEMENT
- place() = x/y/relwidth/relheight SEULEMENT

### Frames racines
- SEUL : place(x=0, y=0, relwidth=1, relheight=1)
- INTERDIT : pack(fill="both") = écran noir

### Sidebar
- CTkScrollableFrame + pack() interne
- Badge = emoji 🇩🇿, jamais texte "DZ"

### DB init
- initialize_database() AVANT ctk.CTk()

### FIFO (conservé dans la DB même si non affiché)
- deduction_engine.py intact
- Rollover 1er Mai fonctionnel via Administration

### Updater
- Téléchargement dans %TEMP% uniquement

### Crash dump
- tashil_boot_error.txt avant sys.exit

---

## 5. Polycliniques EPSP ES-SENIA (7)

| Code | Nom |
|------|-----|
| POLY_01 | POLYCLINIQUE ES SENIA |
| POLY_02 | POLYCLINIQUE AADL AIN BEIDA MABROUK LOUCIF |
| POLY_03 | POLYCLINIQUE AIN BEIDA 1 |
| POLY_04 | POLYCLINIQUE AIN BEIDA 2 |
| POLY_05 | POLYCLINIQUE SIDI MAAROUF |
| POLY_06 | POLYCLINIQUE SIDI CHAHMI |
| POLY_07 | POLYCLINIQUE EL KERMA |

---

## 6. Historique corrections

| Version | Correction |
|---------|------------|
| v1.1.32 | Sidebar scrollable, modules rendus |
| v1.1.33 | Mois FR, badge drapeau |
| v1.1.34 | Migration TASHIL-ES |
| v1.1.35 | Fix Errno 13 updater TEMP |
| v1.1.36 | DnD, institutions EPSP/EPH/CHU/EHU |
| v1.1.37 | Bordereau/TableauService supprimés |
| v1.1.38 | Employés/Congés/Reliquats supprimés, Admin pro |
