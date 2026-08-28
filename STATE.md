# TASHIL DOCUMENT HUB — WEB EDITION
## Documentation de traçabilité — v2.3.0

**Copyright :** ILINE TECH 2026 BY FERAK ALADDIN
**Date :** 2026-08-28

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
| Onboarding (Wilaya/Institution/Clé série) | ✅ Testé — génère une vraie clé HMAC, confirmé sur build Windows réel |
| Tableau de Bord (stats + activité récente) | ✅ Testé, confirmé sur build Windows réel |
| Messagerie — Envoi (upload + archivage + tracking) | ✅ Testé end-to-end, confirmé sur build Windows réel |
| Messagerie — Réception (avec accusé de réception) | ✅ Testé — voir section 8 |
| Accès réseau (URL LAN pour ouvrir depuis un téléphone) | ✅ Fonctionnel |
| Registre officiel (filtrable Entrant/Sortant/Tous) | ✅ Testé, confirmé sur build Windows réel |
| Téléchargement + suppression (Tableau de Bord, Réception, Registre) | ✅ Testé — voir section 8 |
| Notifications (toast + navigateur) envoi/réception | ✅ Testé — voir section 8 |
| Verrouillage / changement d'établissement (multi-profils) | ✅ Testé — voir section 10 |
| Code PIN par établissement + écran de verrouillage | ✅ Testé — voir section 10 |
| Isolation stricte des données entre établissements | ✅ Testé — voir section 10 |
| Dropdown dynamique Nom de l'établissement (onboarding) | ✅ Testé — voir section 10 |
| Thème clair/sombre | ✅ Fonctionnel, persisté en base + localStorage |
| PWA installable sur Android | ✅ manifest.json présent |
| Fenêtre native de bureau (pywebview) | ✅ Confirmé fonctionnel sur build Windows réel (v2.1.0) |
| Autocomplétion Institution destinataire | ✅ Confirmé fonctionnel (v2.1.0) |
| Vérification des mises à jour (GitHub Releases) | ✅ Confirmé fonctionnel — affiche "TASHIL est à jour" (v2.1.0) |
| Pied de page copyright | ✅ Ajouté — voir section 8 |

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

1. ~~Tester le build Windows~~ — ✅ Fait, confirmé par l'utilisateur (fenêtre
   native pywebview fonctionnelle, envoi/dashboard/registre/paramètres
   tous opérationnels).
