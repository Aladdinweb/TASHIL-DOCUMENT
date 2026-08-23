# TASHIL DOCUMENT HUB — Documentation de traçabilité
## v1.0.0 — REBOOT COMPLET (Option B : nouveau dépôt propre)

**Copyright :** ILINE TECH 2026 BY FERAK ALADDIN
**Dépôt :** https://github.com/Aladdinweb/TASHIL-Hub
**Date :** 2026-08-23

---

## But de ce fichier

Coller ce fichier au début d'une nouvelle conversation Claude pour
restaurer le contexte complet du projet instantanément.
Mettre à jour après chaque push.

---

## 0. ⚠️ Changement majeur

L'ancien projet `epsp-conge-manager` / TASHIL-ES (Congés, FIFO, Employés,
Reliquats, Rollover, Bordereau) est **abandonné**. Ce fichier documente le
nouveau produit repartant de zéro : **TASHIL DOCUMENT HUB**, un outil
d'échange de documents administratifs entre institutions de santé
algériennes (EPSP, EPH, CHU, EHU, Polyclinique).

---

## 1. Vue d'ensemble

- **Nom :** TASHIL DOCUMENT HUB
- **Type :** Application Windows desktop (PyInstaller, standalone)
- **Stack :** Python 3.11 + CustomTkinter + SQLite + serveur HTTP embarqué
- **CI/CD :** GitHub Actions (Windows runner) → Release automatique
- **EXE :** TASHIL_DOCUMENT.exe
- **Version :** v1.0.0

---

## 2. Navigation — 4 modules (sidebar)

| Module | Fichier | Contenu |
|--------|---------|---------|
| Tableau de Bord | vue_dashboard.py | Stats (envoyés/reçus/en attente), activité récente |
| Centre de Messagerie | vue_messagerie.py | Envoi, Réception, Pont Téléphone (QR) |
| Administration & Archivage | vue_administration.py | Registre officiel des courriers |
| Paramètres | vue_parametres.py | Profil, langue, notifications, thème, MAJ |

### Onboarding (première utilisation)
`vue_activation.py` — 3 étapes : Wilaya → Type/Nom établissement → Clé série
générée (HMAC-SHA256, format `TSH-WW-TT-XXXX-CHK`).

---

## 3. Architecture fichiers (état actuel)

```
TASHIL-Hub/
├── main.py                        # Bootstrapper, splash 🇩🇿, crash dump, routing
├── STATE.md                       # Ce fichier
├── requirements.txt
├── epsp_conge.spec                # PyInstaller config (nom conservé pour compat CI)
├── app/
│   ├── config.py                  # Branding, 58 wilayas, types d'institution, chemins
│   ├── assets/                    # icon.ico (à générer / fournir)
│   ├── utils/
│   │   ├── database.py            # SQLite: profile, messages, registre, phone_queue
│   │   ├── theme.py                # Palette COULEURS Dark/Light, FONTS
│   │   ├── version.py
│   │   ├── serial_key.py          # Génération clé série chiffrée par wilaya/institution
│   │   ├── notifications.py       # Toast overlay + son (winsound)
│   │   ├── updater.py             # OTA via GitHub Releases API, download -> %TEMP%
│   │   ├── archive_manager.py     # Routage fichiers -> C:\TASHIL\TASHIL_ARCHIVES\
│   │   └── phone_bridge.py        # Serveur HTTP embarqué + QR code (pont sans fil)
│   └── views/
│       ├── app_principale.py      # Fenêtre principale, sidebar, header, routing vues
│       ├── vue_activation.py      # Assistant de configuration initiale
│       ├── vue_dashboard.py       # Cartes stats + activité récente
│       ├── vue_messagerie.py      # Onglets Envoi / Réception / Pont Téléphone
│       ├── vue_administration.py  # Registre officiel (table filtrable)
│       └── vue_parametres.py      # Profil, préférences, updater
└── .github/workflows/
    └── build_windows.yml          # Build + release automatique sur tag v*
```

---

## 4. Règles IMMUABLES (CustomTkinter)

