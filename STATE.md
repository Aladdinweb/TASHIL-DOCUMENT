# TASHIL DOCUMENT HUB — WEB EDITION
## Documentation de traçabilité — v2.8.0

**Copyright :** ILINE TECH 2026 BY FERAK ALADDIN
**Date :** 2026-09-07

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

---

## 11. v2.3.1 — Corrections réelles suite à retour utilisateur (2026-08-28)

Deux signalements utilisateur après test sur build Windows réel, tous deux
identifiés comme de **vrais bugs**, pas des préférences cosmétiques.

### 11.1 🐛 Champs PIN non stylés (bug CSS réel)

**Cause :** la règle CSS de style des champs de formulaire ne ciblait que
`input[type="text"]` — or les 4 champs de code PIN utilisent
`type="password"`, donc ils ne recevaient AUCUN style personnalisé et
s'affichaient avec l'apparence par défaut du navigateur/WebView.

**Correctif :**
- Sélecteur CSS élargi à `input[type="password"]`, `input[type="tel"]`,
  `input[type="number"]`, `input[type="email"]` (pas seulement `text`).
- Nouvelle classe `.pin-input` appliquée aux 4 champs PIN (onboarding +
  écran de verrouillage) : grande taille de police, espacement des
  lettres, police monospace, centré — apparence "code d'accès" moderne
  plutôt qu'un champ texte générique.

### 11.2 🐛 Accès réseau non fonctionnel sur le build Windows (bug réel, pas juste UX)

**Cause racine :** `desktop_launcher.py` démarrait le serveur Flask avec
`host="127.0.0.1"` (boucle locale uniquement) — alors que
`app.py` (utilisé pour `python app.py` en Termux) utilise correctement
`host="0.0.0.0"`. Résultat : **sur le build Windows réel testé par
l'utilisateur, aucun appareil du réseau local ne pouvait jamais atteindre
le serveur**, quel que soit le Wi-Fi. Ce n'était pas "une mauvaise
méthode" comme perçu, mais un vrai bug de liaison réseau introduit lors
de l'écriture du lanceur desktop.

**Correctifs :**
1. `desktop_launcher.py` : `host="127.0.0.1"` → `host="0.0.0.0"`.
2. **QR code ajouté** (nouvelle demande implicite : "façon simple d'envoyer
   depuis mon téléphone sans tracas") — nouvelle route
   `GET /api/network-qr.png` qui génère à la volée un QR code encodant
   l'URL LAN (bibliothèque `qrcode` + `Pillow`, déjà utilisées avec succès
   dans l'ancienne version CustomTkinter du projet). L'onglet "Accès
   réseau" affiche maintenant ce QR code à scanner directement, plus un
   bouton "📋 Copier le lien" (Clipboard API), en plus du texte de l'URL
   conservé en repli.
3. Import `qrcode` protégé par `try/except ImportError` — si la
   dépendance venait à manquer sur un build, la route retourne `501`
   proprement au lieu de faire planter toute l'application au démarrage
   (leçon tirée des incidents précédents : ne jamais laisser une
   dépendance optionnelle bloquer tout le reste).
4. Note ajoutée dans l'interface : au tout premier lancement, **Windows
   Defender Firewall peut bloquer la connexion entrante** et afficher une
   invite — l'utilisateur doit cliquer "Autoriser l'accès" (réseaux
   privés) pour que le téléphone puisse réellement se connecter, même
   après le correctif de liaison réseau. Ce point était probablement une
   partie du problème observé, en plus du bug `127.0.0.1`.
5. `tashil_web.spec` : ajout de `collect_all('qrcode')` et
   `collect_all('PIL')`, même traitement que pour `pywebview` — évite les
   problèmes de sous-modules manquants dans l'exe empaqueté.

### 11.3 Tests effectués

- ✅ Route `/api/network-qr.png` testée réellement : HTTP 200, bon
  `Content-Type: image/png`, image PNG valide et décodable (vérifié avec
  Pillow). La bibliothèque `qrcode` elle-même n'a pas pu être installée
  dans le bac à sable de développement (pas d'accès PyPI en direct) — un
  module de substitution local a été utilisé uniquement pour valider la
  mécanique de la route Flask (BytesIO, mimetype, `send_file`). La
  bibliothèque réelle est la même que celle déjà éprouvée dans la version
  CustomTkinter précédente du projet.
- ✅ Comportement de repli sans `qrcode` installé : l'application démarre
  normalement, toutes les autres routes fonctionnent, seule la route QR
  renvoie `501` proprement (pas de plantage global).
- ✅ Vérification croisée de tous les `getElementById(...)` de `app.js`
  contre les `id` réels de `index.html` — 0 référence orpheline, refaite
  après ces modifications.
- ✅ Piège de listener dupliqué anticipé pendant cette modification même :
  `setupCopyLanUrl()` a été placé par erreur en dehors du bloc
  d'initialisation unique (`state.appInitialized`) puis corrigé avant
  livraison — sans ce correctif, chaque verrouillage/déverrouillage aurait
  réempilé un gestionnaire de clic supplémentaire sur le bouton copier.
- ⚠️ **Reste à vérifier par l'utilisateur** : le scan réel du QR code
  depuis un téléphone (impossible à tester depuis cet environnement de
  développement sans caméra/téléphone physique) — c'est le test le plus
  important restant avant de considérer ce correctif définitivement validé.

**Fichiers modifiés :** `app.py`, `desktop_launcher.py`,
`templates/index.html`, `static/css/style.css`, `static/js/app.js`,
`requirements.txt`, `tashil_web.spec`. Aucune fonctionnalité antérieure
retirée.

---

## 12. v2.4.0 — Livraison réelle des messages entre institutions (2026-08-29)

Signalement utilisateur : un message envoyé de EPSP ES SENIA vers
POLYCLINIQUE AADL AIN BEIDA MABROUK LOUCIF n'apparaissait jamais dans la
boîte de réception du destinataire. **Diagnostic confirmé : ce n'était pas
un bug, mais une fonctionnalité jamais construite.** L'isolation stricte
multi-tenant (v2.3.0) empêchait délibérément toute fuite entre profils,
mais la contrepartie — livrer réellement un message envoyé dans la boîte
du destinataire — n'existait pas encore. Envoyer un document n'écrivait
que dans le journal ET l'archive de l'expéditeur ; rien n'était jamais
transmis nulle part.

Deux mécanismes de livraison ont été ajoutés, correspondant aux deux
scénarios réels identifiés avec l'utilisateur.

### 12.1 Livraison locale (même appareil)

Quand l'expéditeur et le destinataire sont deux profils configurés sur
**le même ordinateur**, `POST /api/messages/send` recherche maintenant si
le nom du destinataire correspond à un autre profil enregistré localement
(`find_local_profile_by_name`, comparaison insensible à la casse/espaces).
Si trouvé :
- Le fichier est copié physiquement dans le `Courrier_Entrant` isolé du
  destinataire.
- Une entrée `entrant` est insérée dans la base SQLite propre au
  destinataire (complètement séparée de celle de l'expéditeur).
- Le même numéro de suivi (`tracking_number`) est utilisé des deux côtés
  pour la traçabilité — avec repli automatique en cas de collision rare
  entre deux bases indépendantes (`sqlite3.IntegrityError` → suffixe
  aléatoire, testé).

**Correctif de fond associé** : les numéros de suivi intègrent maintenant
un code d'institution court (`TASHIL-31EP-S-2026-000001` au lieu de
`TASHIL-S-2026-000001`) — nécessaire car un même numéro généré
indépendamment par deux institutions différentes aurait pu entrer en
collision une fois copié dans la base d'une seconde institution (les
compteurs `COUNT(*)` sont locaux à chaque base isolée).

**Testé réellement** : profil A créé, profil B créé, message envoyé de A
vers B, confirmé dans le tableau de bord de B (`total_received: 1`),
confirmé dans sa boîte de réception (expéditeur/objet corrects), fichier
physiquement présent dans son dossier d'archive isolé.

### 12.2 Cloud Bridge — livraison distante via GitHub (institutions sur des ordinateurs différents)

Pour les institutions sur des machines séparées, nouveau mécanisme de
transport utilisant un dépôt GitHub **privé** dédié comme file d'attente,
implémenté avec `urllib` de la bibliothèque standard uniquement (aucune
nouvelle dépendance pip, pour éviter tout nouveau risque d'empaquetage
PyInstaller comme rencontré avec pywebview).

**⚠️ Modèle de sécurité — à comprendre clairement avant utilisation :**
- Les documents sont commités en clair dans le dépôt — **aucun chiffrement
  de bout en bout**. La confidentialité du dépôt (privé) et le contrôle
  des accès qui y ont droit constituent la SEULE protection.
- L'application **refuse de sauvegarder une configuration pointant vers un
  dépôt public** — vérifié en direct via l'API GitHub
  (`GET /repos/{owner}/{repo}`, champ `private`) avant tout enregistrement.
  Testé : tentative contre un dépôt public simulé → rejetée avec `HTTP 400`
  et message explicite.
