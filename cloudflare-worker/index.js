/**
 * TASHIL BRIDGE — Cloudflare Worker (v1.0, remplace le GitHub Bridge)
 * ---------------------------------------------------------------------
 * Déployer : coller ce fichier dans Cloudflare Dashboard > Workers >
 * Quick Edit, puis Settings > Variables > KV Namespace Bindings :
 *   Variable name : TASHIL_KV
 *   KV namespace  : (créer/choisir le namespace existant)
 *
 * ⚠️ Ce Worker est exposé PUBLIQUEMENT (URL connue de tous les postes
 * TASHIL). Il n'y a AUCUNE authentification de plateforme fournie par
 * Cloudflare par défaut — toute la sécurité vient du code ci-dessous :
 *   - /register et toute route "protégée" exigent une clé secrète par
 *     établissement, jamais stockée en clair (seul son hash SHA-256 l'est).
 *   - Comparaison des hashs en temps constant (timingSafeEqual maison,
 *     Workers n'a pas crypto.timingSafeEqual de Node) pour limiter les
 *     attaques par mesure de temps de réponse.
 *   - Aucune route ne liste jamais les secrets ou leurs hashs.
 *
 * MODÈLE DE CLÉ SECRÈTE (choix de conception, à valider avec l'utilisateur) :
 *   TASHIL (app.py) génère une clé secrète aléatoire UNE SEULE FOIS, au
 *   premier lancement de l'application sur un poste, et l'utilise pour
 *   TOUT établissement onboardé sur CE poste. Le premier /register pour
 *   un institution_id donné "capture" cette clé comme preuve de propriété
 *   de cet identifiant — un second poste doit connaître cette MÊME clé
 *   (transmise hors-bande : QR de provisioning, saisie manuelle) pour
 *   pouvoir à son tour écrire au nom de ce même institution_id. C'est
 *   l'équivalent direct de l'ancien jeton GitHub partagé, mais désormais
 *   scellé par établissement plutôt que par dépôt entier.
 *
 * CYCLE DE VIE DES MESSAGES (TTL de sécurité) :
 *   Un message + ses pièces jointes restent dans KV jusqu'à réception
 *   explicite de l'Accusé (/accuse), qui les supprime immédiatement.
 *   MESSAGE_TTL_SECONDS est un filet de sécurité si l'Accusé n'arrive
 *   jamais (destinataire qui ne consulte plus) — purge automatique par
 *   Cloudflare KV lui-même, aucun job de nettoyage à programmer côté app.
 */

const MESSAGE_TTL_SECONDS = 30 * 24 * 60 * 60; // 30 jours — filet de sécurité, pas le chemin normal de nettoyage
const PRESENCE_TTL_SECONDS = 90;               // "en ligne" = annoncé il y a moins de 90s
const MAX_BODY_BYTES = 24 * 1024 * 1024;        // Workers KV : 25 Mo max par valeur — marge de sécurité

// ------------------------------------------------------------------ //
// CORS
// ------------------------------------------------------------------ //
// ⚠️ Ajouté sur demande explicite — par construction de TASHIL, app.py
// parle à ce Worker côté SERVEUR (urllib Python), jamais depuis le
// navigateur : CORS, un mécanisme appliqué uniquement par les
// navigateurs, ne s'applique donc à aucun appel réel de l'application
// actuelle. Ces en-têtes n'en restent pas moins une bonne pratique pour
// toute API publique (débogage direct depuis un navigateur, outils
// tiers, évolutions futures) — gardés volontairement permissifs
// (Access-Control-Allow-Origin: *) puisque chaque route reste de toute
// façon protégée par sa propre vérification de secret_key.
const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "86400",
};

function handleOptions() {
  return new Response(null, { status: 204, headers: CORS_HEADERS });
}

// ------------------------------------------------------------------ //
// Utilitaires crypto / réponses
// ------------------------------------------------------------------ //
function jsonResponse(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...CORS_HEADERS },
  });
}

function errorResponse(message, status) {
  return jsonResponse({ error: message }, status);
}

async function sha256Hex(text) {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, "0")).join("");
}