2. **Tester sur Android/Termux** : `pip install flask`, `python app.py`,
   ouvrir Chrome → `http://127.0.0.1:5000/` — reste à confirmer avec le
   navigateur (le serveur Termux a démarré avec succès, l'ouverture dans
   le navigateur du téléphone n'a pas encore été confirmée explicitement).
3. Décider du vrai mécanisme de transmission inter-institutions distant
   (au-delà du réseau local). Le point 2 (ci-dessous, validation
   utilisateur du 2026-08-26) propose GitHub (API/Releases/Actions) comme
   "Cloud Bridge" — **encore à concevoir et implémenter**, non fait à ce
   jour. Pistes : un dépôt privé faisant office de file d'attente de
   messages (chaque institution pousse/tire via l'API GitHub), ou un vrai
   service cloud dédié si le volume devient trop important pour GitHub.
4. Optionnel : ajouter un service worker pour un mode hors-ligne plus
   complet sur mobile (actuellement le manifest permet l'installation
   mais pas la mise en cache hors-ligne).
5. Le répertoire d'institutions (`INSTITUTIONS_DIRECTORY` dans `app.py`)
   reste un point de départ générique — à enrichir avec de vrais contacts
   au fur et à mesure (voir avertissement section 9).

---

## 7. Validation utilisateur (2026-08-26) + v2.1.0

L'architecture Web Edition a été validée par l'utilisateur après un test
réel sur build Windows (fenêtre native, envoi de document, dashboard,
registre, paramètres — tous confirmés fonctionnels par capture d'écran).

**Trois fonctionnalités ajoutées et testées (v2.1.0) :**
1. **Fenêtre de bureau native (pywebview)** — remplace l'onglet navigateur
   externe. `desktop_launcher.py` tente `pywebview` en premier ; en cas
   d'échec (WebView2 manquant, DLL non empaquetée), bascule
   automatiquement sur l'ouverture du navigateur par défaut — testé en
   simulant l'absence de pywebview, confirmé qu'aucune exception ne
   remonte. `tashil_web.spec` utilise `collect_all('webview')` pour
   empaqueter correctement les DLLs de la plateforme.
2. **Autocomplétion Institution destinataire** — `<input list="...">` +
   `<datalist>` standard HTML, alimenté par `/api/institutions` (192
   entrées : les 7 vraies polycliniques EPSP ES-SENIA + un gabarit
   générique `<Type> <Wilaya>` pour EPSP/EPH/Polyclinique + CHU limité aux
   11 wilayas qui en possèdent réellement un). **Répertoire de départ, pas
   un registre officiel vérifié** — à éditer avec de vrais contacts.
3. **Vérificateur de mise à jour intégré** — dans Paramètres, appelle
   `https://api.github.com/repos/Aladdinweb/TASHIL-ES/releases/latest`,
   compare les versions sémantiquement (pas une comparaison de chaînes),
   affiche une bannière de téléchargement si une version plus récente
   existe. Confirmé fonctionnel par l'utilisateur ("TASHIL est à jour").

**Point de transmission Cloud Bridge (noté, pas encore implémenté) :**
pour la transmission inter-institutions distante (hors réseau local),
l'utilisateur propose d'utiliser le dépôt GitHub (API/Releases/Actions)
comme pont de transmission sécurisé. Ceci reste à concevoir — voir
section 6, point 3.

---

## 8. v2.2.0 — Notifications, actions de liste, déconnexion, copyright (2026-08-27)

Quatre ajouts, tous testés réellement (serveur lancé, routes appelées via
`curl`, réponses JSON vérifiées) avant livraison :

1. **Notifications + accusé de réception**
   - Système de toasts en haut à droite (`showToast()`), déclenché à
     l'envoi d'un document ET à la réception d'un nouveau message.
   - Sondage en arrière-plan (`startBackgroundPolling()`, toutes les 8s)
     qui compare `total_received` au dernier total connu — si un nouveau
     message est arrivé, affiche un toast même si l'utilisateur n'est pas
     sur l'onglet Messagerie.
   - Notifications navigateur natives en complément (`Notification` API),
     avec détection de compatibilité et repli silencieux si indisponible
     (pywebview/WebView2 ne supporte pas toujours cette API).
   - **Accusé de réception** : bouton "✅ Accusé" sur chaque message reçu
     dans la Boîte de réception → `POST /api/messages/<id>/status` avec
     `{"status": "accuse"}` → le badge devient "✅ accusé" une fois
     confirmé. Testé via `curl`, changement de statut vérifié en base.
   - ⚠️ Limite actuelle : tout tourne sur la même base SQLite locale — il
     n'existe pas encore de vraie séparation réseau entre "expéditeur" et
     "destinataire" sur deux machines distinctes (voir point Cloud Bridge,
     section 6). L'accusé de réception fonctionne dès aujourd'hui pour un
     usage sur un même appareil/réseau local ; sa portée inter-
     institutions dépendra de l'implémentation du Cloud Bridge.

2. **Téléchargement et suppression** — Tableau de Bord (Activité Récente),
   Boîte de réception, et Registre affichent maintenant, par ligne :
   - 📥 Télécharger → ouvre `/api/messages/<id>/download` (route déjà
     existante en backend mais jamais reliée au frontend jusqu'ici — gap
     comblé).
   - 🗑️ Supprimer → confirmation, puis `DELETE /api/messages/<id>` qui
     retire l'entrée de la base ET le fichier archivé du disque. Testé :
     suppression confirmée en base ET absence du fichier vérifiée.

3. **Pied de page copyright** — `© ILINE TECH BY FERAK ALADDIN`, visible
   en bas de chaque vue (dans `<main>`, après Paramètres, donc toujours
   présent quel que soit l'onglet actif). Sur mobile, reste au-dessus de
   la barre d'onglets fixe grâce au padding déjà existant.

4. **Déconnexion / réinitialisation du profil** — carte "Session" dans
   Paramètres avec bouton de confirmation → `POST /api/profile/logout`
   supprime la ligne `profile` (mais PAS les messages/archives, décision
   délibérée : la déconnexion réinitialise l'identité de l'appareil, pas
   les données). Après confirmation, la page se recharge et l'assistant
   d'onboarding réapparaît. Testé via `curl` : `first_launch` repasse à
   `true` après l'appel.

**Fichiers modifiés :** `app.py`, `templates/index.html`,
`static/css/style.css`, `static/js/app.js`. Aucun fichier supprimé,
aucune fonctionnalité antérieure retirée.

---

## 9. ⚠️ Rappel — répertoire d'institutions non officiel

`INSTITUTIONS_DIRECTORY` dans `app.py` (utilisé par l'autocomplétion) est
un point de départ générique, PAS un registre national vérifié. Il
contient les 7 vraies polycliniques EPSP ES-SENIA et un gabarit
`<Type> <Wilaya>` pour le reste. À éditer avec de vrais contacts au fur
et à mesure — le champ accepte aussi la saisie libre pour tout ce qui
n'y figure pas encore.

---

## 10. v2.3.0 — Multi-tenant, code PIN, écran de verrouillage (2026-08-28)

Changement d'architecture significatif, entièrement testé en réel (serveur
lancé, chaque route/scénario vérifié via `curl` avant livraison — voir le
détail des tests en fin de section) : l'appareil peut désormais héberger
**plusieurs profils d'établissement isolés**, chacun protégé par son propre
code PIN.

### 10.1 Répertoire d'onboarding dynamique (dropdown)

Le champ "Nom de l'établissement" de l'assistant de configuration est
maintenant un `<select>` peuplé dynamiquement selon la Wilaya + le Type
choisis (`GET /api/institutions/onboarding?wilaya_code=&institution_type=`).
Seule la Wilaya 31 (Oran) contient des entrées réelles confirmées :
- **EPSP / Polyclinique** → les 7 vraies polycliniques EPSP ES-SENIA.
- **EPH** → `EPH AIN TURCK`.
- **CHU** → `CHU ORAN`.
- **EHU** → `EHU ORAN`.

Toute autre combinaison Wilaya/Type retombe sur une entrée générique
`<Type> <Wilaya>`. Une option **"Autre (saisir manuellement)"** est
toujours présente en dernier recours, avec un champ texte qui apparaît
dynamiquement — personne n'est jamais bloqué par une liste incomplète.
⚠️ Toujours pas un registre officiel vérifié, même remarque qu'en section 9.

### 10.2 Code PIN & écran de verrouillage

- Le formulaire d'onboarding exige désormais un **code PIN à 4-6 chiffres**
  (+ confirmation), stocké **hashé** (`werkzeug.security.generate_password_hash`
  — jamais en clair) dans la table `profiles` du registre.
- **Écran de verrouillage** (`lock-overlay`) affiché à chaque démarrage de
  l'application tant qu'aucun profil n'est déverrouillé : liste des
  établissements enregistrés sur l'appareil → sélection → saisie du PIN.
- Bouton 🔒 dans la barre supérieure + carte "Session" dans Paramètres
  permettent de verrouiller manuellement à tout moment sans fermer
  l'application (SPA — pas de rechargement de page).
- ⚠️ **Honnêteté sur le niveau de sécurité** : ce PIN est un verrou d'écran
  contre le survol/accès physique occasionnel sur un appareil partagé — ce
  n'est **pas** un chiffrement des données. Quiconque a un accès direct au
  système de fichiers (`~/TASHIL_DATA/profiles/<clé>/`) peut toujours lire
  les archives et la base SQLite directement, PIN ou non.
- ⚠️ **Limite de concurrence** : la session active est une simple variable
  en mémoire côté serveur — conçu pour une personne, un appareil, qui
  change de casquette, pas pour plusieurs utilisateurs simultanés sur le
  même processus serveur.

### 10.3 Isolation stricte multi-tenant

Nouvelle architecture de stockage :
```
~/TASHIL_DATA/
├── registry.db                          # Registre maître (profils, PIN hashés, thème)
└── profiles/
    └── <institution_key>/
        ├── tashil.db                    # Base de messages ISOLÉE à ce profil
        └── archives/
            ├── Courrier_Sortant/
            └── Courrier_Entrant/
```
`institution_key` est dérivé de la Wilaya + du Type + du nom (ex.
`31_EP_EPSP_ES_SENIA`), avec suffixe anti-collision si nécessaire.

**Déconnexion repensée** : "Déconnexion" ne supprime plus le profil (ancien
comportement v2.0-v2.2, jugé destructif). Elle **verrouille** simplement la
session — les données de l'établissement restent intactes et isolées,
récupérables en se reconnectant avec le PIN. Une nouvelle route
`POST /api/session/lock` remplace `POST /api/profile/logout` (supprimée).

**Migration automatique** : si une ancienne base `~/TASHIL_DATA/tashil.db`
(structure mono-profil pré-v2.3.0) est détectée au démarrage et qu'aucun
profil n'existe encore dans le registre, elle est **déplacée** (pas copiée)
vers `profiles/<clé>/` avec ses archives, sans PIN initial — l'écran de
verrouillage détecte ce cas (`pin_set: false`) et invite à **créer** un PIN
plutôt que d'en demander un qui n'a jamais existé. Rien n'est perdu.

### 10.4 Tests réels effectués avant livraison

Tous testés en lançant le serveur réel et en appelant les routes via `curl`
(pas seulement relus) :
- ✅ Session vide → `first_launch: true`
- ✅ Dropdown onboarding Oran/EPSP → 7 vraies polycliniques ; Oran/EPH →
  `EPH AIN TURCK` seul ; Adrar/EPSP → repli générique `EPSP Adrar`
- ✅ Création de profil A avec PIN → activation automatique, `pin_hash`
  jamais renvoyé au frontend
- ✅ Accès aux routes de données pendant que la session est verrouillée →
  `423` partout
- ✅ Mauvais PIN → `401` ; bon PIN → déverrouillage réussi
- ✅ **Isolation croisée** : création du profil B (CHU ORAN) → tableau de
  bord immédiatement à 0 message (aucune fuite depuis A) ; reverrouillage
  puis redéverrouillage de A → son message envoyé plus tôt est toujours là
- ✅ Séparation physique des dossiers vérifiée sur disque
  (`profiles/31_EP_.../` vs `profiles/31_CU_.../`)
- ✅ Migration héritée : base + archives pré-v2.3.0 simulées, migration
  automatique confirmée (fichiers physiquement déplacés, message hérité
  intact, PIN à créer détecté correctement, ancien chemin bien supprimé)
- ✅ Vérification statique croisée : chaque `getElementById(...)` de
  `app.js` correspond à un `id` réellement présent dans `index.html` (0
  référence orpheline — script de vérification automatisé, pas juste une
  relecture)
- ✅ Bug de listeners dupliqués anticipé et corrigé : comme le
  verrouillage/déverrouillage ne recharge plus la page, le câblage des
  événements (`setupNav`, `setupMessaging`, etc.) et `startBackgroundPolling`
  ne s'exécutent maintenant qu'**une seule fois** (`state.appInitialized`),
  pour éviter l'empilement de gestionnaires d'événements ou d'intervalles
  concurrents au fil des changements de profil dans une même session
  d'application.

**Fichiers modifiés :** `app.py` (réécriture substantielle),
`templates/index.html`, `static/css/style.css`, `static/js/app.js`.
Aucune fonctionnalité antérieure retirée — voir sections 1 à 9 pour
l'historique complet, toujours valable.
