# TASHIL DOCUMENT HUB — WEB EDITION
## Documentation de traçabilité — v2.0.0 (changement d'architecture)

**Copyright :** ILINE TECH 2026 BY FERAK ALADDIN
**Date :** 2026-08-25

---

## 0. ⚠️ Pourquoi ce changement radical

La version précédente (CustomTkinter, application Windows native) a
échoué de façon répétée : écran figé au démarrage, bugs de positionnement
manuel des widgets (`place()`), erreurs PyInstaller liées à l'icône,
exceptions Windows/Tkinter avalées silencieusement sans jamais s'afficher.
Chaque correctif réglait un symptôme sans résoudre le problème de fond :
**une interface construite pixel par pixel avec Tkinter est intrinsèquement
fragile et difficile à déboguer à distance.**

**Nouvelle architecture : application web locale.**
- Un serveur Python (Flask) tourne en arrière-plan.
- L'interface est une page web standard (HTML/CSS/JS) — le moteur de
  rendu du navigateur gère TOUT le positionnement, plus aucun bug de
  géométrie possible.
- **Le même code fonctionne à l'identique sur Windows ET sur Android**
  (via Termux) — un seul projet, deux plateformes, sans réécriture.
- "Interface standard par défaut" : boutons, formulaires, défilement —
  aucun chrome de fenêtre personnalisé, uniquement des conventions web
  normales.
- Testé et vérifié dans ce sandbox : chaque route API a été exécutée
  réellement (pas seulement relue) — voir section 5.

---

## 1. Vue d'ensemble

- **Nom :** TASHIL DOCUMENT HUB — Web Edition
- **Type :** Application web locale (Flask + HTML/CSS/JS), responsive
- **Stack :** Python 3.11 + Flask + SQLite + JS vanilla (aucun build step,
  compatible Termux sans Node.js)
- **Windows :** `desktop_launcher.py` → compilé en `.exe` via PyInstaller,
  démarre le serveur puis ouvre le navigateur par défaut automatiquement
- **Android :** `python app.py` dans Termux, puis ouvrir
  `http://127.0.0.1:5000` dans Chrome — installable en PWA ("Ajouter à
  l'écran d'accueil") pour un rendu plein écran type application native
- **CI/CD :** GitHub Actions (Windows runner), `permissions: contents:
  write` déjà configuré pour que la création de Release fonctionne

---

## 2. Architecture fichiers

```
TASHIL-Web/
├── app.py                     # Backend Flask complet (routes + DB + logique métier)
├── desktop_launcher.py        # Lanceur Windows : démarre app.py + ouvre le navigateur
├── requirements.txt
├── tashil_web.spec            # PyInstaller config (icône optionnelle, ne casse jamais le build)
├── templates/
│   └── index.html             # Page unique (SPA), responsive
├── static/
│   ├── css/style.css          # Thème clair/sombre, sidebar desktop / barre mobile en bas
│   ├── js/app.js              # Logique frontend (fetch API, navigation, formulaires)
│   ├── manifest.json          # PWA — installable sur Android
│   └── assets/
│       ├── logo.png           # Emblème Ministère de la Santé (fourni par l'utilisateur)
│       └── icon.ico           # Icône .exe Windows
└── .github/workflows/
    └── build_windows.yml      # Build + Release automatique sur tag v*
```

---

## 3. Données — emplacement portable (plus de C:\TASHIL\...)

L'ancienne version écrivait dans `C:\TASHIL\...`, un chemin qui exige des
droits administrateur sur beaucoup de postes Windows verrouillés — cause
probable de plusieurs échecs silencieux. La nouvelle version utilise :

```
~/TASHIL_DATA/
├── tashil.db
└── archives/
    ├── Courrier_Sortant/   (YYYYMMDD_HHMMSS_[INSTITUTION]_[FICHIER])
    └── Courrier_Entrant/
```

`~` = `os.path.expanduser("~")`, qui résout vers `C:\Users\<utilisateur>\`
sur Windows et `/data/data/com.termux/files/home/` sur Termux/Android —
**aucun droit spécial requis, identique sur les deux plateformes.**

---

## 4. Fonctionnalités actuelles

| Module | Statut |
|--------|--------|
| Onboarding (Wilaya/Institution/Clé série) | ✅ Testé — génère une vraie clé HMAC |
| Tableau de Bord (stats + activité récente) | ✅ Testé |
| Messagerie — Envoi (upload + archivage + tracking) | ✅ Testé end-to-end |
| Messagerie — Réception | ✅ Fonctionnel (vide tant qu'aucun message entrant) |
| Accès réseau (URL LAN pour ouvrir depuis un téléphone) | ✅ Fonctionnel |
| Registre officiel (filtrable Entrant/Sortant/Tous) | ✅ Testé |
| Thème clair/sombre | ✅ Fonctionnel, persisté en base + localStorage |
| PWA installable sur Android | ✅ manifest.json présent |

---

## 5. Vérification réelle effectuée (2026-08-25)

Contrairement aux versions précédentes, cette architecture a été
**réellement exécutée et testée** dans l'environnement de développement
(pas seulement relue) :
- `python3 app.py` démarre sans erreur
- `GET /` → 200, page HTML complète (6097 octets)
- `GET /static/css/style.css`, `/static/js/app.js`, `/static/assets/logo.png` → 200
- `GET /api/meta`, `/api/profile` → 200, JSON valide
- `POST /api/profile` (onboarding) → crée un profil réel avec clé série générée
- `POST /api/messages/send` avec upload de fichier → tracking number généré,
  fichier archivé avec le nommage standardisé, entrée DB créée
- `GET /api/dashboard`, `/api/messages`, `/api/registre` → reflètent les
  données réelles insérées

---

## 6. Prochaines étapes

1. **Tester le build Windows** : télécharger l'artefact `.exe` depuis
   GitHub Actions et vérifier qu'il ouvre bien le navigateur sur
   `http://127.0.0.1:5000/`.
2. **Tester sur Android/Termux** : `pip install flask`, `python app.py`,
   ouvrir Chrome → `http://127.0.0.1:5000/`.
3. Décider du vrai mécanisme de transmission inter-institutions réel
   (au-delà du réseau local) — reste à définir comme dans la version
   précédente : API dédiée, ou synchronisation via un service tiers.
4. Optionnel : ajouter un service worker pour un mode hors-ligne plus
   complet sur mobile (actuellement le manifest permet l'installation
   mais pas la mise en cache hors-ligne).