// Comparaison en temps constant — évite qu'une différence de latence
// révèle combien de caractères du hash correspondent.
function timingSafeEqualHex(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// institution_id arrive déjà "propre" côté app.py (c'est l'institution_key
// existant, déjà normalisé) — sanitize minimal pour qu'il reste un
// fragment de clé KV sûr (pas de ':' qui casserait le préfixage).
function sanitizeId(raw) {
  return String(raw || "").trim().replace(/[:\s]+/g, "_").slice(0, 200);
}

async function readJson(request) {
  const text = await request.text();
  if (text.length > MAX_BODY_BYTES) {
    throw new HttpError(413, "Corps de requête trop volumineux.");
  }
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new HttpError(400, "JSON invalide.");
  }
}

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// ------------------------------------------------------------------ //
// Device binding — device:{institution_id} = {secret_hash, hardware_id,
// registered_at}. Permanent (pas de TTL) : seul /unregister l'efface.
// ------------------------------------------------------------------ //
async function getDevice(env, institutionId) {
  const raw = await env.TASHIL_KV.get(`device:${institutionId}`);
  return raw ? JSON.parse(raw) : null;
}

// Vérifie secret_key pour institution_id. Lève HttpError(401) si absent/
// invalide. Utilisé par TOUTES les routes protégées — pas seulement
// /auth — pour qu'il n'existe aucune route "vérifiée une fois puis
// ouverte" : chaque appel prouve à nouveau la clé.
async function requireValidSecret(env, institutionId, secretKey) {
  const device = await getDevice(env, institutionId);
  if (!device) {
    throw new HttpError(401, "Établissement non enregistré — appelez /register d'abord.");
  }
  if (!secretKey) {
    throw new HttpError(401, "Clé secrète manquante.");
  }
  const providedHash = await sha256Hex(secretKey);
  if (!timingSafeEqualHex(providedHash, device.secret_hash)) {
    throw new HttpError(401, "Clé secrète invalide pour cet établissement.");
  }
  return device;
}

// ------------------------------------------------------------------ //
// Routes
// ------------------------------------------------------------------ //
async function handleRegister(request, env) {
  const body = await readJson(request);
  const institutionId = sanitizeId(body.institution_id);
  const secretKey = String(body.secret_key || "");
  const hardwareId = String(body.hardware_id || "");
  if (!institutionId || !secretKey) {
    return errorResponse("institution_id et secret_key sont requis.", 400);
  }

  const existing = await getDevice(env, institutionId);
  const providedHash = await sha256Hex(secretKey);

  if (existing) {
    if (!timingSafeEqualHex(providedHash, existing.secret_hash)) {
      // Même message que /auth pour ne pas distinguer "existe mais mauvaise
      // clé" de "clé invalide" — évite de confirmer l'existence d'un
      // institution_id à un appelant qui ne le connaît pas déjà.
      return errorResponse(
        "Cet établissement est déjà enregistré avec une clé secrète différente. " +
        "Fournissez la clé secrète d'origine, ou appelez /unregister avec cette clé " +
        "pour libérer l'identifiant avant un nouvel enregistrement.", 401
      );
    }
    // Même clé déjà connue — ré-enregistrement idempotent (ex. un second
    // rôle/profil sur le MÊME poste, ou un poste ré-apparié qui a adopté
    // cette même clé). On met à jour le hardware_id à titre indicatif
    // uniquement — ce n'est jamais un facteur de blocage ici, la clé
    // secrète est la seule preuve d'autorisation dans ce modèle.
    await env.TASHIL_KV.put(`device:${institutionId}`, JSON.stringify({
      ...existing, hardware_id: hardwareId || existing.hardware_id,
    }));
    return jsonResponse({ ok: true, status: "already_registered_same_key" });
  }

  await env.TASHIL_KV.put(`device:${institutionId}`, JSON.stringify({
    secret_hash: providedHash, hardware_id: hardwareId, registered_at: new Date().toISOString(),
  }));
  return jsonResponse({ ok: true, status: "claimed" });
}

async function handleAuth(request, env) {
  const body = await readJson(request);
  const institutionId = sanitizeId(body.institution_id);
  try {
    await requireValidSecret(env, institutionId, body.secret_key);
  } catch (e) {
    if (e instanceof HttpError) return errorResponse(e.message, e.status);
    throw e;
  }
  return jsonResponse({ ok: true });
}

async function handleUnregister(request, env) {
  const body = await readJson(request);
  const institutionId = sanitizeId(body.institution_id);
  try {
    await requireValidSecret(env, institutionId, body.secret_key);
  } catch (e) {
    if (e instanceof HttpError) return errorResponse(e.message, e.status);
    throw e;
  }
  await env.TASHIL_KV.delete(`device:${institutionId}`);
  return jsonResponse({ ok: true });
}

