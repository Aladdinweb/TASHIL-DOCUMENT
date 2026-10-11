# TASHIL BRIDGE — Cloudflare Worker

Remplace intégralement l'ancien GitHub Bridge. Déploiement :

1. Dashboard Cloudflare → Workers & Pages → créer un Worker (ou ouvrir
   celui existant à `tashil-bridge.alaacasanova31.workers.dev`).
2. **Quick Edit** → coller l'intégralité de `index.js` → **Save and deploy**.
3. **Settings → Variables → KV Namespace Bindings** → ajouter :
   - Variable name : `TASHIL_KV`
   - KV namespace : créer ou choisir un namespace existant.
4. Dans TASHIL (Paramètres → Réseau TASHIL), entrer l'URL du Worker.
   Aucune autre information n'est nécessaire — la clé secrète de chaque
   appareil est générée et gérée automatiquement par l'application.

## Modèle de sécurité (à relire avant mise en production)

Ce Worker est exposé **publiquement**. Toute la protection vient du code
lui-même :
- Chaque établissement est lié à un appareil par une clé secrète dont
  seul le hash SHA-256 est stocké dans KV.
- **Chaque** route protégée (pas seulement `/auth`) revérifie cette clé
  à chaque appel — il n'existe aucune route "vérifiée une fois puis
  ouverte".
- `/presence`, `/health` et `/` sont volontairement publics et sans
  authentification (ils ne révèlent rien de sensible : juste "qui est en
  ligne" et "ce Worker répond").

## Cycle de vie des messages

Un message et ses pièces jointes restent dans KV jusqu'à réception de
l'Accusé (`/accuse`), qui les supprime immédiatement. `MESSAGE_TTL_SECONDS`
(30 jours par défaut, en tête de fichier) est un filet de sécurité si
l'Accusé n'arrive jamais — pas le mécanisme de nettoyage normal.

## Limite connue, honnêtement non testée ici

Ce script a été testé en l'exécutant **réellement** (Node.js 22, qui
fournit nativement `Request`/`Response`/`crypto.subtle`/`fetch`) contre un
mock KV fidèle au comportement documenté de Cloudflare (TTL, exclusion des
clés expirées de `list()`), et contre un vrai serveur HTTP local parlant
avec `app.py` via `urllib`. **Il n'a cependant jamais tourné dans le vrai
isolat V8 de Cloudflare Workers ni contre le vrai Workers KV** — ce bac à
sable n'a pas accès à l'API Cloudflare. Le test le plus important restant
avant la production : déployer ce script tel quel et refaire le cycle
envoi → poll → accusé entre deux vrais postes TASHIL.