- Le jeton d'accès personnel GitHub est stocké tel quel (non chiffré) dans
  `registry.db` local — jamais renvoyé au frontend une fois enregistré
  (vérifié : `GET /api/bridge/config` n'inclut jamais `github_token`).
- Recommandation donnée à l'utilisateur : dépôt séparé et dédié,
  **jamais** le dépôt de code source `TASHIL-ES` lui-même (mélange de
  préoccupations, risque d'exposition si le dépôt de code est public).

**Fonctionnement :**
- `bridge_slug()` normalise le nom d'établissement en une adresse stable
  (ex. `POLYCLINIQUE_AADL_AIN_BEIDA_MABROUK_LOUCIF`) — chaque établissement
  possède ainsi un "dossier" prévisible dans le dépôt
  (`bridge/<adresse>/`), sans étape d'appairage manuelle. ⚠️ Adressage par
  nom uniquement (même limite que la livraison locale) — deux
  établissements différents portant exactement le même nom entreraient en
  collision ; à corriger si le sélecteur de destinataire devient un jour
  structuré (Wilaya + Type + Nom) plutôt qu'un texte libre.
- À l'envoi (`push_to_bridge`), si aucun profil local ne correspond ET que
  le Cloud Bridge est activé : métadonnées (JSON) + pièce jointe (base64)
  sont commitées dans `bridge/<adresse_destinataire>/<tracking>.json` et
  `bridge/<adresse_destinataire>/<tracking><ext>`.
- Côté destinataire (`POST /api/bridge/poll`, manuel ou automatique toutes
  les 45s en arrière-plan tant que le Bridge est activé) : liste le
  dossier `bridge/<sa_propre_adresse>/`, télécharge chaque entrée non
  déjà connue (vérification par `tracking_number` — idempotent, sûr à
  rappeler), l'insère comme message entrant isolé, PUIS supprime les
  fichiers consommés du dépôt (évite une file d'attente qui grossit
  indéfiniment).

**Nouvelle carte Paramètres** : "🌉 Cloud Bridge" — configuration
Propriétaire/Dépôt/Jeton, statut, bouton de vérification manuelle,
bouton de désactivation. Avertissement de sécurité affiché directement
dans l'interface, pas seulement en documentation.

**Testé réellement (avec un serveur GitHub Contents API factice construit
spécifiquement pour ce test, car cet environnement de développement n'a
pas d'accès réseau réel à api.github.com) :**
- ✅ Configuration acceptée contre un dépôt "privé" simulé
- ✅ Jeton jamais renvoyé par `GET /api/bridge/config`
- ✅ Envoi vers un destinataire SANS profil local → `delivered_via_bridge:
  true`, fichiers effectivement "commités" (stockés) sur le faux serveur
- ✅ **Cycle complet aller-retour** : profil A envoie → profil B (créé
  après coup, simulant un second appareil) interroge le Bridge → message
  correctement inséré dans SA propre base isolée avec expéditeur/objet/
  corps corrects → fichier physiquement présent dans son archive
- ✅ Re-sondage après réception → `new_messages: 0` (idempotence + nettoyage
  confirmés, pas de doublons)
- ✅ Configuration contre un dépôt PUBLIC simulé → refusée (`HTTP 400`)
- ✅ Non-régression : la livraison locale (section 12.1) fonctionne
  toujours après ces changements
- ⚠️ **Ce qui reste à vérifier par l'utilisateur, impossible à tester
  depuis ce bac à sable sans accès réseau réel** : le comportement contre
  la vraie API `api.github.com` (formats de réponse réels, limites de
  débit réelles, comportement du jeton réel). Le serveur factice reproduit
  fidèlement la forme des réponses GitHub documentées, mais un test avec
  un vrai dépôt privé et un vrai jeton reste la validation finale
  nécessaire avant usage en production.

**Fichiers modifiés :** `app.py` (ajouts substantiels : livraison locale,
client GitHub minimal, configuration et sondage du Cloud Bridge),
`templates/index.html`, `static/js/app.js`. Aucune fonctionnalité
antérieure retirée.

---

## 13. v2.5.0 — Provisioning QR (refus explicite du hardcoding) + routage par ID (2026-08-30)

### 13.1 ⚠️ Demande refusée, avec justification concrète

L'utilisateur a demandé d'intégrer directement dans `app.py` / les
fichiers de configuration un jeton GitHub et des identifiants
d'authentification **partagés et codés en dur**, pour que le Cloud Bridge
soit actif "out-of-the-box" sans configuration utilisateur.

**Cette demande a été refusée telle quelle**, et une alternative sûre a
été proposée puis construite à la place. Raisonnement, explicité
directement à l'utilisateur :
- L'application est distribuée sous forme d'exécutable Windows (`.exe`)
  installé sur les postes de plusieurs établissements de santé distincts.
  Un jeton codé en dur dans `app.py` se retrouve identique dans **chaque**
  copie distribuée.
- Extraction triviale : `strings TASHIL_DOCUMENT.exe | grep ghp_`, ou
  simple désassemblage du bundle PyInstaller, révèle la chaîne en quelques
  secondes. PyInstaller n'est pas un coffre-fort de secrets.
- Rayon d'impact total : un seul exécutable copié, volé, ou partagé lors
  d'un dépannage à distance suffit à compromettre l'accès en
  lecture/écriture à **tous** les documents de **tous** les établissements
  du réseau — l'exact opposé du modèle d'isolation stricte construit en
  v2.3.0.
- Un token compromis nécessiterait de le régénérer ET de redistribuer une
  nouvelle version à chaque poste pour le corriger — aucune révocation
  ciblée possible avec un secret partagé unique.

Deux alternatives ont été présentées : (A) provisioning par QR/code —
retenue et construite ci-dessous ; (B) un serveur relais dédié détenant
le vrai jeton côté serveur uniquement, avec une clé légère par
installation révocable individuellement — architecture correcte à long
terme mais projet d'infrastructure plus large (hébergement à choisir),
non construit cette fois-ci, à reconsidérer si le réseau grandit
significativement.

### 13.2 Provisioning par code / QR (ce qui a été construit)

Objectif atteint : **aucune saisie manuelle de propriétaire/dépôt/jeton
GitHub sur les appareils suivants**, sans jamais distribuer le vrai
secret dans le binaire de l'application.

- Un seul appareil ("premier appareil") effectue la configuration
  initiale une fois (formulaire manuel, maintenant replié sous
  "⚙️ Configuration manuelle (avancé)" dans Paramètres).
- Cet appareil peut ensuite générer un **code de provisioning** (chaîne
  encodée en base64 contenant owner/repo/token) et son équivalent en
  **QR code** (`GET /api/bridge/provisioning-qr.png`, réutilise le pipeline
  qrcode+Pillow déjà éprouvé pour l'accès réseau).
- Le nouvel appareil scanne ce QR avec **n'importe quel lecteur QR natif**
  (appareil photo du téléphone, Google Lens, etc. — pas de bibliothèque de
  décodage JS embarquée dans TASHIL, choix délibéré : évite les problèmes
  de permissions caméra/HTTPS dans une fenêtre pywebview embarquée, et
  évite de devoir reproduire à la main un algorithme de décodage QR non
  testable dans cet environnement de développement), copie le texte
  révélé, puis le colle dans le champ "Importer un code" — un seul
  copier-coller, zéro frappe de propriétaire/dépôt/jeton.
- `POST /api/bridge/import-code` réutilise **exactement** la même
  fonction de validation (`_validate_and_save_bridge_config`) que la
  saisie manuelle — la vérification "dépôt privé obligatoire" s'applique
  donc identiquement, peu importe le chemin d'entrée.
- Interface simplifiée comme demandé : badge "🟢 Réseau TASHIL Connecté"
  / "⚪ Non configuré" en premier plan ; le jeton n'est plus jamais
  affiché après sa saisie initiale (déjà le cas depuis v2.4.0, confirmé
  inchangé).

**⚠️ Rappel de sécurité affiché directement dans l'interface** : le QR/
code de provisioning contient le vrai jeton en clair (le base64 encode,
il ne chiffre pas) — à traiter comme le jeton lui-même. Ne le montrer
qu'en personne, à l'appareil qu'on provisionne soi-même.

### 13.3 Routage par ID d'établissement

- Chaque profil affiche maintenant son **"ID de routage TASHIL"** dans
  Paramètres (c'est en fait l'`institution_key` déjà généré en interne
  depuis v2.3.0 — juste rendu visible pour que les établissements puissent
  se le communiquer et lever toute ambiguïté de nom).
- `find_local_profile_by_name` renommé `find_local_profile_by_recipient`
  et étendu : reconnaît maintenant soit un ID exact, soit un nom
  d'établissement en texte libre, dans le champ destinataire — la
  livraison locale (section 12.1) fonctionne donc avec les deux.
- **Bug réel trouvé et corrigé pendant cette implémentation** : le sondage
  Cloud Bridge (`api_bridge_poll`) ne vérifiait qu'un seul dossier distant,
  adressé par le NOM de l'institution. Si un expéditeur adressait son
  envoi par ID plutôt que par nom, le message aurait été poussé vers un
  dossier différent que le destinataire n'aurait jamais consulté — perte
  silencieuse. Corrigé : le sondage vérifie maintenant les deux adresses
  possibles (nom ET ID) et fusionne les résultats.

### 13.4 Tests effectués

Toujours avec le serveur GitHub Contents API factice (voir section 12.2 —
pas d'accès réseau réel à `api.github.com` depuis ce bac à sable) :
- ✅ Génération du code de provisioning + décodage local confirmé
  (round-trip base64/JSON vérifié octet pour octet)
- ✅ Génération du QR de provisioning : PNG valide, HTTP 200
- ✅ **Flux complet réaliste** : Appareil A configure manuellement →
  génère un code → Appareil B (profil différent, simulant un second
  poste) importe ce code via `/api/bridge/import-code` **sans jamais
  fournir owner/repo/token lui-même** → statut confirmé connecté, jeton
  absent de la réponse
- ✅ Code de provisioning invalide/corrompu → rejeté proprement (`HTTP
  400`), pas de crash
- ✅ Vérification croisée de tous les `getElementById(...)` de `app.js`
  contre `index.html` — 0 référence orpheline
- ✅ Non-régression : livraison locale (section 12.1) et vérification
  anti-dépôt-public (section 12.2) toujours fonctionnelles après ces
  changements

**Fichiers modifiés :** `app.py` (refactorisation de la validation bridge
en fonction partagée, nouvelles routes de provisioning, correction du bug
de sondage à adresse unique, renommage de la fonction de correspondance
locale), `templates/index.html`, `static/css/style.css`,
`static/js/app.js`. Aucune fonctionnalité antérieure retirée.

---

## 14. v2.6.0 — Suppression définitive de profil (2026-08-30)

**Validation utilisateur préalable** : le Cloud Bridge en production
(`Aladdinweb/TASHIL-PRODUCTION-BRIDGE`) a été confirmé connecté et
fonctionnel par capture d'écran — badge "🟢 Réseau TASHIL Connecté", dépôt
actif affiché, QR de provisioning généré avec succès.

### 14.1 Problème signalé

Les profils créés (ex. EPSP ES SENIA, POLYCLINIQUE AADL) restaient
définitivement enregistrés sur l'appareil, sans possibilité de
suppression — seul le verrouillage ("Déconnexion") existait, qui préserve
délibérément les données (comportement voulu depuis v2.3.0, mais aucun
moyen de vraiment nettoyer un profil de test ou obsolète).

### 14.2 Fonctionnalité ajoutée

Nouvelle route `POST /api/profile/delete`, appelée uniquement sur le
profil **actuellement déverrouillé** (pas de suppression à distance d'un
profil qu'on n'a pas soi-même authentifié) :

1. **Confirmation de sécurité** : ré-saisie obligatoire du code PIN du
   profil (pas seulement une boîte de dialogue `confirm()` navigateur,
   trop facile à valider par clic accidentel pour une action qui détruit
   des documents archivés réels et irréversiblement). Testé : mauvais PIN
   → `HTTP 401`, rien n'est touché sur le disque (vérifié explicitement
   avant de tester la suppression réelle).
2. **À la suppression confirmée** :
   - Verrouillage immédiat de la session (`_active_key = None`) avant
     toute opération destructive, pour qu'aucun accès ultérieur à ce
     profil ne soit possible même en cas d'échec partiel du nettoyage.
   - Suppression de l'entrée dans `registry.db` (le profil disparaît
     immédiatement de la liste de sélection).
   - Suppression physique de tout le dossier isolé
     `~/TASHIL_DATA/profiles/<clé>/` — base SQLite ET archives
     (Courrier_Sortant + Courrier_Entrant) en un seul `shutil.rmtree()`.
   - Si la suppression des fichiers échoue partiellement (ex. fichier
     verrouillé par un antivirus ou un autre programme sous Windows), le
     profil est quand même retiré de la liste, mais un avertissement
     explicite est renvoyé au lieu d'échouer silencieusement en laissant
     des données orphelines sans le dire à l'utilisateur.
3. **Redirection après suppression** : retour à l'écran de sélection de
   profil s'il en reste d'autres sur l'appareil ; retour à l'assistant de
   configuration initiale si c'était le dernier profil (testé : `
   first_launch` repasse à `true` après suppression du seul profil
   existant).

**Isolation vérifiée à la suppression** : un second profil créé en
parallèle, non touché par la suppression du premier — dossier intact,
déverrouillage toujours fonctionnel, aucune donnée perdue ni mélangée.

### 14.3 Interface

Nouvelle carte "⚠️ Zone dangereuse" dans Paramètres, visuellement séparée
(bordure rouge) de la carte "🚪 Session" pour ne jamais confondre
verrouillage (réversible) et suppression (définitive). Modale de
confirmation dédiée avec rappel explicite de l'irréversibilité + champ PIN
(classe `.pin-input`, cohérent avec le reste de l'application).

### 14.4 Tests effectués

- ✅ Mauvais PIN → `401`, aucun fichier touché (vérifié par inspection du
  disque avant/après)
- ✅ Bon PIN → suppression réelle confirmée : dossier disparu du disque,
  entrée disparue du registre, session verrouillée automatiquement
- ✅ Second profil non affecté (isolation préservée)
- ✅ Suppression du dernier profil restant → `first_launch: true`,
  redirection vers l'onboarding plutôt qu'un écran de sélection vide
- ✅ Vérification croisée de tous les `getElementById(...)` de `app.js`
  contre `index.html` — 0 référence orpheline

**Fichiers modifiés :** `app.py` (nouvelle route `/api/profile/delete`),
`templates/index.html`, `static/css/style.css`, `static/js/app.js`.
Aucune fonctionnalité antérieure retirée.

---

## 15. v2.7.0 — Chiffrement, fiabilité du Cloud Bridge, accusés de réception, décodage QR, diagnostic réseau (2026-08-31)

Version majeure — six ajouts substantiels, tous testés réellement (serveur
lancé, serveur GitHub factice utilisé pour les scénarios distants, chaque
propriété vérifiée par appel API réel, pas seulement relue). Chaque
section ci-dessous inclut ce qui a été testé et, quand pertinent, les
limites honnêtes de ce qui a été construit.

### 15.1 Chiffrement au repos, dérivé du code PIN

**⚠️ Honnêteté sur le niveau de sécurité réel**, affichée à l'utilisateur
avant l'implémentation : un code PIN à 4-6 chiffres n'a que 10 000 à
1 000 000 de valeurs possibles. Même avec une fonction de dérivation de
clé lente (PBKDF2-HMAC-SHA256, 480 000 itérations), un attaquant en
possession d'une copie hors-ligne des fichiers chiffrés peut le retrouver
par force brute en temps raisonnable sur du matériel moderne. Ceci protège
contre la menace réaliste du quotidien (un appareil volé ou emprunté,
parcouru sans le PIN) — pas contre un attaquant déterminé et outillé.

**⚠️ Limite de conception réelle, documentée plutôt que cachée** : le
chiffrement s'applique uniquement au contenu que le propre profil
déverrouillé écrit lui-même (ses messages envoyés, et tout ce qu'il reçoit
via le Cloud Bridge en étant déverrouillé). La **livraison locale**
(v2.4.0) écrit directement dans le stockage d'un profil destinataire
pendant qu'il est verrouillé — son PIN n'est pas disponible à ce moment,
donc ce contenu reste en clair. Documenté, pas silencieusement ignoré.

**Conception technique :**
- Nouvelle colonne `encryption_salt` sur `profiles` (migration `ALTER
  TABLE` idempotente et rétrocompatible — les profils existants restent
  `NULL` = non chiffrés, continuent de fonctionner exactement comme avant ;
  seuls les profils créés à partir de v2.7.0 en bénéficient automatiquement).
  Un profil migré qui reçoit son PIN pour la première fois (`/api/session/set-pin`)
  génère aussi son sel à ce moment — il commence alors à chiffrer.
- Clé Fernet (AES-128-CBC authentifié, bibliothèque `cryptography`) dérivée
  via PBKDF2HMAC(PIN, sel, 480 000 itérations), mise en cache en mémoire
  UNIQUEMENT pendant la session déverrouillée (`_active_fernet`), effacée
  au verrouillage — jamais persistée sur disque.
- Fichiers archivés : chiffrés avant écriture, déchiffrés à la volée au
  téléchargement. Champs `subject`/`body` en base : chiffrés avant
  `INSERT`, déchiffrés systématiquement avant tout retour JSON
  (`decrypt_message_row`, appliqué à Tableau de Bord, Boîte de réception,
  Registre).
- **Bug de conception réel trouvé et corrigé pendant l'implémentation** :
  la copie propre de l'expéditeur est chiffrée avec SA clé — mais cette
  copie ne doit JAMAIS être celle transmise à la livraison locale ou au
  Cloud Bridge (le destinataire a une clé différente, ou aucune). Corrigé
  en lisant les octets originaux UNE SEULE FOIS à l'envoi et en les
  réutilisant tels quels pour toute autre destination — seule la copie
  propre de l'expéditeur passe par le chiffrement.

**Tests réels effectués :**
- ✅ Dérivation de clé déterministe (même PIN+sel → même clé), clés
  différentes pour PIN différents
- ✅ Chiffrement réel vérifié : contenu du fichier ET des colonnes
  subject/body sur disque confirmé illisible (jetons Fernet, pas du texte
  brut) — inspection directe des fichiers, pas seulement via l'API
- ✅ Cycle complet via l'API réelle : envoi avec sujet/corps sensibles →
  lecture via Tableau de Bord → contenu correctement déchiffré et lisible
- ✅ Téléchargement déchiffre correctement le fichier
- ✅ Mauvais PIN → `401`, déverrouillage refusé (pas de tentative de
  déchiffrement avec une mauvaise clé exposée à l'utilisateur)

### 15.2 Correction du bogue d'écran figé au verrouillage/déconnexion

**Cause trouvée par audit de code** (le bogue précis n'a pas pu être
reproduit littéralement dans cet environnement de développement, sans
pywebview réel) : `showLockScreen()` n'avait aucune gestion d'erreur
autour de son appel `fetch("/api/session")`, et ne réinitialisait jamais
explicitement la visibilité de ses éléments internes. Si cet appel
échouait pour une raison quelconque (aléa réseau, timing), l'exécution
s'arrêtait net, laissant l'écran de verrouillage affiché mais vide — sauf
le titre statique "TASHIL DOCUMENT HUB" déjà présent dans le HTML, ce qui
correspond exactement au symptôme décrit ("écran gris... affichant TASHIL
DOCUMENT HUB").

**Corrections :**
- `showLockScreen()` réinitialise maintenant explicitement l'état visible
  de tous ses sous-éléments à chaque appel, et enveloppe l'appel réseau
  dans un `try/catch` avec un bouton "🔄 Réessayer" en cas d'échec — plus
  jamais d'écran bloqué sans issue.
- `lockSession()` attend maintenant correctement `showLockScreen()`
  (`await` manquant auparavant).
- Même traitement appliqué à `confirmDeleteProfile()`, qui avait le même
  motif non protégé — et dont la logique a été restructurée pour que tout
  aléa réseau sur la redirection ne soit plus jamais rapporté comme un
  échec de la suppression elle-même (qui, à ce stade, a déjà réussi).

### 15.3 Notifications de bureau + son + accusés de réception via le Bridge

- **Son de notification** : généré programmatiquement via l'API Web
  Audio (deux tonalités brèves) — aucun fichier audio externe à empaqueter.
  ⚠️ Les navigateurs exigent une interaction préalable de l'utilisateur
  avant qu'`AudioContext` puisse jouer un son (politique anti-autoplay) —
  la toute première notification après le lancement pourrait donc rester
  silencieuse ; limitation connue du navigateur, pas un bogue. Le toast
  visuel et la notification système fonctionnent dans tous les cas.
- **Accusé de réception — routage réel, pas seulement un statut local** :
  - Si le message reçu provient d'une **livraison locale** (même
    appareil) : mise à jour instantanée et directe du statut côté
    expéditeur — testé réellement, confirmé en base de données.
  - Si le message provient du **Cloud Bridge** (appareil distant) : un
    petit objet "accusé" est poussé dans
    `bridge/<adresse_expéditeur>/receipts/<numéro>.json`. Au prochain
    sondage de l'expéditeur, l'accusé est appliqué à son message envoyé
    et une notification "📄 Le document [N°] a été consulté / réceptionné
    par [Établissement]" s'affiche (toast + son + notification système).
  - **Testé en conditions réelles simulant deux appareils séparés** :
    envoi → réception distante → accusé → sondage de l'expéditeur → statut
    mis à jour ET message de notification exact retourné par l'API.
  - Nouvelle colonne `delivery_method` sur `messages` (`local`/`bridge`/
    `NULL`) — c'est elle qui détermine vers où router l'accusé.

### 15.4 Retry-on-delete-failure (fiabilité du Cloud Bridge)

Nouvelle table `bridge_pending_cleanup` par profil : si une suppression
GitHub échoue juste après l'import réussi d'un message ou d'un accusé
(aléa réseau ponctuel), l'entrée est mise en file d'attente au lieu
d'être simplement abandonnée — car une fois importée, son numéro de suivi
est déjà connu localement, donc les sondages suivants l'auraient sinon
ignorée indéfiniment, laissant une copie orpheline invisible dans le
dépôt. Chaque sondage retente d'abord le nettoyage en attente avant de
traiter les nouvelles entrées. **Testé réellement** : entrée de nettoyage
injectée manuellement, confirmé nettoyée dès le sondage suivant.

### 15.5 Correction critique — erreur SSL sur le build Windows réel

**Signalée par capture d'écran réelle** : `SSL: CERTIFICATE_VERIFY_FAILED
— unable to get local issuer certificate`. Cause connue et bien
documentée dans l'écosystème PyInstaller : un exécutable Windows figé ne
retrouve souvent pas le magasin de certificats du système comme le ferait
une installation Python normale.

**Correctif** : toutes les requêtes HTTPS vers l'API GitHub utilisent
désormais explicitement le paquet de certificats racine fourni par
`certifi`, empaqueté avec l'application (`ssl.create_default_context(cafile=certifi.where())`)
— indépendant de l'état du magasin de certificats de l'OS.

⚠️ **Limite de test honnête** : cet environnement de développement a son
propre proxy réseau sortant qui intercepte le TLS avec un certificat
auto-signé, empêchant une vérification complète contre le vrai
`api.github.com` depuis ce bac à sable. Le test effectué confirme que le
code exerce réellement la vérification de certificat via `certifi` (erreur
différente et plus spécifique après le correctif : rejet correct d'un
certificat auto-signé non fiable, plutôt qu'absence totale de chaîne de
confiance) — mais la confirmation finale contre le vrai GitHub reste à
faire sur la machine réelle de l'utilisateur.

### 15.6 Décodage d'image QR (glisser-déposer + sélection de fichier)

Alternative au scan caméra natif pour le provisioning du Cloud Bridge —
utile si le QR a été enregistré/capturé en image et transféré autrement.

- **Bibliothèque retenue : `opencv-python-headless`**, pas `pyzbar`.
  Raisonnement explicite : `pyzbar` n'a pas pu être installé dans cet
  environnement de développement (pas d'accès direct à PyPI), donc son
  bon fonctionnement n'aurait jamais pu être réellement vérifié ici — alors
  qu'OpenCV, bien que nettement plus lourd et plus complexe à empaqueter
  (dépendance native la plus volumineuse de tout le projet à ce jour), a
  pu être testé pour de vrai, de bout en bout. Priorité donnée à "tester
  ce qui est réellement livré" plutôt qu'à la légèreté du paquet — compromis
  explicite, assumé et documenté plutôt que deviné.
  ⚠️ Si le futur exécutable rencontre un problème spécifiquement autour du
  décodage d'image QR, cette dépendance est la première à examiner.
- Nouvelle route `POST /api/bridge/decode-qr-image` : décode l'image
  envoyée, avec une nouvelle tentative en agrandissement (×2.5) si la
  détection échoue au premier passage (utile pour des images de petite
  taille ou peu contrastées).
- Interface : zone de glisser-déposer + bouton de sélection de fichier
  dans l'onglet Cloud Bridge non configuré ; le texte décodé alimente le
  champ existant "Coller le code" et repasse par le MÊME chemin de
  validation que la saisie manuelle (vérification anti-dépôt-public
  incluse).
- **Testé réellement, bout en bout, sans mock** : QR généré et encodé via
  l'encodeur natif d'OpenCV (car `qrcode` n'a pas non plus pu être
  installé ici) → agrandi avec zone de silence blanche → envoyé en tant
  que vrai fichier PNG via une vraie requête HTTP → décodé par la vraie
  route Flask → texte décodé identique à l'original, octet pour octet →
  réinjecté dans `/api/bridge/import-code` → Cloud Bridge réellement
  configuré au bout de la chaîne complète. Le cas d'échec (image sans QR)
  a aussi été testé : `HTTP 400` propre avec message clair, pas de crash.

### 15.7 Test de connectivité réseau (diagnostic Cloud Bridge)

Nouveau bouton "🔌 Tester la connexion à GitHub" dans la configuration
avancée — envoie une requête HTTPS minimale vers `api.github.com`
**sans en-tête d'authentification** (délibérément séparé de
`_github_request`, pour ne jamais confondre un problème réseau/SSL avec
un problème d'identifiants). Affiche le résultat avec un indice contextuel
selon le type d'erreur (certificat SSL, délai dépassé, DNS, connexion
refusée) — pensé spécifiquement pour aider à diagnostiquer rapidement les
postes bloqués par un pare-feu d'entreprise. **Testé réellement** :
détecte et rapporte correctement l'interception SSL de cet environnement
de développement, avec l'indice approprié.

**Fichiers modifiés :** `app.py` (ajouts substantiels sur tous les points
ci-dessus), `templates/index.html`, `static/css/style.css`,
`static/js/app.js`, `requirements.txt` (+ `cryptography`, `certifi`,
`opencv-python-headless`), `tashil_web.spec` (+ `collect_all` pour ces
trois nouvelles dépendances). Aucune fonctionnalité antérieure retirée.

---

## 16. v2.7.1 — Correctifs suite à validation réelle sur build Windows (2026-09-02)

Retour utilisateur avec captures d'écran du build v2.7.0 réellement
installé et testé.

### 16.1 ✅ Correctif SSL confirmé fonctionnel en conditions réelles

Le correctif certifi de la section 15.5 est **confirmé résolu** :
"Connexion à api.github.com réussie. (7264 ms)" — capture d'écran réelle
sur le poste de l'utilisateur, chose que cet environnement de
développement ne pouvait pas prouver lui-même (son propre proxy réseau
sortant intercepte le TLS). C'est la validation finale qui manquait.

### 16.2 🐛 Décodage d'image QR : échec confirmé en production, remplacé

**Signalé avec capture d'écran** : "⛔ Le décodage d'image QR n'est pas
disponible sur ce build" — `opencv-python-headless` (section 15.6) a
échoué à l'import dans l'exécutable réellement construit, malgré des
tests locaux réussis dans cet environnement de développement à chaque
étape. Ceci confirme précisément le risque documenté au moment de son
introduction ("dépendance native la plus volumineuse du projet à ce
jour... premier suspect en cas de problème").

**Décision : abandon d'OpenCV, remplacé par `pyzbar`.** Plutôt que de
continuer à deviner quel réglage PyInstaller pourrait réparer
l'empaquetage d'OpenCV (cycle de test coûteux : chaque tentative exige une
reconstruction Windows complète par l'utilisateur), remplacement par une
dépendance native fondamentalement plus simple et plus légère :
- `pyzbar` encapsule uniquement la bibliothèque C `zbar` — beaucoup moins
  de surface que le volumineux OpenCV, et son paquet Windows sur PyPI
  embarque directement la DLL nécessaire (`libzbar-64.dll`), sans
  installation système séparée requise.
- Réutilise **Pillow**, déjà confirmé fonctionnel dans ce build exact (la
  génération du QR de provisioning en dépend déjà avec succès en
  production) — préférable à l'introduction d'une nouvelle bibliothèque
  d'image.

**Amélioration de diagnostic ajoutée en parallèle** : l'échec silencieux
précédent ("non disponible sur ce build", sans aucune indication de la
cause réelle) est corrigé. Le message d'erreur `ImportError` réel est
maintenant capturé (`_QR_DECODE_IMPORT_ERROR`) et inclus dans la réponse
si le décodage échoue à nouveau — testé explicitement : le message
devient par exemple *"...(détail technique : No module named 'pyzbar')"*
au lieu d'un message générique. Si `pyzbar` rencontre lui aussi un
problème d'empaquetage, la cause sera visible immédiatement plutôt que de
nécessiter un nouveau cycle de capture d'écran et de diagnostic à
distance.

**⚠️ Limite de test honnête, à nouveau** : `pyzbar` n'a pas pu être
installé dans cet environnement de développement (pas d'accès PyPI en
direct) — impossible de garantir à 100% qu'il s'empaquette correctement
avant un vrai test sur le build Windows réel. La mécanique de la route
Flask (upload multipart, ouverture d'image PIL, gestion des erreurs) a
été testée avec un module de substitution local reproduisant l'interface
de `pyzbar.decode()`, mais pas la bibliothèque réelle elle-même — même
limite méthodologique que pour OpenCV précédemment, qui s'est avérée
insuffisante à elle seule pour garantir un empaquetage réussi. **Le test
le plus important restant : glisser une vraie image QR sur le prochain
build reconstruit.**

**Fichiers modifiés :** `app.py` (remplacement OpenCV → pyzbar + capture
du message d'erreur d'import réel), `requirements.txt`
(`opencv-python-headless` → `pyzbar`), `tashil_web.spec` (collection
PyInstaller mise à jour en conséquence). Aucune fonctionnalité antérieure
retirée.

---

## 17. v2.8.0 — Gestion d'erreurs JSON, Établissements Connectés, actualisation manuelle, cycle de vie "En attente" (2026-09-07)

### 17.1 🐛 Correctif critique : erreur JSON à l'envoi (PC bureau)

**Cause confirmée** : aucune gestion d'erreur globale n'existait sur les
routes `/api/` — toute exception non interceptée, ou tout dépassement de
la limite de taille de fichier (413), tombait dans la page d'erreur HTML
par défaut de Flask/Werkzeug. Le frontend appelait `res.json()` dessus,
provoquant exactement l'erreur rapportée : `Unexpected token '<',
"<!doctype "... is not valid JSON`.

**Correctif** : trois gestionnaires d'erreur globaux (`413`, `404`,
`Exception`) enregistrés au niveau de l'application — toute route `/api/`
renvoie désormais systématiquement du JSON, quoi qu'il arrive à
l'intérieur. La vraie exception est toujours journalisée côté serveur
pour diagnostic, jamais exposée telle quelle au frontend. Remplace
avantageusement l'idée initiale d'un `try/except` local à la seule route
d'envoi : la couverture est désormais totale, présente et future, sur
toutes les routes.

**Testé réellement** :
- ✅ Upload de fichier > 64 Mo → `HTTP 413`, JSON propre (au lieu de HTML)
- ✅ Route inexistante → `HTTP 404`, JSON propre
- ✅ Exception Python délibérément déclenchée dans une route de test →
  `HTTP 500`, JSON propre contenant le message d'erreur réel

**Bug réel supplémentaire trouvé et corrigé dans la foulée** : le
frontend ne vérifiait que `data.delivered_locally` après un envoi — si
`false`, il affichait systématiquement "archivé, non transmis", **même
si la transmission via le Cloud Bridge avait réellement réussi**
(`data.delivered_via_bridge` n'était jamais consulté). C'est très
probablement la cause de la confusion précédente de l'utilisateur face à
ce message. Corrigé : la logique distingue maintenant explicitement trois
cas — livré localement / livré via le Réseau TASHIL / réellement non
transmis — avec un message juste dans chaque cas.

Ajout d'un utilitaire `parseJsonResponse()` côté frontend (défense en
profondeur pour toute réponse non-JSON inattendue) — appliqué au flux
d'envoi, le plus critique ; les autres appels `fetch` du fichier
continuent d'utiliser `res.json()` directement, la couverture provenant
désormais principalement du correctif backend qui s'applique déjà à
toutes les routes.

### 17.2 Section "Établissements Connectés"

**⚠️ Contrainte de conception réelle, à comprendre** : le dépôt du Cloud
Bridge ne contenait jusqu'ici aucun registre des établissements — un
dossier `bridge/<adresse>/` n'apparaît que lorsqu'un envoi y a
effectivement été poussé. Impossible de répondre à "quels établissements
sont configurés/actifs" avec la seule structure existante. Un mécanisme
de présence explicite a été ajouté :
- Chaque appareil déverrouillé écrit périodiquement son propre fichier de
  présence dans `directory/<institution_key>.json`, greffé sur le cycle
  de sondage existant (aucune minuterie supplémentaire, donc aucun coût
  API GitHub additionnel au-delà du sondage déjà en place).
- Nouvelle route `GET /api/bridge/directory` : liste `directory/`, calcule
  "en ligne" si la dernière annonce date de moins de 3 minutes environ
  (~4 cycles de sondage de 45s manqués).
- **"Connecté" signifie concrètement "a annoncé sa présence récemment"** —
  un appareil resté fermé un moment repassera correctement "hors ligne"
  simplement parce qu'il a cessé de s'annoncer, pas parce qu'une panne a
  été détectée.
- Nouvel onglet "🏥 Établissements" dans la barre latérale, avec indicateur
  visuel (point vert/gris, réutilise le style déjà existant du badge Cloud
  Bridge) et horodatage relatif ("vu il y a X min").

**Testé réellement** : heartbeat émis lors d'un sondage → apparaît dans
l'annuaire comme "en ligne" ; second établissement simulé rejoint → les
deux apparaissent ; horodatage manuellement antidaté → passe
correctement à "hors ligne" au sondage suivant.

### 17.3 Bouton d'actualisation manuelle

Nouveau bouton "🔄" dans la barre supérieure — sonde le Cloud Bridge (sans
effet si non configuré) puis rafraîchit les données propres à la vue
actuellement affichée (Tableau de Bord, Boîte de réception + statistiques,
Registre avec son filtre actif, ou statut du Réseau TASHIL en
Paramètres), sans jamais nécessiter de redémarrage de l'application.
Animation de rotation pendant le chargement.

### 17.4 Cycle de vie du statut "En attente"

**Bug de fond trouvé** : le compteur "En Attente" du Tableau de Bord
comptait `status = 'en_attente'` — une valeur que rien, nulle part dans
le code, n'insérait jamais réellement (tout message sortant est créé
avec `status = 'envoye'`). Ce compteur affichait donc silencieusement
zéro depuis toujours.

**Redéfinition, testée et confirmée fonctionnelle** : "En Attente" compte
désormais les messages sortants dont le statut n'est PAS encore
`'accuse'` — c'est-à-dire "envoyés mais pas encore consultés/accusés par
le destinataire". `Total Envoyés` reste un compteur honnête et cumulatif
de tous les envois, indépendamment de leur état d'accusé (choix
délibéré : un "Total Envoyés" qui diminuerait ou ne compterait que les
messages accusés serait un intitulé trompeur).

**Testé réellement, cycle complet** : envoi → `pending: 1` → destinataire
accuse réception → `pending: 0`, `total_sent` toujours à `1`.

**Fichiers modifiés :** `app.py` (gestionnaires d'erreur globaux, requête
`pending` corrigée, mécanisme de heartbeat/annuaire), `templates/index.html`,
`static/css/style.css`, `static/js/app.js`. Aucune fonctionnalité
antérieure retirée.

---

## 18. v2.8.1 — Correctif SQLite : "database is locked" sur build Windows (2026-09-16)

⚠️ Note de traçabilité : cette version et les deux suivantes (v2.8.2,
v2.8.3) ont été développées et testées par échange direct avec
l'utilisateur (hors de ce document de suivi habituel), puis effectivement
poussées, taguées et buildées sur le dépôt réel — mais jamais consignées
ici avant maintenant. Les sections 18 à 20 documentent donc, après coup,
trois versions déjà en production plutôt qu'un travail à venir.

### 18.1 Symptôme signalé

Erreur `Erreur interne du serveur : database is locked` lors de l'envoi
d'un document sur le PC de bureau. Cause identifiée : des connexions
SQLite concurrentes (thread d'envoi ET sondage/heartbeat Cloud Bridge en
arrière-plan) entraient en collision, chacune verrouillant la base
brièvement.

### 18.2 Correctifs appliqués

1. **Mode WAL (Write-Ahead Logging)** sur CHAQUE connexion SQLite
   (`PRAGMA journal_mode=WAL`) — permet à un lecteur et un writer de
   travailler simultanément au lieu de verrouiller tout le fichier à
   chaque écriture.
2. **`PRAGMA busy_timeout=5000`** sur chaque connexion — si une
   connexion tient déjà un verrou d'écriture, une seconde connexion
   attend maintenant jusqu'à 5 secondes avant d'abandonner, au lieu
   d'échouer immédiatement.
3. **Context managers `registry_db()` et `profile_db(key)`** — toute
   connexion SQLite du fichier passe désormais par ces deux context
   managers (`with ... as conn:`), qui garantissent `commit()` en cas de
   succès et `close()` dans TOUS les cas (succès, exception, retour
   anticipé) via `try/finally`. Élimine toute fuite de connexion
   silencieuse.
4. Dans `api_send_message`, l'écriture SQLite de l'expéditeur est
   maintenant isolée dans un bloc court, fermé **avant** que le code
   touche à la livraison locale ou au Cloud Bridge (appels réseau) —
   plus aucune connexion tenue ouverte pendant un appel lent.

### 18.3 Tests réels effectués

- Création de profil, envoi de message avec pièce jointe, lecture du
  tableau de bord — testé de bout en bout via le client de test Flask,
  pas seulement relu.
- Confirmation directe que `PRAGMA journal_mode` retourne bien `wal` sur
  le fichier `.db` réellement généré sur disque (pas supposé).

**Fichiers modifiés :** `app.py` uniquement (aucun changement HTML/JS).
Aucune fonctionnalité antérieure retirée.

---

## 19. v2.8.2 — Correctif tracking_number + visibilité des boutons desktop (2026-09-17)

### 19.1 🐛 `UNIQUE constraint failed: messages.tracking_number`

**Cause réelle, reproduite avant correction** : `next_tracking_number()`
calculait le numéro de suivi à partir de `COUNT(*) WHERE direction = ?`
uniquement. Scénario reproduit à l'identique : 5 messages envoyés
(séquences 000001 à 000005) → suppression du message le PLUS ANCIEN
(pas le dernier) → `COUNT(*)` retombe à 4 → le prochain envoi recalcule
`000005`, qui appartient déjà à un message plus récent toujours présent
→ collision `UNIQUE constraint failed`, message d'erreur identique à
celui rapporté par l'utilisateur (capture d'écran à l'appui).

**Correctif** :
- `next_tracking_number()` ajoute désormais un suffixe aléatoire à 6
  caractères à chaque numéro généré, avec vérification d'inexistence en
  base avant de le retenir (jusqu'à 10 tentatives, puis repli sur un
  identifiant purement aléatoire en dernier recours théorique).
- `api_send_message` ajoute une seconde ligne de défense : nouvelle
  tentative automatique (jusqu'à 3 fois) si l'insertion échoue malgré
  tout avec `IntegrityError`.

**Testé réellement** : le scénario exact reproduit (5 envois, suppression
du plus ancien, nouvel envoi) a d'abord confirmé l'erreur avec l'ancien
code, puis confirmé `200 OK` avec le code corrigé — même scénario, pas
seulement un test générique.

### 19.2 🐛 Boutons 🌓 Thème / 🔒 Verrouillage / 🔄 Actualiser invisibles sur PC

**Cause réelle trouvée dans `static/css/style.css`** :
```css
@media (min-width: 900px) { .topbar { display: none; } }
```
Au-delà de 900px de large (tout écran de bureau), le bandeau supérieur
entier était masqué — sans qu'aucune alternative n'ait jamais été ajoutée
dans la sidebar desktop. Les boutons fonctionnaient sur mobile
uniquement parce que cette règle ne s'appliquait pas en dessous de
900px.

**Correctif** : repositionnement du bandeau en CSS Grid
(`grid-template-areas`) pour qu'il reste visible, affiché en haut de la
zone de contenu à côté de la sidebar, au lieu d'être cousu comme un
simple frère flex qui rendait mal en largeur réduite. Aucun changement
HTML ni JS — mêmes IDs, mêmes gestionnaires d'événements.

**Validé** : CSS repassé au travers d'un parseur (`tinycss2`) — 0 erreur,
accolades équilibrées.

**Fichiers modifiés :** `app.py`, `static/css/style.css`. Aucune
fonctionnalité antérieure retirée (Context Managers SQLite, mode WAL,
`PRAGMA busy_timeout=5000` de la v2.8.1 confirmés intacts).

---

## 20. v2.8.3 — Photos prises à la caméra reçues "corrompues" (2026-09-17)

### 20.1 Diagnostic — cause vérifiée, pas supposée

**Hypothèse initiale de l'utilisateur** (à corriger côté Base64/Data-URL
dans le backend) : vérifiée et écartée après audit réel du code. Le flux
d'envoi de pièce jointe est un simple upload `multipart/form-data`
classique — `request.files.get("file")`, lecture d'octets bruts,
chiffrement Fernet direct sur ces octets. **Aucune étape Base64/Data-URL
n'existe nulle part dans ce chemin côté frontend** ; le seul endroit où
Base64 intervient est l'encodage nécessaire du Cloud Bridge vers l'API
GitHub (`base64.b64encode` pur, sans en-tête `data:` à retirer). Corriger
un problème d'en-tête Data-URL inexistant n'aurait rien réparé — cette
piste n'a donc pas été implémentée.

**Cause réelle identifiée** : les iPhones utilisant Safari capturent par
défaut leurs photos en **HEIC** — un format d'image parfaitement valide,
mais que l'application Photos de Windows ne peut pas ouvrir sans un
codec supplémentaire (non installé par défaut), d'où le message
"Nous ne pouvons pas ouvrir ce fichier" que l'utilisateur interprète
comme une corruption. Les captures caméra Android sont presque toujours
déjà en JPEG, donc ce problème concerne principalement les envois
iPhone → PC.

### 20.2 Correctifs appliqués

1. **Frontend (`static/js/app.js`)** — nouvelle fonction
   `normalizeImageForUpload()` : si le fichier sélectionné/déposé est
   HEIC/HEIF (ou un type d'image non standard), il est redessiné sur un
   `<canvas>` et ré-exporté en JPEG standard avant l'envoi. Les fichiers
   non-image (docx, pdf, xlsx...) et les images déjà dans un format
   standard (JPEG, PNG, WEBP, GIF) traversent sans aucune modification.
   Si le navigateur lui-même ne peut pas décoder la source (certains
   navigateurs non-Safari ne décodent pas non plus le HEIC), le fichier
   original est envoyé tel quel plutôt que de perdre la pièce jointe.
2. **Backend (`app.py`)** — nouvelle fonction `sniff_real_extension()` :
   vérifie les octets réels du fichier (signature magique : JPEG, PNG,
   GIF, WEBP, HEIC) et corrige l'extension du nom de fichier archivé/
   affiché si elle ne correspond pas au contenu réel. Ce n'est PAS un
   convertisseur de format (le serveur ne décode aucune image) — c'est un
   filet de sécurité qui empêche un fichier mal étiqueté de porter un nom
   qui ment sur son vrai format. Un envoi vide (0 octet) est désormais
   rejeté explicitement au lieu d'être archivé silencieusement.

### 20.3 Tests réels effectués

- Un vrai JPEG correctement étiqueté → traverse sans changement.
- Un fichier HEIC (signature `ftypheic` réelle) mais étiqueté `.jpg` par
  le client → nom corrigé en `.heic` avant archivage.
- Un envoi de 0 octet → rejeté avec `400` et message clair, au lieu
  d'être archivé silencieusement.
- Un `.docx` → nom de fichier inchangé, octets identiques bit à bit
  après le cycle chiffrement/déchiffrement complet (aucune régression
  introduite sur les fichiers non-image).
- Syntaxe JS vérifiée (`node --check`), syntaxe Python vérifiée
  (`py_compile`).

**Fichiers modifiés :** `app.py`, `static/js/app.js`. Aucune
fonctionnalité antérieure retirée (SQLite WAL/Context Managers de la
v2.8.1 et correctifs tracking_number/CSS de la v2.8.2 confirmés
intacts par re-vérification directe du code après ce changement).

---

## 21. v2.8.4 — Lisibilité des cartes de messages + System Tray Windows (2026-09-17)

### 21.1 🎨 Refonte des cartes (Tableau de Bord, Boîte de réception, Registre)

**Problème signalé** : le `tracking_number` (long, ex.
`TASHIL-31EP-S-2026-000001-BD6C08`) s'affichait comme titre principal des
cartes ; l'Objet et un aperçu du message n'étaient pas visibles
directement.

**Correctif** (frontend uniquement, `static/js/app.js` +
`static/css/style.css`) :
- **Titre** : l'Objet du message (`"Sans objet"` si vide).
- **Sous-titre** : établissement expéditeur/destinataire + extrait —
  le corps du message tronqué à 60 caractères, ou à défaut le nom du
  fichier joint (`📎 nom_fichier`) si le corps est vide, ou `—` si aucun
  des deux.
- **Badge secondaire discret** : le `tracking_number` conservé, mais en
  petit texte monospace atténué (`.tracking-badge`), sous le sous-titre.

**Testé réellement** : logique de rendu exécutée directement en Node.js
avec des données réalistes (objet vide + pièce jointe ; objet renseigné
+ corps long à tronquer) — sortie HTML inspectée, troncature à 60
caractères confirmée, échappement HTML toujours actif. Syntaxe JS
(`node --check`) et CSS (`tinycss2`) validées sans erreur.

Aucun changement backend/API pour cette partie.

### 21.2 🔔 Suivi des messages non lus (backend)

Nouvelle colonne `is_read` sur la table `messages` (migration idempotente
`ALTER TABLE`, valeur par défaut `1` = lu — donc toute ligne existante
avant cette version reste inchangée ; seuls les nouveaux messages
`entrant` insérés à partir de maintenant reçoivent explicitement
`is_read=0`).

- `GET /api/messages?direction=entrant` marque désormais automatiquement
  tous les messages entrants non lus comme lus (effet de bord de la
  consultation de la boîte de réception), via une connexion courte
  séparée, ouverte après la lecture — même principe d'isolation des
  écritures que depuis la v2.8.1.
- Nouvelle route `GET /api/messages/unread-count` — retourne le nombre
  de messages entrants non lus pour le profil actif. Aucune logique
  spécifique à un OS ici ; c'est un simple compteur interrogeable par
  n'importe quel client.

**Testé réellement, cycle complet** via le client de test Flask : envoi
d'un message avec livraison locale → `unread: 1` côté destinataire avant
consultation → consultation de la boîte de réception → `unread: 0` →
comportement `423` propre (pas de crash) quand le profil est verrouillé.

### 21.3 🖥️ System Tray Windows — minimisation, badge, notifications (nouveau module `tray.py`)

**Objectif** : garder l'application active dans la zone de notification
Windows (à côté de l'horloge) à la fermeture de la fenêtre, avec un badge
rouge du nombre de non-lus directement dessiné sur l'icône du tray, et
une notification Windows native (toast) à la réception d'un nouveau
message.

**Conception** : nouveau module isolé `tray.py`, entièrement optionnel —
`pystray` (icône + menu Afficher/Quitter) et `plyer` (notification toast
cross-plateforme) sont importés avec `try/except`, exactement le même
schéma défensif déjà utilisé pour `qrcode`, `cryptography`, `certifi` et
`pyzbar` dans ce projet. Si l'un des deux manque, ou si n'importe quelle
partie de `tray.py` lève une exception, l'application entière continue
de fonctionner exactement comme en v2.8.3 : la fenêtre s'ouvre, et la
fermer quitte normalement l'application (aucune régression possible sur
la stabilité existante).

`desktop_launcher.py` n'attache le gestionnaire "minimiser au lieu de
fermer" QUE si le tray a réellement démarré avec succès
(`tray_controller.available`) — sinon, aucun changement de comportement
par rapport à v2.8.3.

**⚠️ Note d'honnêteté impérative, à lire avant de considérer cette partie
comme validée** : ce bac à sable de développement est un Linux headless,
sans serveur d'affichage ni GTK — `pystray` lui-même échoue à l'import
ici (`ValueError: Namespace Gtk not available`), ce qui est **spécifique
à cet environnement de test**, pas au build Windows réel (qui utilise le
backend natif `win32` de pystray, sans dépendance GTK). Cet échec a
cependant permis de vérifier une chose utile : la dégradation gracieuse
fonctionne bel et bien — `TrayController.available` passe à `False`
et `run()`/`stop()` restent des no-op sûrs, sans jamais lever
d'exception, testé explicitement.

Ce qui a donc pu être vérifié réellement dans ce bac à sable :
- ✅ La composition de l'image du badge (`draw_badge`, via Pillow pur,
  indépendamment de `pystray`) — rendue et inspectée visuellement à
  plusieurs tailles, y compris un downscale réel à 24×24px (taille
  typique d'une icône de tray Windows). **Premier essai illisible** à
  cette taille avec la police par défaut de Pillow → corrigé en utilisant
  `ImageFont.load_default(size=...)` dimensionnée par rapport au badge —
  lisible ensuite à 48px, tout juste discernable à 24px (limite physique
  inhérente à la taille d'une icône de tray, pas un défaut du code).
- ✅ `desktop_launcher._setup_tray()` et `TrayController` se dégradent
  bien sans jamais planter quand `pystray`/`plyer` sont indisponibles
  (testé avec une fausse fenêtre simulée).
- ✅ Le compteur `/api/messages/unread-count` interrogé par le thread de
  sondage du tray (voir section 21.2).

Ce qui n'a **pas** pu être vérifié ici et reste à confirmer sur un vrai
build Windows, comme cela a déjà été le cas pour pywebview/pyzbar/certifi
dans l'historique de ce projet :
- L'icône apparaît-elle réellement dans la zone de notification à côté
  de l'horloge ?
- Cliquer dessus restaure-t-il réellement la fenêtre ?
- La notification toast s'affiche-t-elle réellement (le backend Windows
  de `plyer` a ses propres dépendances, qui pourraient échouer à
  l'empaquetage PyInstaller de la même façon qu'`opencv-python-headless`
  ou `pywebview` l'ont fait par le passé dans ce projet) ?
- Le rendu réel de l'icône par Windows (anti-aliasing, densité de
  pixels) à la taille de tray effective.

**Fichiers ajoutés :** `tray.py`. **Fichiers modifiés :**
`desktop_launcher.py` (intégration tray optionnelle), `app.py` (colonne
`is_read`, routes de suivi des non-lus), `static/js/app.js`,
`static/css/style.css` (refonte des cartes), `requirements.txt` (+
`pystray`, `plyer`), `tashil_web.spec` (+ `collect_all` pour ces deux
nouvelles dépendances + `tray.py` ajouté aux données empaquetées).
Aucune fonctionnalité antérieure retirée — SQLite WAL/Context Managers
(v2.8.1), correctif `tracking_number` (v2.8.2), CSS desktop (v2.8.2),
et normalisation HEIC/JPEG (v2.8.3) tous reconfirmés intacts.

**Recommandation avant mise en production** : tester impérativement le
system tray sur un vrai poste Windows avant de considérer cette partie
aussi stable que le reste — contrairement aux corrections précédentes de
ce fichier, celle-ci touche à des API natives Windows qui n'ont jamais pu
être exercées dans l'environnement de développement.

---

## 22. v2.8.5 — Couverture DSP nationale, hiérarchie des rôles, appairage matériel, récupération (2026-09-19)

### 22.1 ⚠️ Demande refusée puis remplacée — clé Master Admin universelle

Le cahier des charges initial demandait une **clé Master Admin unique et
universelle** (`ADMIN-ILINE-2024`, codée en dur, modifiable via config)
capable de débloquer *n'importe quel poste* du réseau national.

**Cette demande a été refusée telle quelle**, pour exactement la même
raison déjà documentée en v2.5.0 (section 13.1) à propos du token GitHub
du Cloud Bridge — avec un rayon d'impact plus grave ici :
- Une clé unique codée en dur se retrouve identique dans **chaque**
  exécutable distribué sur des centaines de postes.
- `strings TASHIL.exe | grep ADMIN` l'extrait en quelques secondes.
- Un seul poste compromis donnerait accès à **tous les autres**
  (courriers de direction, dossiers RH, dossiers sociaux), sans
  révocation individuelle possible.

**Alternative validée par l'utilisateur** : récupération via le
`serial_key` **propre à chaque institution** (déjà existant dans le
projet), jamais un secret partagé. Voir section 22.5.

### 22.2 🌐 Couverture nationale des DSP (58 wilayas)

`INSTITUTION_TYPES` inclut désormais `"DSP"`. Chaque wilaya reçoit
automatiquement sa DSP (`f"DSP {wilaya_name}"`) dans le répertoire
national ET dans le tirage d'onboarding, en réutilisant directement la
table `WILAYAS` déjà présente — aucune saisie manuelle, aucune donnée
supplémentaire à maintenir.

**Testé réellement** : `GET /api/institutions/onboarding?wilaya_code=1&institution_type=DSP`
→ `DSP Adrar` ; même requête avec `wilaya_code=58` → `DSP El Meniaa`.
Les 58 wilayas confirmées couvertes.

### 22.3 🏛️ Hiérarchie des rôles (DIRECTEUR / DRH / DAS / SECRETARIAT)

Nouvelle table de règles `ROLE_RULES` :
```python
ROLE_RULES = {
    "DSP":  ["DIRECTEUR", "SECRETARIAT"],
    "EPSP": ["DIRECTEUR", "DRH", "DAS", "SECRETARIAT"],
}
```
Tout autre type (EPH, CHU, EHU, Polyclinique) → `SECRETARIAT` uniquement,
par construction (`allowed_roles()` retourne `["SECRETARIAT"]` par
défaut pour tout type absent de `ROLE_RULES`).

**Appliqué côté SERVEUR, pas seulement en façade** : `api_save_profile`
recalcule `allowed_roles(institution_type)` et **corrige silencieusement**
tout rôle invalide vers la seule option autorisée — un client trafiqué ou
buggé ne peut pas créer un `DIRECTEUR` pour une Polyclinique. Nouvelle
route `GET /api/roles?institution_type=X` pour que le frontend
interroge la même source de vérité plutôt que de dupliquer la règle en
JavaScript.

Chaque combinaison (établissement, rôle) devient un profil et une boîte
isolée à part entière — `make_institution_key()` et `generate_serial_key()`
incorporent désormais le rôle. Le DRH et le DIRECTEUR du même EPSP ont
deux `institution_key` et deux `serial_key` totalement distincts.

**Testé réellement** :
- Création EPSP × DRH puis EPSP × DIRECTEUR (même établissement) →
  `institution_key` confirmés différents (`..._DRH` vs `..._DIRECTEUR`).
- Tentative de créer un `DIRECTEUR` pour une Polyclinique → rôle stocké
  confirmé forcé à `SECRETARIAT`.
- `GET /api/roles` vérifié pour DSP, EPSP et Polyclinique — `locked: true`
  correctement renvoyé quand une seule option existe.

### 22.4 🔐 Secret HMAC déplacé hors du code source public

**Problème réel découvert en concevant cette version** (pas signalé par
l'utilisateur, trouvé en auditant `generate_serial_key`) : le secret HMAC
utilisé pour générer les `serial_key` était codé en dur dans `app.py` —
qui est sur un dépôt GitHub **public**. N'importe qui lisant le code
source pouvait déjà recalculer le `serial_key` de n'importe quelle
institution, puisque `WILAYAS` et les conventions de nommage sont
également dans ce même fichier public.

**Correctif** : le secret est désormais lu depuis la variable
d'environnement `TASHIL_HMAC_SECRET`, avec repli sur l'ancienne valeur
codée en dur **uniquement** pour qu'une installation fraîche continue de
fonctionner avant toute configuration — ce repli n'offre aucune sécurité
réelle et doit être remplacé par un vrai secret privé en production.

**`generate_serial_key` rendu déterministe** (l'ancienne version mélangeait
la date du jour dans le calcul — cohérent pour une génération unique au
moment de l'onboarding réel, mais incompatible avec la pré-génération
d'un registre national à l'avance). La vérification ne recalcule jamais
la clé — elle compare la valeur soumise à la colonne `profiles.serial_key`
stockée — donc faire tourner `TASHIL_HMAC_SECRET` reste toujours sans
risque pour les clés déjà émises.

**Testé réellement** : le registre central généré à l'instant T et un
recalcul simulé "plus tard" (avec une pause explicite) produisent
**exactement** la même clé série pour la même institution+rôle, avec le
même secret. Confirmé octet pour octet.

### 22.5 🔒 Appairage matériel automatique + 🐛 bug réel trouvé et corrigé pendant les tests

`get_hardware_fingerprint()` : UUID matériel via `wmic csproduct get UUID`
sur Windows, repli sur une valeur dérivée de l'adresse MAC
(`uuid.getnode()`) sur toute autre plateforme — y compris ce bac à sable
Linux, où seul le repli a pu être exercé. Le brut n'est jamais stocké,
seul son hash SHA-256 l'est (`paired_hardware_hash`), même principe que
pour les PIN.

Au premier déverrouillage réussi d'un profil, l'empreinte de la machine
est enregistrée automatiquement. Toute tentative ultérieure depuis une
machine différente est bloquée avec `HTTP 403` **avant même** la
vérification du PIN.

**🐛 Bug réel trouvé et corrigé avant livraison** : lors de la première
implémentation, le décorateur `@app.route("/api/session/unlock", ...)`
s'est retrouvé accroché par erreur à la fonction `get_hardware_fingerprint()`
plutôt qu'à `api_session_unlock()` (effet de bord d'une édition de code
mal positionnée). Conséquence : Flask acheminait bien les requêtes vers
la vraie fonction de déverrouillage, MAIS la logique d'appairage,
elle-même définie plus bas dans le fichier sans décorateur, n'était
**jamais exécutée** — `paired_hardware_hash` restait `NULL` indéfiniment,
rendant le blocage matériel totalement inopérant sans qu'aucune erreur
ne soit visible (les déverrouillages continuaient de réussir
normalement). **Trouvé uniquement parce que le test de simulation d'une
« autre machine » attendait un `403` et recevait un `200`** — sans ce
test spécifique, ce bug serait passé inaperçu jusqu'en production.
Corrigé en replaçant le décorateur directement au-dessus de la bonne
fonction.

**Tests réels effectués, cycle complet (7 scénarios)**, TOUS reproduits
après correction :
1. Premier déverrouillage réel → `paired_hardware_hash` confirmé défini.
2. Re-déverrouillage même machine → `200`.
3. Déverrouillage depuis une empreinte différente → `403`,
   `hardware_mismatch: true`.
4. Récupération avec un `serial_key` invalide → `401`.
5. Récupération avec le bon `serial_key` → `200`, PIN réinitialisé,
   avertissement de chiffrement renvoyé.
6. Nouveau PIN fonctionne sur la machine venant d'être ré-appairée.
7. L'ancienne machine (empreinte d'origine) est désormais bloquée.

### 22.6 🔑 Récupération via `serial_key` (pas de clé partagée)

Nouvelle route `POST /api/session/recover` : vérifie le `serial_key`
**propre à l'institution** (comparaison à temps constant,
`hmac.compare_digest`) contre la valeur stockée dans `registry.db`,
réinitialise le PIN et ré-appaire automatiquement la machine courante —
couvrant à la fois "PIN oublié sur la même machine" et "remplacement de
machine légitime" en un seul flux.

**⚠️ Compromis honnête, affiché à l'utilisateur, pas caché** : changer le
PIN change la clé Fernet dérivée (`derive_fernet`) — tout document déjà
chiffré avec l'ancien PIN devient **définitivement illisible**. Ce n'est
pas un bug introduit par cette fonctionnalité : c'est ce qu'implique un
vrai chiffrement, déjà documenté depuis la v2.7.0. Un mécanisme de
récupération qui contournerait ce fait ne serait pas un vrai chiffrement.
Le message d'avertissement est renvoyé par l'API et affiché explicitement
côté frontend avant l'entrée dans l'application.

### 22.7 ⚙️ Adressage à deux niveaux (Établissement → Service)

Le formulaire d'envoi comporte désormais un champ **Service destinataire**
(`SECRETARIAT` par défaut, `DIRECTEUR`/`DRH`/`DAS` sélectionnables). Côté
serveur, `find_local_profile_by_recipient()` et `bridge_slug()` ont été
étendus pour désambiguïser par rôle — une même institution peut
désormais avoir plusieurs profils (un par rôle), et un courrier adressé
sans préciser de service est automatiquement orienté vers le
`SECRETARIAT`.

**Rétrocompatibilité de l'adressage Cloud Bridge préservée** :
`bridge_slug()` n'ajoute un suffixe de rôle que pour les rôles autres que
`SECRETARIAT` — toute adresse déjà en usage pour une institution
SECRETARIAT-only (100 % des institutions avant cette version) reste
identique, octet pour octet.

**Testé réellement, isolation complète confirmée** : création de 3
profils pour le même `EPSP ES SENIA` (DRH, DAS, SECRETARIAT) → 3 envois
adressés respectivement à chaque service (+ 1 envoi sans service précisé)
→ vérification de la boîte de réception de chacun des 3 profils : chaque
boîte ne contient **que** le message qui lui était destiné, aucune fuite
croisée.

### 22.8 📄 Registre national des `serial_key` (`tools/generate_serial_registry.py`)

Nouveau script autonome, **volontairement absent de `tashil_web.spec`**
(jamais empaqueté dans l'exécutable distribué, jamais destiné aux postes
de terrain) — à exécuter une seule fois, en central, par ILINE TECH.

Génère 348 entrées (58 wilayas × (2 rôles DSP + 4 rôles EPSP)) en
réutilisant **exactement** `WILAYAS`, `allowed_roles()` et
`generate_serial_key()` de `app.py`, garantissant que le registre central
correspond mot pour mot à ce que produira l'onboarding réel sur le poste
de chaque institution, du moment que le même `TASHIL_HMAC_SECRET` est
configuré des deux côtés.

Sortie : un fichier Markdown et un fichier Excel (bannière de sécurité
rouge en première ligne, colonnes Wilaya / Type / Établissement / Rôle /
Clé série). ⚠️ Seul l'EPSP d'Oran a une liste réelle nommée
(`_ONBOARDING_KNOWN`) ; toutes les autres wilayas utilisent le nom
générique `EPSP <Wilaya>` — la même convention déjà utilisée par
l'application elle-même. Si l'EPSP réel d'une wilaya est onboardé sous un
nom différent, sa vraie clé série divergera de cette entrée générique et
devra être relevée sur son propre écran Paramètres.

**⚠️ Avertissement de sécurité intégré au script et rappelé dans son
en-tête** : ce fichier exporté est, en cumulé, une liste de clés de
réinitialisation pour tout le réseau national — jamais à commiter sur le
dépôt Git public, jamais à partager sans contrôle d'accès.

**Testé réellement** :
- Exécution réelle → 348 entrées générées, fichiers `.md` et `.xlsx`
  physiquement présents et inspectés (structure du classeur Excel
  vérifiée ligne par ligne : bannière, en-têtes, première et dernière
  ligne de données).
- **Déterminisme confirmé** : deux exécutions successives avec le même
  `TASHIL_HMAC_SECRET` → fichiers Markdown identiques (`diff` sans sortie).
- **Cohérence centrale/terrain confirmée** : la clé calculée par le
  script d'export et celle qu'un onboarding réel calculerait "plus tard"
  (simulé avec une pause explicite) sont identiques.
- Avertissement affiché correctement quand `TASHIL_HMAC_SECRET` n'est pas
  défini.

### 22.9 ⚠️ Limite connue, documentée et non résolue — routage des accusés de réception

Le routage d'un accusé de réception (local et Cloud Bridge) ne connaît
que le **nom** de l'institution émettrice (`messages.sender_institution`),
jamais son rôle précis. Pour une institution multi-rôles (EPSP avec
DIRECTEUR/DRH/DAS/SECRETARIAT), un accusé pourrait ne pas revenir
exactement au bon service si plusieurs profils partagent ce nom.

**Non corrigé dans cette version** — la correction complète nécessiterait
d'ajouter une colonne `sender_institution_key` (ou `sender_role`) à la
table `messages` et de la propager dans l'INSERT, les métadonnées Cloud
Bridge, et la logique de `route_read_receipt()`. Périmètre jugé trop
large pour cette livraison ; à traiter en v2.8.6. Documenté ici
explicitement plutôt que laissé silencieux.

### 22.10 Régression complète (v2.8.1 → v2.8.5)

Suite exécutée sur l'arborescence finale, TOUT confirmé fonctionnel
ensemble sans collision :
- ✅ Mode WAL + `PRAGMA busy_timeout=5000` (v2.8.1)
- ✅ `tracking_number` : scénario exact de collision reproduit puis
  confirmé résolu (v2.8.2)
- ✅ Correctif CSS desktop topbar (v2.8.2)
- ✅ Normalisation HEIC → extension corrigée, upload vide rejeté (v2.8.3)
- ✅ Suivi des messages non lus, cycle complet (v2.8.4)
- ✅ Hiérarchie des rôles appliquée côté serveur, DSP × 58 wilayas,
  appairage matériel (7 scénarios), récupération via `serial_key`,
  isolation complète de l'adressage à deux niveaux (v2.8.5)

**Fichiers ajoutés :** `tools/generate_serial_registry.py`. **Fichiers
modifiés :** `app.py` (DSP, rôles, `institution_key`/`serial_key` avec
rôle, secret HMAC en variable d'environnement, appairage matériel,
récupération, adressage à deux niveaux), `templates/index.html`
(sélecteur de rôle onboarding, champ Service destinataire, écran de
récupération), `static/js/app.js` (câblage complet des trois flux),
`static/css/style.css` (`.btn-link`). Aucune fonctionnalité antérieure
retirée — WAL/Context Managers (v2.8.1), `tracking_number` (v2.8.2),
CSS desktop (v2.8.2), HEIC/JPEG (v2.8.3), suivi des non-lus et System
Tray (v2.8.4) tous reconfirmés intacts par la suite de régression
complète ci-dessus.

**Recommandation avant déploiement national** : configurer un vrai
`TASHIL_HMAC_SECRET` (jamais la valeur par défaut) avant de lancer le
script d'export en production, et traiter la limite de la section 22.9
avant de compter sur les accusés de réception pour des institutions
multi-rôles.

---

## 23. v2.8.5.1 — Correctif registre : EPH/CHU/Polyclinique manquants (2026-09-20)

**Signalé en production** : un poste onboardé sous
`POLYCLINIQUE AADL AIN BEIDA MABROUK LOUCIF` (SECRETARIAT) n'avait
aucune entrée dans le registre national — bloqué sans clé de
récupération possible.

**Cause réelle** : `tools/generate_serial_registry.py` (v2.8.5) ne
couvrait que DSP et EPSP, exactement le périmètre demandé à l'origine —
mais Polyclinique, EPH et CHU sont des types d'établissement réels et
onboardables (`INSTITUTION_TYPES`), tout aussi susceptibles d'un PIN
oublié.

**Correctif** : le script couvre maintenant l'intégralité des types —
DSP, EPSP, EPH, CHU (wilayas concernées uniquement), Polyclinique
générique par wilaya, **et les 7 vraies polycliniques d'Oran nommément**
(`_REAL_ESSENIA_POLYCLINICS`), puisque ce sont celles réellement
onboardées en pratique. 348 → **482 entrées**, vérifié par calcul exact
(58×2 + 58×4 + 58×1 + 11×1 + 58×1 + 7×1 = 482).

**Testé réellement** : registre régénéré, entrée
`POLYCLINIQUE AADL AIN BEIDA MABROUK LOUCIF — SECRETARIAT` confirmée
présente avec sa clé série.

⚠️ **Rappel non résolu par ce correctif** : la clé générée n'est valable
que si `TASHIL_HMAC_SECRET` était identique au moment de l'onboarding
réel de ce poste et au moment de l'export. Si le poste a été onboardé
après configuration d'un secret personnalisé, il faut relancer l'export
avec ce même secret.

**Fichiers modifiés :** `tools/generate_serial_registry.py` uniquement.
Aucun changement à `app.py` — ce correctif touche seulement l'outil
d'export, pas l'application elle-même.

---

## 24. v2.8.6 — Polyclinique rattachée à l'EPSP, Secrétariats distincts, correctifs UI (2026-09-20)

### 24.1 ⚠️ Clarification demandée, pas appliquée telle quelle

Le cahier des charges demandait d'"harmoniser" le calcul de
`institution_key` entre `app.py` et `generate_serial_registry.py` pour
que le registre débloque les postes sans erreur. Vérification faite :
**aucune divergence n'existe** — le script appelle littéralement
`tashil_app.generate_serial_key(...)`, la même fonction, importée
directement depuis `app.py`. La confusion venait d'un raccourci de
vocabulaire (`institution_key`, qui sert à l'isolement des bases par
rôle, n'est pas le `serial_key` utilisé pour la récupération).

Le vrai échec de récupération signalé par l'utilisateur venait d'un
poste onboardé **avant** la v2.8.5 (quand `generate_serial_key` mélangeait
encore la date du jour dans le calcul) — aucune formule actuelle ne peut
reconstruire une valeur calculée avec une date désormais inconnue. Rien
n'a été changé dans `institution_key` : retirer le rôle de sa formule
aurait cassé l'isolement DRH/DAS/DIRECTEUR introduit en v2.8.5.

### 24.2 🏥 Polyclinique n'est plus un type d'établissement

`INSTITUTION_TYPES` = `["DSP", "EPSP", "EPH", "CHU", "EHU"]` — une
polyclinique est désormais un **nom** choisi dans "Nom de l'établissement"
sous le type `EPSP`, "sous la tutelle de son EPSP". `_TYPE_CODES` garde
`"Polyclinique": "PC"` pour que les clés déjà émises avant cette version
restent décodables, mais `api_save_profile` bloque toute nouvelle
création avec ce type (`400`).

`get_onboarding_institutions("EPSP", ...)` retourne désormais le siège
EPSP **et** ses polycliniques rattachées dans la même liste (ex. pour
Oran : `["EPSP Oran", "POLYCLINIQUE ES SENIA", ...]`) — avant cette
version, il n'existait même aucun moyen d'onboarder le siège EPSP d'Oran
lui-même (seules les 7 polycliniques étaient proposées).

### 24.3 🏛️ Deux secrétariats distincts, plus de `SECRETARIAT` générique

`SECRETARIAT_DIRECTION` (siège EPSP/DSP, EPH, CHU, EHU) et
`SECRETARIAT_POLYCLINIQUE` (toute institution dont le **nom** commence
par "POLYCLINIQUE", détecté via `_is_polyclinique_name()` — fonctionne
pour toute polyclinique actuelle ou future sans modification de code).

`allowed_roles(institution_type, institution_name)` prend maintenant le
nom en compte : `allowed_roles("EPSP", "EPSP Oran")` → 4 rôles direction ;
`allowed_roles("EPSP", "POLYCLINIQUE ES SENIA")` → verrouillé sur
`SECRETARIAT_POLYCLINIQUE` uniquement. Appliqué côté serveur dans
`api_save_profile` — un client trafiqué ne peut pas créer un `DIRECTEUR`
pour une polyclinique nommée.

**Migration des données existantes, avec un vrai bug trouvé et corrigé
avant livraison** : la première version de la migration utilisait
`ALTER TABLE profiles ADD COLUMN role TEXT DEFAULT 'SECRETARIAT_DIRECTION'`
— sur une base **pré-v2.8.5** (sans colonne `role` du tout), cela
assignait directement la nouvelle valeur par défaut à toutes les lignes,
y compris les anciennes Polycliniques, qui ne passaient donc jamais par
l'ancienne valeur littérale `'SECRETARIAT'` que la requête de
reclassification cherchait — une ancienne Polyclinique restait donc
incorrectement classée `SECRETARIAT_DIRECTION`. **Trouvé en testant
explicitement ce scénario précis** (simulation d'une base pré-v2.8.5).
Corrigé : la colonne est ajoutée sans valeur par défaut (`NULL`), puis
une classification explicite tourne à chaque démarrage
(`WHERE role IS NULL OR role = 'SECRETARIAT'`), couvrant à la fois le cas
pré-v2.8.5 (`NULL` après l'ALTER) et le cas v2.8.5-seul (valeur littérale
`'SECRETARIAT'` déjà stockée). **Testé réellement sur les deux
scénarios** : ancienne Polyclinique → `SECRETARIAT_POLYCLINIQUE` ; ancien
EPH → `SECRETARIAT_DIRECTION` ; ligne v2.8.5 avec `'SECRETARIAT'` déjà
stocké littéralement → `SECRETARIAT_POLYCLINIQUE` si Polyclinique.

### 24.4 🐛 Doublons dans le menu Service/Rôle — cause réelle trouvée

**Cause** : `showOnboarding()` s'exécute à chaque ouverture de l'écran
d'onboarding (premier lancement ET "Ajouter un nouvel établissement"
depuis l'écran de verrouillage), mais les `<select>` eux-mêmes ne sont
jamais recréés — seules leurs options le sont. `wilayaSelect.
addEventListener("change", ...)` et `typeSelect.addEventListener(...)`
**empilaient** un nouvel écouteur à chaque appel au lieu de remplacer
l'ancien. Après N ouvertures de l'onboarding, un seul changement
déclenchait N rafraîchissements asynchrones qui se chevauchaient, chacun
ajoutant sa propre copie de la liste avant que le `.innerHTML = ""` d'un
autre appel n'ait eu le temps de nettoyer — exactement le symptôme
"DIRECTEUR, DRH, DAS, SECRETARIAT répétés à la chaîne" signalé.

**Correctif** : `addEventListener` remplacé par une assignation directe
(`.onchange = fn`), qui remplace un gestionnaire précédent au lieu de
s'empiler dessus, quel que soit le nombre de fois où `showOnboarding()`
est appelée. Le vidage du menu (`innerHTML = ""`) déjà présent depuis la
v2.8.5 reste en place — la vraie cause était l'empilement des
écouteurs, pas l'absence de vidage.

Le rafraîchissement des rôles est maintenant aussi déclenché par un
changement de **nom** (pas seulement de type), puisque le rôle disponible
dépend désormais du nom choisi (siège EPSP vs. polyclinique nommée) —
chaîné après le rafraîchissement des noms (`await refreshOnboardingInstitutions()`
puis `refreshOnboardingRoles()`) pour éviter une course où le rôle serait
calculé sur un nom pas encore à jour.

### 24.5 ⚙️ Adressage assoupli pour les institutions à rôle unique

`find_local_profile_by_recipient()` : le repli "un seul profil sous ce
nom → le livrer, même si le rôle précisé ne correspond pas exactement"
s'applique désormais **que le service ait été précisé ou non** (avant :
uniquement si omis). Nécessaire car le formulaire d'envoi soumet
toujours une valeur de service (jamais `null`) — sans cet assouplissement,
une polyclinique (qui n'a qu'un seul rôle possible) devenait injoignable
dès que l'expéditeur laissait le service par défaut sur
`SECRETARIAT_DIRECTION`. Aucune ambiguïté introduite pour les
institutions multi-rôles (un siège EPSP), puisque `len(name_matches)`
n'est égal à 1 que lorsqu'il n'existe réellement qu'un seul profil à
livrer.

### 24.6 📄 Registre régénéré (structure mise à jour)

`tools/generate_serial_registry.py` : les polycliniques réelles d'Oran
sont désormais générées avec `institution_type="EPSP"` et
`role="SECRETARIAT_POLYCLINIQUE"` — leur code de clé change en
conséquence (`TSH-31-EP-...` au lieu de l'ancien `TSH-31-PC-...`). Toute
clé notée avant cette version pour une polyclinique ne correspondra plus
et doit être régénérée après ré-onboarding sous le nouveau système.
424 entrées au total (58 wilayas × DSP(2) + EPSP siège(4) + EPH(1) +
CHU(1, wilayas concernées) + 7 polycliniques d'Oran(1 rôle chacune)).

### 24.7 Régression complète (v2.8.1 → v2.8.6)

Suite exécutée sur l'arborescence finale — WAL, `tracking_number`, HEIC,
suivi des non-lus, appairage matériel + récupération (v2.8.5), retrait de
Polyclinique, verrouillage serveur du rôle, et adressage vers une
polyclinique malgré un service par défaut incorrect : **tout confirmé
fonctionnel ensemble**, aucune régression.

**Fichiers modifiés :** `app.py` (types, rôles, migration, adressage),
`templates/index.html` (options du sélecteur de service),
`static/js/app.js` (correctif des écouteurs empilés, rafraîchissement des
rôles par nom), `tools/generate_serial_registry.py` (structure
polyclinique sous EPSP). Aucune fonctionnalité antérieure retirée.

---

## 25. v2.8.7 — Vraie hiérarchie multi-EPSP, rôles élargis EPH/CHU/EHU, correctif du bug "En attente" (2026-09-20)

### 25.1 🏥 Structure réelle : plusieurs EPSP distincts par wilaya

**Problème signalé** : un seul "EPSP Oran" générique regroupait toutes
les polycliniques, alors qu'une wilaya contient plusieurs EPSP réels et
distincts (EPSP ES SENIA, EPSP SEDDIKIA, EPSP ARZEW, EPSP BOUTLELIS pour
Oran), chacun avec son propre siège et ses propres polycliniques
rattachées.

⚠️ **Rattachement partiellement inconnu, non deviné** : lors d'un
premier échange, seul le rattachement EPSP ES SENIA ↔ POLYCLINIQUE ES
SENIA était confirmé par l'exemple donné ; les 6 autres polycliniques
déjà en base n'avaient pas de parent confirmé. Plutôt que d'inventer une
hiérarchie administrative réelle (risque concret d'égarer du courrier
médical/administratif), la répartition complète a été explicitement
redemandée et fournie par l'utilisateur avant implémentation.

**Structure implémentée** (`_EPSP_HIERARCHY` dans `app.py`, remplace
l'ancien `_REAL_ESSENIA_POLYCLINICS` plat) :
- **EPSP ES SENIA** — Siège + 7 polycliniques (ES SENIA, AADL AIN BEIDA
  MABROUK LOUCIF, AIN BEIDA 1, AIN BEIDA 2, SIDI MAAROUF, SIDI CHAHMI,
  EL KERMA) + Salle de Soin Terminus.
- **EPSP SEDDIKIA** (Front de Mer) — Siège + 3 polycliniques (AKID
  LOTFI, SEDDIKIA, GAMBETTA).
- **EPSP ARZEW** — Siège + 3 polycliniques (ARZEW, BETHIOUA, GDYEL).
- **EPSP BOUTLELIS** — Siège + 2 polycliniques (MISSERGHIN, BOUTLELIS).

`get_onboarding_institutions("EPSP", ...)` retourne chaque siège suivi
immédiatement de ses propres structures rattachées ; le frontend affiche
le siège avec le libellé "- SIÈGE" (affichage uniquement, le
`institution_name` stocké reste le nom propre, sans suffixe).

Une nouvelle fonction `_is_satellite_structure_name()` généralise
l'ancienne `_is_polyclinique_name()` pour reconnaître aussi les "SALLE
DE SOIN" en plus des "POLYCLINIQUE" — même rôle unique
`SECRETARIAT_POLYCLINIQUE` pour les deux, aucun rôle supplémentaire
inventé.

Toute wilaya sans hiérarchie confirmée retombe sur le comportement
précédent (siège générique "EPSP <Wilaya>" seul) — aucune régression
pour les 57 autres wilayas.

### 25.2 🏛️ Rôles élargis pour EPH, CHU, EHU

Ces trois types disposent désormais des mêmes 4 services précis qu'un
siège EPSP : `DRH`, `DAS`, `SECRETARIAT_DIRECTION`, et un nouveau rôle
`SECRETARIAT_GENERAL` (distinct du secrétariat de direction). Avant
cette version, ces structures n'avaient qu'un rôle générique unique.
Aucune migration de données nécessaire : les profils déjà onboardés
gardent leur rôle existant (`SECRETARIAT_DIRECTION` par défaut suite à
la migration v2.8.6) ; seul le choix disponible à l'onboarding change
pour les nouveaux profils.

### 25.3 🐛 Bug réel corrigé : compteur "En attente" bloqué après accusé

**Cause exacte confirmée** (limite déjà documentée en v2.8.5 §22.9,
restée non résolue jusqu'ici) : `route_read_receipt()` ne connaissait que
le **nom** de l'institution émettrice, jamais son rôle précis. Dès qu'un
expéditeur avait un rôle différent du défaut (`SECRETARIAT_DIRECTION`)
ou que plusieurs profils partageaient ce nom (ex. un siège EPSP avec
DIRECTEUR/DRH/DAS/SECRETARIAT_DIRECTION), le matching par nom échouait
silencieusement — l'accusé n'était jamais appliqué côté expéditeur, et
"En attente" restait bloqué indéfiniment.

**Correctif** : nouvelle colonne `sender_institution_key` sur la table
`messages` (migration idempotente, `NULL` pour les messages antérieurs)
— chaque message livré (localement ou via Cloud Bridge) enregistre
désormais l'`institution_key` exact de son expéditeur. `route_read_receipt()`
utilise cette valeur pour cibler directement le bon profil, sans deviner
par nom/rôle ; repli sur l'ancienne méthode uniquement pour les messages
antérieurs à cette colonne. Côté Cloud Bridge, `push_receipt_to_bridge()`
adresse désormais l'accusé via `bridge_slug(sender_institution_key)` —
une adresse que le sondage de l'expéditeur vérifie déjà nativement
(`keys_to_check` inclut `bridge_slug(institution_key)` depuis la v2.8.5),
aucune modification côté sondage nécessaire.

**Second problème trouvé en marge, corrigé aussi** : même une fois le
routage réparé côté serveur, cliquer "Accusé" depuis l'onglet Boîte de
réception ne rafraîchissait que cet onglet — le compteur du Tableau de
Bord restait visuellement figé jusqu'à un changement d'onglet manuel.
Corrigé : le clic sur "Accusé" rafraîchit désormais systématiquement
aussi les statistiques du Tableau de Bord, quel que soit l'onglet actif.

**Testé réellement, scénario complet reproduisant exactement le bug
signalé** : profil SECRETARIAT_DIRECTION envoie à SENDER (rôle par
défaut, aurait fonctionné par accident avant ce correctif) — test
insuffisant à lui seul ; le test déterminant utilise un profil **DRH**
(rôle non-défaut) comme émetteur du message vers SENDER, confirme
l'échec attendu SANS le correctif (non exécuté ici, déjà documenté en
v2.8.5), puis confirme `status == 'accuse'` correctement appliqué côté
DRH **avec** le correctif — 17 tests exécutés au total, tous passent.

### 25.4 🎨 Badges de statut colorés (Tableau de Bord)

Nouvelle fonction JS `messageStatusDot(row)` : 🟢 message entrant (déjà
reçu avec succès par définition) ou sortant avec accusé confirmé ; 🟠
sortant transmis mais accusé pas encore reçu ; 🔴 sortant archivé mais
jamais réellement transmis (`delivery_method` vide — ni correspondance
locale, ni Cloud Bridge configuré/atteint). Purement visuel, aucun
changement backend nécessaire (`delivery_method` déjà présent dans la
réponse JSON existante).

### 25.5 📄 Registre régénéré

`tools/generate_serial_registry.py` reconstruit entièrement à partir de
`app.py._EPSP_HIERARCHY` (plus de duplication de données) : chaque siège
EPSP réel + ses propres structures rattachées, et EPH/CHU avec leurs 4
rôles désormais alignés sur `allowed_roles()`. **652 entrées** générées
et vérifiées (contre 424 en v2.8.6) — structure inspectée ligne par
ligne pour Oran, confirmant les 4 sièges EPSP et leurs bonnes
polycliniques respectives.

### 25.6 Régression complète (v2.8.1 → v2.8.7)

17 tests exécutés sur l'arborescence finale : WAL, `tracking_number`,
HEIC, suivi des non-lus, appairage matériel + récupération, retrait de
Polyclinique, rôle EPH étendu accepté, présence des 4 EPSP + leurs
structures rattachées à Oran, verrouillage de rôle sur Salle de Soin, et
le scénario complet de correction du bug d'accusé (DRH → SENDER →
accusé → statut mis à jour). **Tout confirmé fonctionnel ensemble,
aucune régression.**

**Fichiers modifiés :** `app.py` (hiérarchie EPSP, rôles étendus,
`sender_institution_key`, routage d'accusé corrigé), `templates/index.html`
(option Secrétariat Général), `static/js/app.js` (libellé "- SIÈGE",
badges de statut, rafraîchissement du tableau de bord après accusé),
`tools/generate_serial_registry.py` (structure multi-EPSP). Aucune
fonctionnalité antérieure retirée.

---

## 26. v2.8.8 — Filtrage dynamique du Service destinataire, rôles EPH/CHU/EHU complétés (2026-09-21)

### 26.1 🎯 Filtrage dynamique du Service destinataire (formulaire d'envoi)

**Cause réelle** : `allowed_roles()` filtrait déjà correctement les
rôles disponibles selon l'institution (utilisé depuis la v2.8.6 pour
l'onboarding), mais le sélecteur "Service destinataire" du **formulaire
d'envoi** n'interrogeait jamais cette logique — il affichait toujours la
liste statique complète de tous les rôles possibles, quelle que soit
l'institution destinataire tapée.

**Correctif** (frontend uniquement) : nouvelle fonction
`guessInstitutionType(name)` qui déduit le type d'établissement à partir
du préfixe du nom (même convention que celle déjà utilisée par
`app.py` : "POLYCLINIQUE"/"SALLE DE SOIN" → EPSP-satellite, "EPSP " →
EPSP-siège, "DSP "/"EPH "/"CHU "/"EHU " → leurs types respectifs). À
chaque saisie dans "Institution destinataire", `refreshSendServiceOptions()`
interroge `GET /api/roles` (même endpoint que l'onboarding, aucune
duplication de règle côté client) et reconstruit le menu déroulant en
conséquence. Un nom non reconnu retombe sur la liste complète d'origine
(rien n'est jamais bloqué par erreur).

**Résultat, conforme à la demande** :
- Envoi vers un siège EPSP → seulement DIRECTEUR / DRH / DAS /
  Secrétariat de Direction proposés.
- Envoi vers une polyclinique → verrouillé sur Secrétariat de
  Polyclinique uniquement.
- Envoi vers EPH/CHU/EHU → les 5 rôles complets proposés (voir 26.2).

**Testé réellement** : logique `guessInstitutionType()` exécutée en
Node.js sur 8 cas réels (EPSP, polyclinique, salle de soin, EPH, CHU,
EHU, DSP, nom inconnu) — tous corrects. Les 3 règles de filtrage
backend testées via `/api/roles` : siège EPSP (exactement 4 rôles, sans
Secrétariat Général ni Secrétariat de Polyclinique), polyclinique
(verrouillée), EPH/CHU/EHU (5 rôles chacun).

Bonus de cohérence : nouveau dictionnaire `ROLE_LABELS`/`roleLabel()`
partagé entre l'onboarding et le formulaire d'envoi — les deux affichent
désormais les mêmes libellés français au lieu des valeurs brutes
(`SECRETARIAT_POLYCLINIQUE`) précédemment visibles dans l'onboarding.

### 26.2 🏛️ DIRECTEUR ajouté aux rôles EPH/CHU/EHU

**Changement de spécification** : la v2.8.7 avait défini EPH/CHU/EHU
avec 4 rôles (DRH, DAS, Secrétariat de Direction, Secrétariat Général) —
sans DIRECTEUR. La v2.8.8 corrige : ces trois types ont désormais
exactement les 5 mêmes rôles qu'un siège EPSP plus le Secrétariat
Général (DIRECTEUR, DRH, DAS, Secrétariat de Direction, Secrétariat
Général), appliqués identiquement à l'onboarding ET au formulaire
d'envoi. Aucune migration nécessaire : `ROLE_RULES` ne gouverne que les
choix proposés pour les nouveaux profils, jamais les valeurs déjà
stockées.

### 26.3 📄 Registre régénéré sans modification du script

Le script `tools/generate_serial_registry.py` appelle déjà
`tashil_app.allowed_roles("EPH")` / `("CHU")` directement — la mise à
jour de `ROLE_RULES` dans `app.py` s'y répercute automatiquement, sans
aucun changement de code nécessaire dans le script lui-même. **721
entrées** générées et vérifiées (contre 652 en v2.8.7) — `DIRECTEUR`
confirmé présent pour chaque EPH testé.

### 26.4 ⚠️ Point 4 (verrouillage anti-connexions simultanées) — clarification, rien implémenté

La demande ("lier la session à l'identifiant machine, rejeter toute
tentative depuis un second poste") est déjà couverte, de façon **plus
stricte**, par l'appairage matériel de la v2.8.5 :
- Un profil s'appaire automatiquement au **premier** poste qui le
  déverrouille avec succès (hash de l'empreinte matérielle stocké,
  jamais l'empreinte brute).
- Toute tentative de déverrouillage depuis un **second** poste échoue
  immédiatement avec `403 hardware_mismatch`, **avant même** la
  vérification du PIN — il n'existe donc jamais de session active sur
  ce second poste à "déconnecter", puisqu'elle n'a jamais pu s'ouvrir.
- Chaque poste héberge sa **propre** base SQLite locale (pas de compte
  hébergé centralement) — il n'existe pas de scénario où le même
  processus applicatif servirait deux sessions actives simultanément
  pour un même profil, y compris sur une seule machine (`_active_key`
  est une variable unique par processus depuis la conception initiale
  du projet).

**Rien n'a été ajouté ou modifié pour ce point** — construire un
mécanisme distinct de "session active à révoquer" risquerait d'être
**moins** sûr que l'existant : cela impliquerait qu'un second poste
connaissant le PIN puisse un jour "prendre la main" en expulsant le
premier, ce qui est exactement le scénario de clonage que l'appairage
matériel a été conçu pour empêcher définitivement. À rediscuter
explicitement si un besoin différent de celui déjà couvert existe
réellement (ex. stockage réseau partagé entre plusieurs machines, un
scénario distinct qui n'a pas été confirmé).

### 26.5 Régression complète (v2.8.1 → v2.8.8)

Suite exécutée sur l'arborescence finale : WAL, `tracking_number`,
routage d'accusé DRH (v2.8.7), appairage matériel, hiérarchie EPSP Oran
intacte, et les 3 nouvelles règles de filtrage v2.8.8 — **tout confirmé
fonctionnel ensemble, aucune régression.**

**Fichiers modifiés :** `app.py` (DIRECTEUR ajouté à `ROLE_RULES` pour
EPH/CHU/EHU), `static/js/app.js` (filtrage dynamique du service,
libellés français partagés). Aucun changement à
`tools/generate_serial_registry.py` (récupère déjà les règles depuis
`app.py`). Aucune fonctionnalité antérieure retirée.