async function handleHeartbeat(request, env) {
  const body = await readJson(request);
  const institutionId = sanitizeId(body.institution_id);
  try {
    await requireValidSecret(env, institutionId, body.secret_key);
  } catch (e) {
    if (e instanceof HttpError) return errorResponse(e.message, e.status);
    throw e;
  }
  const record = {
    institution_id: institutionId,
    display_name: String(body.display_name || institutionId),
    wilaya_name: String(body.wilaya_name || ""),
    institution_type: String(body.institution_type || ""),
    last_seen: new Date().toISOString(),
  };
  await env.TASHIL_KV.put(`presence:${institutionId}`, JSON.stringify(record), {
    expirationTtl: PRESENCE_TTL_SECONDS,
  });
  return jsonResponse({ ok: true });
}

async function handlePresence(request, env) {
  // Lecture seule, non protégée par une clé spécifique : c'est la liste
  // des établissements EN LIGNE (annuaire), analogue à l'ancien
  // directory/ public du dépôt GitHub — aucune donnée sensible ici (pas
  // de secret, pas de contenu de message).
  const list = await env.TASHIL_KV.list({ prefix: "presence:" });
  const institutions = [];
  for (const key of list.keys) {
    const raw = await env.TASHIL_KV.get(key.name);
    if (raw) institutions.push(JSON.parse(raw));
  }
  return jsonResponse({ institutions });
}

async function handleSend(request, env) {
  const body = await readJson(request);
  const senderId = sanitizeId(body.sender_institution_id);
  const recipientId = sanitizeId(body.recipient_institution_id);
  const tracking = String(body.tracking || "");
  const attachments = Array.isArray(body.attachments) ? body.attachments : [];
  if (!senderId || !recipientId || !tracking) {
    return errorResponse("sender_institution_id, recipient_institution_id et tracking sont requis.", 400);
  }
  try {
    await requireValidSecret(env, senderId, body.secret_key);
  } catch (e) {
    if (e instanceof HttpError) return errorResponse(e.message, e.status);
    throw e;
  }
  if (!attachments.length) {
    return errorResponse("Au moins une pièce jointe est requise.", 400);
  }

  const meta = {
    tracking_number: tracking,
    sender_institution_id: senderId,
    sender_institution: String(body.sender_institution || ""),
    sender_institution_key: String(body.sender_institution_key || ""),  // passthrough only — never used for auth
    recipient_institution: String(body.recipient_institution || ""),
    recipient_role: String(body.recipient_role || ""),
    subject: String(body.subject || ""),
    body: String(body.body || ""),
    attachments: attachments.map(a => ({ file_original_name: String(a.file_original_name || "document") })),
    created_at: new Date().toISOString(),
  };

  await env.TASHIL_KV.put(`msg:${recipientId}:${tracking}`, JSON.stringify(meta), {
    expirationTtl: MESSAGE_TTL_SECONDS,
  });
  for (let i = 0; i < attachments.length; i++) {
    await env.TASHIL_KV.put(
      `attach:${recipientId}:${tracking}:${i}`,
      String(attachments[i].content_base64 || ""),
      { expirationTtl: MESSAGE_TTL_SECONDS }
    );
  }
  return jsonResponse({ ok: true });
}

async function handlePoll(request, env) {
  const url = new URL(request.url);
  const institutionId = sanitizeId(url.searchParams.get("institution_id"));
  const secretKey = url.searchParams.get("secret_key");
  try {
    await requireValidSecret(env, institutionId, secretKey);
  } catch (e) {
    if (e instanceof HttpError) return errorResponse(e.message, e.status);
    throw e;
  }
  const list = await env.TASHIL_KV.list({ prefix: `msg:${institutionId}:` });
  const messages = [];
  for (const key of list.keys) {
    const raw = await env.TASHIL_KV.get(key.name);
    if (raw) messages.push(JSON.parse(raw));
  }
  return jsonResponse({ messages });
}

async function handleFetchAttachment(request, env) {
  const url = new URL(request.url);
  const institutionId = sanitizeId(url.searchParams.get("institution_id"));
  const secretKey = url.searchParams.get("secret_key");
  const tracking = url.searchParams.get("tracking") || "";
  const index = url.searchParams.get("index") || "0";
  try {
    await requireValidSecret(env, institutionId, secretKey);
  } catch (e) {
    if (e instanceof HttpError) return errorResponse(e.message, e.status);
    throw e;
  }
  const content = await env.TASHIL_KV.get(`attach:${institutionId}:${tracking}:${index}`);
  if (content === null) return errorResponse("Pièce jointe introuvable (peut-être déjà purgée).", 404);
  return jsonResponse({ content_base64: content });
}