- `width` / `height` : constructeur **uniquement**, jamais dans `.place()`.
- Frames racines des vues : `place(x=0, y=0, relwidth=1, relheight=1)`
  **strictement** — jamais `pack(fill="both", expand=True)` (écran noir).
- Sidebar : `CTkScrollableFrame` + `pack()` en interne.
- Badge pays : emoji 🇩🇿 uniquement, jamais le texte "DZ".
- `initialize_database()` doit s'exécuter **avant** `ctk.CTk()`.
- Updater : téléchargement dans `%TEMP%` uniquement (jamais Desktop).
- Crash dump : `tashil_boot_error.txt` écrit avant tout `sys.exit`.

---

## 5. Archive locale isolée (CRUCIAL)

Tout fichier envoyé ou reçu — y compris via le pont téléphone — est copié
automatiquement dans :

```
C:\TASHIL\TASHIL_ARCHIVES\
├── Courrier_Sortant\   (copies des envois + scans téléphone)
└── Courrier_Entrant\   (documents reçus téléchargés)
```

Nommage standardisé : `YYYYMMDD_HHMMSS_[INSTITUTION]_[FILENAME]`
Implémenté dans `app/utils/archive_manager.py`.

Les données applicatives (profil, base SQLite) sont séparées sous
`C:\TASHIL\AppData\` pour ne jamais polluer les archives officielles.

---

## 6. Pont Téléphone (transfert sans câble)

- `phone_bridge.py` démarre un `ThreadingHTTPServer` local (port 8842 par
  défaut, configurable dans `config.py`).
- Un QR code (`qrcode` + `Pillow`) encode `http://<ip_lan>:8842/`.
- Le téléphone scanne → page web minimaliste servie inline (aucune install
  requise) → upload multipart vers `/upload`.
- Le fichier est écrit directement dans `Courrier_Sortant` et une entrée
  est ajoutée à `phone_bridge_queue` ; l'UI sonde cette file toutes les
  2.5s et affiche un toast de confirmation.

---

## 7. 58 Wilayas & types d'institution

Liste complète des 58 wilayas dans `app/config.py::WILAYAS`.
Types d'institution : `EPSP`, `EPH`, `CHU`, `EHU`, `Polyclinique`.

---

## 8. État des livrables demandés (2026-08-23)

| Fichier | Statut |
|---------|--------|
| `main.py` | ✅ Généré — bootstrap complet, splash, crash dump, routing |
| `app/views/vue_activation.py` | ✅ Généré — wizard 3 étapes |
| `app/views/app_principale.py` | ✅ Généré — sidebar 4 modules, header, routing |
| `app/utils/phone_bridge.py` | ✅ Généré — serveur HTTP + QR |
| `app/utils/archive_manager.py` | ✅ Généré — routage archive isolée |
| `STATE.md` | ✅ Ce fichier, mis à jour |

**Modules de support additionnels générés pour rendre le code exécutable**
(non explicitement demandés mais requis par les imports ci-dessus) :
`config.py`, `database.py`, `theme.py`, `version.py`, `serial_key.py`,
`notifications.py`, `updater.py`, `vue_dashboard.py`, `vue_messagerie.py`,
`vue_administration.py`, `vue_parametres.py`, `requirements.txt`,
`epsp_conge.spec`, `.github/workflows/build_windows.yml`.

---

## 9. Prochaines étapes suggérées

1. Fournir/générer `app/assets/icon.ico` (croix médicale verte, cf. ancien
   projet) — actuellement référencé mais absent.
2. Tester le premier lancement (`is_first_launch()` → wizard) sur Windows
   réel (winsound, chemins `C:\TASHIL\...` sont Windows-only).
3. Décider du vrai back-end de transmission inter-institutions (le
   document de reboot mentionne "GitHub Releases/Repository comme pont de
   transmission sécurisé" — à préciser : push vers un repo privé ? API
   dédiée ? Actuellement les messages "envoyés" sont archivés localement
   et enregistrés en DB, mais aucun transport réseau réel vers l'autre
   institution n'est encore implémenté au-delà du pont téléphone local).
4. `pip install -r requirements.txt` puis test local avant premier push
   Termux → GitHub Actions.
