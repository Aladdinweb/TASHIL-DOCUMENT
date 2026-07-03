# TASHIL: Smart Health Management System
## Documentation de traçabilité — v1.1.35

**Copyright :** ILINE TECH 2026 BY FERAK ALADDIN
**Dépôt :** https://github.com/Aladdinweb/TASHIL-ES
**Date :** 2026-07-02

---

## But de ce fichier

Coller ce fichier au début d'une nouvelle conversation Claude
pour restaurer instantanément le contexte complet du projet,
sans réexpliquer l'architecture ni l'historique.
Mettre à jour après chaque push de version.

---

## 1. Vue d'ensemble

- **Nom :** TASHIL — Smart Health Management System
- **Type :** Application Windows desktop (PyInstaller)
- **Stack :** Python 3.11 + CustomTkinter + SQLite
- **CI/CD :** GitHub Actions → Release automatique
- **Repo :** Aladdinweb/TASHIL-ES (branch: main)
- **EXE :** EPSP_CongeManager.exe
- **Version :** v1.1.35 (patch auto-incrémenté par CI)

---

## 2. Architecture des fichiers

```
TASHIL-ES/
├── main.py                    # Entrée, splash, SmartHub
├── STATE.md                   # Ce fichier
├── epsp_conge.spec            # PyInstaller config
├── app/
│   ├── config.py              # Branding, 20 services, grades
│   ├── utils/
│   │   ├── database.py        # SQLite + backup auto
│   │   ├── version.py         # v1.1.0 ancre, patch CI
│   │   ├── migration.py       # Migrations + colonne service
│   │   ├── services.py        # Import depuis config.py
│   │   ├── deduction_engine.py # FIFO + rollover 1er Mai
│   │   ├── employes_dao.py    # CRUD employes
│   │   ├── conges_dao.py      # CRUD conges
│   │   ├── polycliniques_dao.py # CRUD polycliniques
│   │   ├── theme.py           # Palette COULEURS/POLICES
│   │   └── updater.py         # MAJ auto (DL dans TEMP)
│   └── views/
│       ├── app_principale.py  # Navigation 7 onglets
│       ├── vue_dashboard.py   # Dashboard thread-safe
│       ├── vue_employes.py    # Gestion employes
│       ├── vue_conge.py       # Onglet Conges
│       ├── vue_reliquat.py    # Reliquats FIFO
│       ├── vue_bordereau.py   # Bordereau + FIFO
│       ├── vue_tableau_service.py # Grille roster
│       ├── vue_administration.py  # Messagerie
│       ├── vue_activation.py  # Premiere config
│       ├── dialogue_employe.py
│       ├── dialogue_conge_rapide.py
│       ├── dialogue_annulation.py
│       ├── dialogue_transfert.py
│       └── fiche_employe.py
└── .github/workflows/
    └── build_windows.yml      # CI/CD PyInstaller
```

---

## 3. Regles architecturales IMMUABLES

### Regle 1 — CustomTkinter place()
- width/height TOUJOURS dans le constructeur du widget
- place() utilise uniquement x/y/relwidth/relheight
- Violation = ValueError silencieux sous PyInstaller

### Regle 2 — Frames racines des vues
- SEUL moyen valide : vue.place(x=0, y=0, relwidth=1, relheight=1)
- INTERDIT : vue.pack(fill="both", expand=True) = ecran noir

### Regle 3 — Sidebar
- CTkScrollableFrame + pack() en interne
- Badge = emoji uniquement, jamais texte "dz"

### Regle 4 — Initialisation DB
- initialize_database() + migrer() AVANT ctk.CTk()

### Regle 5 — Refresh interception
- _modal_actif() verifie CTkToplevel avant refresh
- Jamais fermer un formulaire actif

### Regle 6 — FIFO (logique gelee)
- CONGE_ANNUEL = deduction reliquat le plus ancien
- MALADIE/MATERNITE = sans deduction
- Rollover 1er Mai = executer_rollover_mai()

### Regle 7 — Updater
- Telechargement TOUJOURS dans %TEMP%
- Jamais dans le dossier exe (Desktop bloque)

### Regle 8 — Crash dump
- Erreur boot = tashil_boot_error.txt avant sys.exit

---

## 4. Signature du code (Windows)

Generer un certificat auto-signe (PowerShell) :

```powershell
$cert = New-SelfSignedCertificate `
  -Subject "CN=TASHIL ILINE TECH 2026" `
  -CertStoreLocation "Cert:\CurrentUser\My" `
  -KeyExportPolicy Exportable -KeySpec Signature

$pwd = ConvertTo-SecureString "TASHIL2026!" -AsPlainText -Force
Export-PfxCertificate -Cert $cert -FilePath "tashil_cert.pfx" -Password $pwd

[Convert]::ToBase64String([IO.File]::ReadAllBytes("tashil_cert.pfx")) |
  Out-File "tashil_cert_b64.txt"
```

Ajouter dans GitHub Secrets :
- SIGNING_CERT_B64 = contenu de tashil_cert_b64.txt
- SIGNING_CERT_PASSWORD = TASHIL2026!

---

## 5. Etat des modules

| Module           | Etat | Description                          |
|------------------|------|--------------------------------------|
| Dashboard        | OK   | 4 tuiles, annuaire, LA REPRISE       |
| Employes         | OK   | 4 champs obligatoires                |
| Conges           | OK   | Menu clic droit, FIFO                |
| Reliquats        | OK   | Matricule masque, colonnes vides     |
| Bordereau        | OK   | Scan FIFO, export Excel              |
| Tableau Service  | OK   | Grille editable, mois FR             |
| Administration   | OK   | Messagerie inter-polycliniques       |
| Smart Hub        | OK   | Socket port 7890 daemon              |
| MAJ automatique  | OK   | DL TEMP, bat remplacement            |

---

## 6. Services cliniques (20)

Urgences, Consultation, Dentaire, PMI, Pediatre,
Psychologue, Vaccin, Sage Femme, Salle de Soin, ECG,
Pharmacie, Medecine Interne/Endocrinologue,
Service Ophtalmologie, Secretariat, Dentaire Urgences,
Dermatologue, Pneumologue, ORL, Administration, Autre

---

## 7. Polycliniques EPSP ES-SENIA (7)

| Code    | Nom                                        |
|---------|--------------------------------------------|
| POLY_01 | POLYCLINIQUE ES SENIA                      |
| POLY_02 | POLYCLINIQUE AADL AIN BEIDA MABROUK LOUCIF |
| POLY_03 | POLYCLINIQUE AIN BEIDA 1                   |
| POLY_04 | POLYCLINIQUE AIN BEIDA 2                   |
| POLY_05 | POLYCLINIQUE SIDI MAAROUF                  |
| POLY_06 | POLYCLINIQUE SIDI CHAHMI                   |
| POLY_07 | POLYCLINIQUE EL KERMA                      |

---

## 8. Historique corrections

| Version  | Correction                                  |
|----------|---------------------------------------------|
| v1.1.21  | Fix ecran noir — DB avant tkinter           |
| v1.1.28  | Fix ValueError — place() constructeur       |
| v1.1.32  | Sidebar scrollable, modules rendus          |
| v1.1.33  | Mois FR, badge drapeau, tuiles              |
| v1.1.34  | Migration vers TASHIL-ES                    |
| v1.1.35  | Fix Errno 13 updater TEMP, STATE.md complet |