async function handleAccuse(request, env) {
  // v1.0 — "suppression immédiate dès la réception de l'Accusé" : appelé
  // par le DESTINATAIRE une fois le message consulté/accusé dans
  // l'interface TASHIL. Supprime le message + toutes ses pièces jointes
  // du KV du destinataire, et dépose un petit accusé pour l'EXPÉDITEUR
  // (consommé par le prochain /poll-receipts de l'expéditeur).
  const body = await readJson(request);
  const institutionId = sanitizeId(body.institution_id);  // le DESTINATAIRE qui accuse
  const tracking = String(body.tracking || "");
  const senderInstitutionId = sanitizeId(body.sender_institution_id);
  const acknowledgedBy = String(body.acknowledged_by || institutionId);
  if (!institutionId || !tracking) {
    return errorResponse("institution_id et tracking sont requis.", 400);
  }
  try {
    await requireValidSecret(env, institutionId, body.secret_key);
  } catch (e) {
    if (e instanceof HttpError) return errorResponse(e.message, e.status);
    throw e;
  }

  const metaKey = `msg:${institutionId}:${tracking}`;
  const rawMeta = await env.TASHIL_KV.get(metaKey);
  let attachmentCount = 0;
  if (rawMeta) {
    try { attachmentCount = (JSON.parse(rawMeta).attachments || []).length; } catch {}
  }
  await env.TASHIL_KV.delete(metaKey);
  for (let i = 0; i < attachmentCount; i++) {
    await env.TASHIL_KV.delete(`attach:${institutionId}:${tracking}:${i}`);
  }

  if (senderInstitutionId) {
    await env.TASHIL_KV.put(`receipt:${senderInstitutionId}:${tracking}`, JSON.stringify({
      tracking_number: tracking, acknowledged_by: acknowledgedBy, acknowledged_at: new Date().toISOString(),
    }), { expirationTtl: MESSAGE_TTL_SECONDS });
  }
  return jsonResponse({ ok: true });
}

async function handlePollReceipts(request, env) {
  const url = new URL(request.url);
  const institutionId = sanitizeId(url.searchParams.get("institution_id"));
  const secretKey = url.searchParams.get("secret_key");
  try {
    await requireValidSecret(env, institutionId, secretKey);
  } catch (e) {
    if (e instanceof HttpError) return errorResponse(e.message, e.status);
    throw e;
  }
  const list = await env.TASHIL_KV.list({ prefix: `receipt:${institutionId}:` });
  const receipts = [];
  for (const key of list.keys) {
    const raw = await env.TASHIL_KV.get(key.name);
    if (raw) {
      receipts.push(JSON.parse(raw));
      await env.TASHIL_KV.delete(key.name);  // consommé une fois lu — comme les messages, pas un journal permanent
    }
  }
  return jsonResponse({ receipts });
}

// ------------------------------------------------------------------ //
// Routage
// ------------------------------------------------------------------ //
async function handleHealth() {
  // Volontairement sans authentification : sert uniquement à distinguer
  // "ce Worker est joignable" de "le reste échoue pour une autre raison"
  // (identifiants invalides, etc.) — ne révèle rien de sensible.
  return jsonResponse({ ok: true, service: "tashil-bridge", version: "1.0" });
}

const ROUTES = {
  "GET /": handleHealth,
  "GET /health": handleHealth,  // alias explicite demandé côté app.py
  "POST /register": handleRegister,
  "POST /auth": handleAuth,
  "POST /unregister": handleUnregister,
  "POST /heartbeat": handleHeartbeat,
  "GET /presence": handlePresence,
  "POST /send": handleSend,
  "GET /poll": handlePoll,
  "GET /fetch-attachment": handleFetchAttachment,
  "POST /accuse": handleAccuse,
  "GET /poll-receipts": handlePollReceipts,
};

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return handleOptions();
    const url = new URL(request.url);
    const key = `${request.method} ${url.pathname}`;
    const handler = ROUTES[key];
    if (!handler) return errorResponse("Route inconnue.", 404);
    try {
      return await handler(request, env);
    } catch (e) {
      if (e instanceof HttpError) return errorResponse(e.message, e.status);
      return errorResponse(`Erreur interne du Worker : ${e.message}`, 500);
    }
  },
};
