// TASHIL DOCUMENT HUB — Web Edition — app.js
// Vanilla JS, no build step required (runs identically via Termux + browser).

// Safe replacement for `await res.json()` used throughout this file. The
// backend now always returns JSON on /api/ routes (see app.py's global
// error handlers), but this is a defense-in-depth backstop against any
// non-JSON response reaching the frontend (e.g. from something outside
// Flask entirely, like a captive-portal page on a public Wi-Fi). Without
// this, a non-JSON body throws a cryptic "Unexpected token '<'..." error
// instead of a readable message.
async function parseJsonResponse(res) {
  const contentType = res.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    const text = await res.text();
    throw new Error(
      `Réponse inattendue du serveur (HTTP ${res.status})` +
      (text ? ` : ${text.slice(0, 150)}` : "")
    );
  }
  return res.json();
}

const state = {
  profile: null,
  meta: null,
  session: null,
  currentView: "dashboard",
  lastKnownReceived: null,
  notifyPermissionAsked: false,
  pendingUnlockKey: null,   // institution_key currently shown on the PIN screen
  pendingUnlockNeedsSetup: false,
  appInitialized: false,    // event listeners wired only once (see showApp)
  selectedFile: null,       // currently attached file in the Envoi form
  bridgeEnabled: false,
  socket: null,              // v2.9.0: local realtime channel (this device <-> its own server)
  fallbackTimer: null,       // only runs while the socket is disconnected/unavailable
};

// ------------------------------------------------------------------ //
// Boot
// ------------------------------------------------------------------ //
async function boot() {
  const theme = localStorage.getItem("tashil_theme") || "dark";
  document.documentElement.setAttribute("data-theme", theme);

  const [metaRes, sessionRes] = await Promise.all([
    fetch("/api/meta").then(r => r.json()),
    fetch("/api/session").then(r => r.json()),
  ]);
  state.meta = metaRes;
  state.session = sessionRes;

  if (sessionRes.first_launch) {
    showOnboarding({ allowCancel: false });
  } else if (sessionRes.active) {
    state.profile = sessionRes.active;
    showApp();
  } else {
    showLockScreen();
  }
}

// ------------------------------------------------------------------ //
// Onboarding (creating a NEW institution profile)
// ------------------------------------------------------------------ //
function showOnboarding({ allowCancel }) {
  document.getElementById("lock-overlay").classList.add("hidden");
  document.getElementById("onboarding-overlay").classList.remove("hidden");

  const wilayaSelect = document.getElementById("ob-wilaya");
  wilayaSelect.innerHTML = "";
  state.meta.wilayas.forEach(([code, name]) => {
    const opt = document.createElement("option");
    opt.value = code;
    opt.textContent = `${String(code).padStart(2, "0")} - ${name}`;
    if (code === 31) opt.selected = true; // default Oran
    wilayaSelect.appendChild(opt);
  });

  const typeSelect = document.getElementById("ob-type");
  typeSelect.innerHTML = "";
  state.meta.institution_types.forEach(t => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    typeSelect.appendChild(opt);
  });

  // v2.8.6 fix: showOnboarding() runs every time the onboarding overlay
  // is shown (first launch AND "Ajouter un nouvel établissement" from
  // the lock screen) — these <select> elements themselves are never
  // recreated, only their options. addEventListener STACKS a new
  // listener on every call instead of replacing the old one, so after
  // N invocations, a single "change" event fired N overlapping async
  // refreshes, each appending its own copy of the role list before the
  // previous one's clear had a chance to "win" — that's the exact cause
  // of the reported repeating DIRECTEUR/DRH/DAS/SECRETARIAT entries.
  // Direct property assignment (.onchange =) REPLACES any previous
  // handler instead of stacking, regardless of how many times this
  // function runs.
  wilayaSelect.onchange = async () => { await refreshOnboardingInstitutions(); refreshOnboardingRoles(); };
  typeSelect.onchange = async () => { await refreshOnboardingInstitutions(); refreshOnboardingRoles(); };
  refreshOnboardingInstitutions().then(refreshOnboardingRoles);

  document.getElementById("ob-submit").onclick = submitOnboarding;

  const cancelBtn = document.getElementById("ob-cancel");
  if (allowCancel) {
    cancelBtn.classList.remove("hidden");
    cancelBtn.onclick = () => {
      document.getElementById("onboarding-overlay").classList.add("hidden");
      showLockScreen();
    };
  } else {
    cancelBtn.classList.add("hidden");
  }
}

// v2.8.5/6: asks the server which roles apply to the selected institution
// type + name — DIRECTEUR/DRH/DAS/SECRETARIAT_DIRECTION for an EPSP head
// office, DIRECTEUR/SECRETARIAT_DIRECTION for a DSP, SECRETARIAT_
// DIRECTION-only (auto-locked, disabled) for EPH/CHU/EHU, and
// SECRETARIAT_POLYCLINIQUE-only for a polyclinic NAME chosen under an
// EPSP. The server enforces this too (api_save_profile
// silently corrects an invalid role) — this is for a good default
// experience, not the actual security boundary.
async function refreshOnboardingRoles() {
  const institutionType = document.getElementById("ob-type").value;
  const nameSelect = document.getElementById("ob-name-select");
  const nameManual = document.getElementById("ob-name-manual");
  const effectiveName = nameSelect.value === "__other__" ? nameManual.value.trim() : nameSelect.value;
  const roleSelect = document.getElementById("ob-role");
  const roleNote = document.getElementById("ob-role-note");
  roleSelect.innerHTML = "";
  try {
    const params = new URLSearchParams({ institution_type: institutionType });
    if (effectiveName) params.set("institution_name", effectiveName);
    const data = await fetch(`/api/roles?${params.toString()}`).then(r => r.json());
    (data.roles || ["SECRETARIAT_DIRECTION"]).forEach(role => {
      const opt = document.createElement("option");
      opt.value = role;
      opt.textContent = roleLabel(role);
      roleSelect.appendChild(opt);
    });
    roleSelect.disabled = !!data.locked;
    roleNote.textContent = data.locked
      ? "Ce choix n'a qu'un seul service possible."
      : "";
  } catch (err) {
    roleSelect.innerHTML = `<option value="SECRETARIAT_DIRECTION">SECRETARIAT_DIRECTION</option>`;
    roleSelect.disabled = true;
  }
}

async function refreshOnboardingInstitutions() {
  const wilayaCode = parseInt(document.getElementById("ob-wilaya").value, 10);
  const institutionType = document.getElementById("ob-type").value;
  const nameSelect = document.getElementById("ob-name-select");
  const nameManual = document.getElementById("ob-name-manual");

  nameSelect.innerHTML = `<option value="">Chargement...</option>`;
  try {
    const data = await fetch(
      `/api/institutions/onboarding?wilaya_code=${wilayaCode}&institution_type=${encodeURIComponent(institutionType)}`
    ).then(r => r.json());

    nameSelect.innerHTML = "";
    (data.institutions || []).forEach(name => {
      const opt = document.createElement("option");
      opt.value = name;
      // v2.8.7: label an EPSP head office as "- SIÈGE" so it's visually
      // distinct from its own satellite structures listed right after
      // it — display only, the stored institution_name stays the clean
      // name with no suffix (matches server-side _is_satellite_structure_name).
      const isSatellite = /^(POLYCLINIQUE|SALLE DE SOIN)/i.test(name.trim());
      opt.textContent = (institutionType === "EPSP" && !isSatellite) ? `${name} - SIÈGE` : name;
      nameSelect.appendChild(opt);
    });
    const otherOpt = document.createElement("option");
    otherOpt.value = "__other__";
    otherOpt.textContent = "Autre (saisir manuellement)";
    nameSelect.appendChild(otherOpt);

    nameSelect.onchange = () => {
      const manual = nameSelect.value === "__other__";
      nameManual.classList.toggle("hidden", !manual);
      if (manual) nameManual.focus();
      refreshOnboardingRoles();
    };
    nameManual.oninput = () => refreshOnboardingRoles();
    nameManual.classList.add("hidden");
  } catch (err) {
    nameSelect.innerHTML = `<option value="__other__">Autre (saisir manuellement)</option>`;
    nameManual.classList.remove("hidden");
  }
}

async function submitOnboarding() {
  const errorEl = document.getElementById("ob-error");
  errorEl.classList.add("hidden");

  const nameSelect = document.getElementById("ob-name-select");
  const nameManual = document.getElementById("ob-name-manual");
  const institutionName = nameSelect.value === "__other__"
    ? nameManual.value.trim()
    : nameSelect.value;

  const pin = document.getElementById("ob-pin").value.trim();
  const pinConfirm = document.getElementById("ob-pin-confirm").value.trim();

  if (!institutionName) {
    errorEl.textContent = "Veuillez indiquer le nom de l'établissement.";
    errorEl.classList.remove("hidden");
    return;
  }
  if (!/^\d{4,6}$/.test(pin)) {
    errorEl.textContent = "Le code PIN doit contenir 4 à 6 chiffres.";
    errorEl.classList.remove("hidden");
    return;
  }
  if (pin !== pinConfirm) {
    errorEl.textContent = "Les deux codes PIN ne correspondent pas.";
    errorEl.classList.remove("hidden");
    return;
  }

  const payload = {
    wilaya_code: parseInt(document.getElementById("ob-wilaya").value, 10),
    institution_type: document.getElementById("ob-type").value,
    institution_name: institutionName,
    role: document.getElementById("ob-role").value || "SECRETARIAT_DIRECTION",
    pin,
  };

  try {
    const res = await fetch("/api/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Erreur inconnue.");

    state.profile = data.profile;
    document.getElementById("onboarding-overlay").classList.add("hidden");
    showApp();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  }
}

// ------------------------------------------------------------------ //
// Lock screen — profile picker + PIN entry
// ------------------------------------------------------------------ //
async function showLockScreen() {
  document.getElementById("app").classList.add("hidden");
  document.getElementById("onboarding-overlay").classList.add("hidden");
  document.getElementById("lock-overlay").classList.remove("hidden");
  document.getElementById("lock-pin-step").classList.add("hidden");
  // Explicitly reset to defaults every time — a previous call may have
  // left these hidden mid-PIN-entry (selectProfileForUnlock hides them).
  // Without this reset, a fresh call from a different entry point (e.g.
  // after deleting a profile) could land on a stuck, mostly-blank screen.
  document.getElementById("lock-profile-list").classList.remove("hidden");
  document.getElementById("lock-add-profile-btn").classList.remove("hidden");

  try {
    const session = await fetch("/api/session").then(r => r.json());
    state.session = session;
    renderProfileList(session.profiles);
    document.getElementById("lock-add-profile-btn").onclick = () => {
      document.getElementById("lock-overlay").classList.add("hidden");
      showOnboarding({ allowCancel: session.profiles.length > 0 });
    };
  } catch (err) {
    // Never leave the screen stuck blank with no way forward — this is
    // exactly the failure mode that previously showed as a frozen gray
    // screen with just the static "TASHIL DOCUMENT HUB" title visible.
    document.getElementById("lock-profile-list").innerHTML = `
      <p class="empty-state">
        ⛔ Impossible de charger la liste des établissements.<br>
        <button class="btn btn-secondary" id="lock-retry-btn" style="margin-top:10px;">🔄 Réessayer</button>
      </p>`;
    document.getElementById("lock-retry-btn").addEventListener("click", showLockScreen);
  }
}

function renderProfileList(profiles) {
  const container = document.getElementById("lock-profile-list");
  if (!profiles.length) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = profiles.map(p => `
    <div class="profile-item" data-key="${escapeHtml(p.institution_key)}">
      <div>
        <div class="profile-item-name">${escapeHtml(p.institution_name)}</div>
        <div class="profile-item-sub">${escapeHtml(p.wilaya_name)} — ${escapeHtml(p.institution_type)}</div>
      </div>
      <span class="profile-item-badge">${p.pin_set ? "🔒" : "⚙️ à configurer"}</span>
    </div>
  `).join("");

  container.querySelectorAll(".profile-item").forEach(el => {
    el.addEventListener("click", () => selectProfileForUnlock(el.dataset.key, profiles));
  });
}

function selectProfileForUnlock(key, profiles) {
  const profile = profiles.find(p => p.institution_key === key);
  state.pendingUnlockKey = key;
  state.pendingUnlockNeedsSetup = !profile.pin_set;

  document.getElementById("lock-profile-list").classList.add("hidden");
  document.getElementById("lock-add-profile-btn").classList.add("hidden");
  const pinStep = document.getElementById("lock-pin-step");
  pinStep.classList.remove("hidden");

  const pinInput = document.getElementById("lock-pin-input");
  const pinConfirmInput = document.getElementById("lock-pin-confirm-input");
  pinInput.value = "";
  pinConfirmInput.value = "";
  document.getElementById("lock-error").classList.add("hidden");

  if (state.pendingUnlockNeedsSetup) {
    document.getElementById("lock-pin-label").textContent =
      `Créez un code PIN pour ${profile.institution_name}`;
    pinConfirmInput.classList.remove("hidden");
    document.getElementById("lock-unlock-btn").textContent = "✅ Définir le code PIN";
  } else {
    document.getElementById("lock-pin-label").textContent =
      `Code PIN — ${profile.institution_name}`;
    pinConfirmInput.classList.add("hidden");
    document.getElementById("lock-unlock-btn").textContent = "🔓 Déverrouiller";
  }
  pinInput.focus();

  document.getElementById("lock-unlock-btn").onclick = submitUnlock;
  document.getElementById("lock-back-btn").onclick = () => {
    pinStep.classList.add("hidden");
    document.getElementById("lock-profile-list").classList.remove("hidden");
    document.getElementById("lock-add-profile-btn").classList.remove("hidden");
  };
  // v2.8.5: "Mot de passe oublié" — only meaningful once a profile has
  // been selected, since recovery needs to know WHICH institution's
  // serial_key to check against.
  const forgotBtn = document.getElementById("lock-forgot-btn");
  forgotBtn.classList.toggle("hidden", state.pendingUnlockNeedsSetup);
  forgotBtn.onclick = () => showRecoverStep(profile.institution_name);
}

// ------------------------------------------------------------------ //
// Recovery via institution serial_key (v2.8.5)
// ------------------------------------------------------------------ //
function showRecoverStep(institutionLabel) {
  document.getElementById("lock-pin-step").classList.add("hidden");
  const step = document.getElementById("lock-recover-step");
  step.classList.remove("hidden");
  document.getElementById("recover-serial").value = "";
  document.getElementById("recover-new-pin").value = "";
  document.getElementById("recover-error").classList.add("hidden");
  document.getElementById("recover-warning").classList.add("hidden");

  document.getElementById("recover-cancel-btn").onclick = () => {
    step.classList.add("hidden");
    document.getElementById("lock-pin-step").classList.remove("hidden");
  };
  document.getElementById("recover-submit-btn").onclick = submitRecovery;
}

async function submitRecovery() {
  const errorEl = document.getElementById("recover-error");
  const warningEl = document.getElementById("recover-warning");
  errorEl.classList.add("hidden");
  warningEl.classList.add("hidden");

  const serialKey = document.getElementById("recover-serial").value.trim();
  const newPin = document.getElementById("recover-new-pin").value.trim();

  if (!serialKey) {
    errorEl.textContent = "Veuillez saisir la clé série de l'établissement.";
    errorEl.classList.remove("hidden");
    return;
  }
  if (!/^\d{4,6}$/.test(newPin)) {
    errorEl.textContent = "Le nouveau code PIN doit contenir 4 à 6 chiffres.";
    errorEl.classList.remove("hidden");
    return;
  }

  try {
    const res = await fetch("/api/session/recover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        institution_key: state.pendingUnlockKey,
        serial_key: serialKey,
        new_pin: newPin,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Échec de la récupération.");

    state.profile = data.profile;
    if (data.warning) {
      // Shown once, deliberately, before entering the app — the person
      // needs to see this BEFORE they go looking for old documents that
      // are genuinely gone, not buried in a toast they might miss.
      warningEl.textContent = `⚠️ ${data.warning}`;
      warningEl.classList.remove("hidden");
      setTimeout(() => {
        document.getElementById("lock-overlay").classList.add("hidden");
        showApp();
      }, 4000);
    } else {
      document.getElementById("lock-overlay").classList.add("hidden");
      showApp();
    }
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  }
}

async function submitUnlock() {
  const errorEl = document.getElementById("lock-error");
  errorEl.classList.add("hidden");

  const pin = document.getElementById("lock-pin-input").value.trim();
  if (!/^\d{4,6}$/.test(pin)) {
    errorEl.textContent = "Le code PIN doit contenir 4 à 6 chiffres.";
    errorEl.classList.remove("hidden");
    return;
  }

  try {
    let res, data;
    if (state.pendingUnlockNeedsSetup) {
      const pinConfirm = document.getElementById("lock-pin-confirm-input").value.trim();
      if (pin !== pinConfirm) {
        errorEl.textContent = "Les deux codes PIN ne correspondent pas.";
        errorEl.classList.remove("hidden");
        return;
      }
      res = await fetch("/api/session/set-pin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ institution_key: state.pendingUnlockKey, pin }),
      });
    } else {
      res = await fetch("/api/session/unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ institution_key: state.pendingUnlockKey, pin }),
      });
    }
    data = await res.json();
    if (!res.ok) {
      // v2.8.5: a hardware-pairing rejection is a DIFFERENT situation
      // from a wrong PIN — this poste was simply never authorized for
      // this institution. Say so plainly and point at the actual way
      // out (recovery with the institution's own serial_key) rather
      // than leaving the person to retry a PIN that was never the issue.
      if (data.hardware_mismatch) {
        throw new Error(
          "⛔ Ce poste n'est pas autorisé pour cet établissement. " +
          "Si c'est un remplacement de machine légitime, utilisez " +
          "\"Mot de passe oublié / Déblocage\" ci-dessous avec la clé " +
          "série de l'établissement."
        );
      }
      throw new Error(data.error || "Échec du déverrouillage.");
    }

    state.profile = data.profile;
    document.getElementById("lock-overlay").classList.add("hidden");
    showApp();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  }
}

// ------------------------------------------------------------------ //
// App shell
// ------------------------------------------------------------------ //
function showApp() {
  document.getElementById("lock-overlay").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  document.getElementById("institution-name").textContent =
    state.profile ? state.profile.institution_name : "—";

  // One-time event wiring only — re-running this on every unlock would
  // stack duplicate listeners (double sends, double toasts) and spawn
  // multiple concurrent polling intervals, since locking no longer
  // reloads the page.
  if (!state.appInitialized) {
    setupNav();
    setupThemeToggle();
    setupMessaging();
    setupUpdateChecker();
    setupLogout();
    setupDeleteProfile();
    setupLockButton();
    setupRefreshButton();
    setupCopyLanUrl();
    setupCloudBridge();
    initRealtime();   // v2.9.0: sets up the local socket + its 5 min fallback once
    setupDocumentViewer();          // v2.9.1
    setupDiagnostics();             // v2.9.1
    setupEtablissementsActions();   // v2.9.1
    state.appInitialized = true;
  }

  // Per-unlock refresh: must never carry over from a previously active
  // profile (this is the actual data-isolation guarantee on the frontend
  // side — the backend already isolates storage, this ensures the UI
  // doesn't show stale counts from the last institution either).
  state.lastKnownReceived = null;
  resetMessagingForm();
  renderParametres();
  loadDashboard();
  loadInstitutions();
  requestNotificationPermission();
  joinRealtimeRoom();   // v2.9.0: (re)join every unlock — including switching profiles
  switchView("dashboard");

  document.getElementById("lan-url").textContent = state.meta.lan_url;
  document.getElementById("network-qr-img").src = `/api/network-qr.png?t=${Date.now()}`;
  document.getElementById("current-version").textContent = `v${state.meta.app_version}`;
}

function setupLockButton() {
  document.getElementById("lock-btn").onclick = lockSession;
}

function setupRefreshButton() {
  document.getElementById("refresh-btn").onclick = manualRefresh;
}

async function manualRefresh() {
  const btn = document.getElementById("refresh-btn");
  btn.classList.add("spinning");
  // v2.8.9: local-only refresh FIRST and awaited — this is always fast
  // (same-device SQLite, no network involved) so the button stops
  // spinning and the screen updates almost instantly regardless of
  // Cloud Bridge network conditions. The Cloud Bridge sync itself runs
  // AFTER, in the background, un-awaited — a slow or flaky GitHub
  // connection (the exact scenario behind "Erreur GitHub (0)") no
  // longer holds the button, or the rest of the UI, hostage. This is
  // the practical equivalent of running the network part on a separate
  // thread in a desktop app: the button's own responsiveness is now
  // decoupled from how long the network call takes.
  try {
    if (state.currentView === "dashboard") await loadDashboard();
    else if (state.currentView === "messagerie") {
      await loadInbox();
      await loadDashboard(); // keeps stat cards current even off-screen
    } else if (state.currentView === "registre") {
      const activeFilter = document.querySelector(".subtab[data-filter].active");
      await loadRegistre(activeFilter ? activeFilter.dataset.filter : "tous");
    } else if (state.currentView === "etablissements") {
      await loadEtablissements();
    } else if (state.currentView === "parametres") {
      await refreshBridgeUI();
    }
    showToast("🔄 Actualisé", "success");
  } catch (err) {
    showToast("⛔ Échec de l'actualisation", "error");
  } finally {
    btn.classList.remove("spinning");
  }

  // Fire-and-forget: whatever this finds (new messages, applied
  // receipts, retried pending pushes) surfaces via its own toasts/
  // notifications once it resolves, same as the existing 20s
  // background timer already does — the button doesn't wait for it.
  pollBridge(false)
    .then(() => {
      if (state.currentView === "dashboard") loadDashboard();
      else if (state.currentView === "messagerie") loadInbox();
    })
    .catch(() => {});
}

function setupCopyLanUrl() {
  document.getElementById("copy-lan-url-btn").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(state.meta.lan_url);
      showToast("📋 Lien copié", "success");
    } catch (err) {
      // Clipboard API can be unavailable in some webview contexts —
      // the URL is already shown as plain text as a fallback.
      showToast("⛔ Impossible de copier automatiquement — copiez le lien affiché.", "error");
    }
  });
}

async function lockSession() {
  try {
    await fetch("/api/session/lock", { method: "POST" });
  } catch (err) {
    // Even if the request fails, still send the user to the lock screen —
    // never leave archives visible on an uncertain network error.
  }
  leaveRealtimeRoom();   // v2.9.0: stop receiving this profile's socket events
  state.profile = null;
  document.getElementById("app").classList.add("hidden");
  await showLockScreen();
}

// ------------------------------------------------------------------ //
// Toast notifications
// ------------------------------------------------------------------ //
function showToast(message, kind = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${kind}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4500);
}

function requestNotificationPermission() {
  if (state.notifyPermissionAsked) return;
  state.notifyPermissionAsked = true;
  try {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission().catch(() => {});
    }
  } catch (err) {
    // Notification API unsupported in this environment — toasts still work
  }
}

function showSystemNotification(title, body) {
  try {
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification(title, { body, icon: "/static/assets/logo.png" });
    }
  } catch (err) {
    // Silently ignore — the in-app toast already covers this
  }
}

// Generates a short two-tone chime with the Web Audio API — no external
// audio file needed (nothing to bundle/package, works identically on
// every platform). Browsers require a prior user interaction before
// AudioContext can play sound (autoplay policy) — by the time a
// background poll fires the user has normally already clicked something,
// but the very first notification after launch could be silently blocked
// by that policy; this is a known, unavoidable browser constraint, not a
// bug — the toast/visual notification still fires regardless.
function playNotificationSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const now = ctx.currentTime;
    [880, 1320].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0, now + i * 0.12);
      gain.gain.linearRampToValueAtTime(0.2, now + i * 0.12 + 0.02);
      gain.gain.linearRampToValueAtTime(0, now + i * 0.12 + 0.18);
      osc.connect(gain).connect(ctx.destination);
      osc.start(now + i * 0.12);
      osc.stop(now + i * 0.12 + 0.2);
    });
  } catch (err) {
    // Web Audio unsupported in this context — toast/notification still fire
  }
}

// ------------------------------------------------------------------ //
// v2.9.0 — Local realtime (Flask-SocketIO) replacing the 8 s / 20 s
// polling loops. The socket connects THIS browser/window to ITS OWN
// local server only — delivery between two different PCs still travels
// through the Cloud Bridge poll, which now runs server-side (see
// app.py's _bridge_loop) and pushes a "new_document" / "receipt_update"
// event over this same socket the instant something is imported, instead
// of the UI having to ask every 20 s.
//
// The room is chosen by the SERVER from the unlocked profile — the
// client only ever asks to "join_room" with no argument, so a device on
// the LAN can never subscribe to another service's notifications.
//
// Fallback: while the socket is down (feature disabled in this build,
// or a real disconnect), a slow 5-minute safety-net poll takes over so
// nothing is ever silently stuck — the same manualRefresh() the 🔄
// button already uses.
// ------------------------------------------------------------------ //
const REALTIME_FALLBACK_MS = 5 * 60 * 1000;

function startFallbackPolling() {
  if (state.fallbackTimer) return;
  state.fallbackTimer = setInterval(() => { manualRefresh(); }, REALTIME_FALLBACK_MS);
}

function stopFallbackPolling() {
  if (state.fallbackTimer) {
    clearInterval(state.fallbackTimer);
    state.fallbackTimer = null;
  }
}

function initRealtime() {
  // meta.realtime reflects whether Flask-SocketIO actually loaded on the
  // server side (see app.py: _SOCKETIO_AVAILABLE) — if a packaged build
  // is somehow missing the dependency, this degrades to the fallback
  // poll instead of trying to connect to a socket that isn't there.
  if (typeof io === "undefined" || !(state.meta && state.meta.realtime)) {
    startFallbackPolling();
    return;
  }
  if (state.socket) return;  // never re-run — this function is only called once (see showApp)

  state.socket = io({ transports: ["websocket", "polling"], reconnectionDelayMax: 10000 });

  state.socket.on("connect", () => {
    stopFallbackPolling();
    joinRealtimeRoom();
    // Catches up on anything missed while disconnected (a message that
    // arrived during a brief network blip, for instance).
    if (state.profile) manualRefresh();
  });

  state.socket.on("disconnect", startFallbackPolling);

  state.socket.on("new_document", (data) => {
    const label = data && data.sender ? ` de ${data.sender}` : "";
    showToast(`📥 Nouveau document reçu${label}`, "success");
    showSystemNotification("TASHIL DOCUMENT HUB", `Nouveau document reçu${label}`);
    playNotificationSound();
    if (state.currentView === "dashboard") loadDashboard();
    if (state.currentView === "messagerie") loadInbox();
  });

  state.socket.on("receipt_update", (data) => {
    const who = data && data.acknowledged_by ? ` par ${data.acknowledged_by}` : "";
    const tracking = data && data.tracking_number ? data.tracking_number : "";
    showToast(`📄 Document ${tracking} consulté${who}`, "success");
    showSystemNotification("TASHIL DOCUMENT HUB", `Document ${tracking} consulté${who}`);
    playNotificationSound();
    if (state.currentView === "dashboard") loadDashboard();
    if (state.currentView === "messagerie") loadInbox();
  });

  // A queued send/receipt that had failed (see _flush_pending_pushes)
  // just went through — refresh so "En attente" doesn't look stuck.
  state.socket.on("sync_update", () => {
    if (state.currentView === "dashboard") loadDashboard();
  });

  // The server locked/deleted the profile we're subscribed to (e.g. the
  // "Zone dangereuse" delete action) — go straight to the lock screen
  // rather than let the UI keep showing now-inaccessible data.
  state.socket.on("session_locked", () => {
    leaveRealtimeRoom();
    state.profile = null;
    document.getElementById("app").classList.add("hidden");
    showLockScreen();
  });
}

function joinRealtimeRoom() {
  if (state.socket && state.socket.connected) {
    state.socket.emit("join_room");
  }
}

function leaveRealtimeRoom() {
  // No explicit "leave" call needed: the server clears the room on its
  // side (socketio.close_room) as soon as the profile is locked/deleted
  // — see _ui_session_closed in app.py. Kept as a named function so the
  // intent is clear at each call site above.
}

async function loadInstitutions() {
  try {
    const data = await fetch("/api/institutions").then(r => r.json());
    const datalist = document.getElementById("institutions-list");
    datalist.innerHTML = data.institutions.map(name =>
      `<option value="${escapeHtml(name)}"></option>`).join("");
  } catch (err) {
    // Datalist is a progressive enhancement — free typing still works if this fails
  }
}

function setupNav() {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => switchView(tab.dataset.view));
  });
}

function switchView(viewName) {
  state.currentView = viewName;
  document.querySelectorAll(".tab").forEach(t =>
    t.classList.toggle("active", t.dataset.view === viewName));
  document.querySelectorAll(".view").forEach(v =>
    v.classList.toggle("active", v.id === `view-${viewName}`));

  if (viewName === "dashboard") loadDashboard();
  if (viewName === "messagerie") loadInbox();
  if (viewName === "registre") loadRegistre("tous");
  if (viewName === "etablissements") loadEtablissements();
}

async function loadEtablissements() {
  const container = document.getElementById("etablissements-list");
  const offCard = document.getElementById("etablissements-bridge-off");
  const clearBtn = document.getElementById("etablissements-clear-btn");

  try {
    const data = await fetch("/api/bridge/directory").then(r => parseJsonResponse(r));
    if (!data.bridge_enabled) {
      offCard.classList.remove("hidden");
      clearBtn.classList.add("hidden");
      container.innerHTML = "";
      return;
    }
    offCard.classList.add("hidden");

    if (!data.institutions.length) {
      clearBtn.classList.add("hidden");
      container.innerHTML = `<p class="empty-state">Aucun établissement détecté pour le moment. ` +
        `Ils apparaîtront ici après leur première synchronisation avec le Réseau TASHIL.</p>`;
      return;
    }
    clearBtn.classList.remove("hidden");

    // v2.9.1: one row per establishment NAME (the backend already merges
    // every role/profile sharing that name and keeps only the most recent
    // heartbeat — see api_bridge_directory). A 🗑️ here removes this
    // establishment from the CONNECTED list only (its heartbeat file(s)):
    // it never touches messages, archives, or the profile itself, and it
    // will simply reappear at its next heartbeat if that device is still
    // active.
    container.innerHTML = data.institutions.map(inst => `
      <div class="list-row">
        <div class="list-row-main">
          <span class="list-row-title">
            <span class="bridge-dot ${inst.online ? "bridge-dot-on" : "bridge-dot-off"}"></span>
            ${escapeHtml(inst.institution_name)}
          </span>
          <span class="list-row-sub">${escapeHtml(inst.wilaya_name)} — ${escapeHtml(inst.institution_type)}</span>
        </div>
        <span class="list-row-badge">${inst.online ? "En ligne" : "Vu " + timeAgo(inst.last_seen)}</span>
        <div class="list-row-actions">
          <button class="row-btn danger" data-remove-establishment="${escapeHtml(inst.institution_name)}"
                  title="Retirer de la liste">🗑️</button>
        </div>
      </div>
    `).join("");

    container.querySelectorAll("[data-remove-establishment]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const name = btn.dataset.removeEstablishment;
        if (!confirm(`Retirer "${name}" de la liste des établissements connectés ?\n\n` +
                     `(Ceci n'affecte ni ses messages ni son profil — il réapparaîtra ` +
                     `automatiquement s'il est encore actif.)`)) return;
        try {
          const res = await fetch(`/api/bridge/directory/${encodeURIComponent(name)}`, { method: "DELETE" });
          const d = await parseJsonResponse(res);
          if (!res.ok) throw new Error(d.error || "Échec de la suppression.");
          showToast(`🗑️ "${name}" retiré de la liste`, "success");
          loadEtablissements();
        } catch (err) {
          showToast(`⛔ ${err.message}`, "error");
        }
      });
    });
  } catch (err) {
    clearBtn.classList.add("hidden");
    container.innerHTML = `<p class="empty-state">⛔ Impossible de charger la liste des établissements.</p>`;
  }
}

function setupEtablissementsActions() {
  document.getElementById("etablissements-clear-btn").addEventListener("click", async () => {
    if (!confirm("Vider entièrement la liste des établissements connectés ?\n\n" +
                 "Ceci n'affecte ni les messages ni les profils — un établissement encore " +
                 "actif réapparaîtra automatiquement à son prochain signal.")) return;
    try {
      const res = await fetch("/api/bridge/directory", { method: "DELETE" });
      const d = await parseJsonResponse(res);
      if (!res.ok) throw new Error(d.error || "Échec de l'opération.");
      showToast("🗑️ Liste des établissements vidée", "success");
      loadEtablissements();
    } catch (err) {
      showToast(`⛔ ${err.message}`, "error");
    }
  });
}

// ------------------------------------------------------------------ //
// v2.9.1 — In-app document viewer (PDF.js for PDFs, <img> for images).
// Fetches the SAME decrypted bytes as the 📥 download button, via
// ?inline=1 (see app.py), as a Blob — nothing is written to disk, and no
// external application is ever launched. PDF.js is loaded from
// static/js/vendor/pdfjs/ (bundled — no CDN, no internet dependency,
// works fully offline like the rest of this app).
// ------------------------------------------------------------------ //
const viewerState = {
  pdfDoc: null,        // pdfjsLib document, when previewing a PDF
  pageNum: 1,
  scale: 1.0,
  kind: null,          // "pdf" | "image" | "unsupported"
  objectUrl: null,      // for <img> — revoked on close to free memory
};

if (typeof pdfjsLib !== "undefined") {
  pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/js/vendor/pdfjs/pdf.worker.min.js";
}

function guessKindFromName(name) {
  const ext = (name.split(".").pop() || "").toLowerCase();
  if (ext === "pdf") return "pdf";
  if (["png", "jpg", "jpeg", "gif", "webp", "bmp"].includes(ext)) return "image";
  return "unsupported";
}

async function openDocumentViewer(messageId, fileName) {
  const modal = document.getElementById("viewer-modal");
  const loading = document.getElementById("viewer-loading");
  const canvas = document.getElementById("viewer-pdf-canvas");
  const img = document.getElementById("viewer-image");
  const unsupported = document.getElementById("viewer-unsupported");
  const pageControls = document.getElementById("viewer-page-controls");

  document.getElementById("viewer-filename").textContent = fileName || "Document";
  document.getElementById("viewer-modal").dataset.messageId = messageId;
  loading.classList.remove("hidden");
  canvas.classList.add("hidden");
  img.classList.add("hidden");
  unsupported.classList.add("hidden");
  pageControls.classList.add("hidden");
  viewerState.pdfDoc = null;
  viewerState.pageNum = 1;
  viewerState.scale = 1.0;
  document.getElementById("viewer-zoom-indicator").textContent = "100%";
  modal.classList.remove("hidden");

  const kind = guessKindFromName(fileName);
  viewerState.kind = kind;

  if (kind === "unsupported") {
    loading.classList.add("hidden");
    unsupported.classList.remove("hidden");
    return;
  }

  try {
    const res = await fetch(`/api/messages/${messageId}/download?inline=1`);
    if (!res.ok) throw new Error(`Le serveur a répondu ${res.status}`);
    const blob = await res.blob();

    if (kind === "image") {
      if (viewerState.objectUrl) URL.revokeObjectURL(viewerState.objectUrl);
      viewerState.objectUrl = URL.createObjectURL(blob);
      img.src = viewerState.objectUrl;
      img.onload = () => {
        loading.classList.add("hidden");
        img.classList.remove("hidden");
      };
      img.onerror = () => {
        loading.classList.add("hidden");
        unsupported.classList.remove("hidden");
      };
      return;
    }

    // kind === "pdf"
    if (typeof pdfjsLib === "undefined") {
      loading.classList.add("hidden");
      unsupported.classList.remove("hidden");
      showToast("⛔ Le visualiseur PDF n'a pas pu se charger.", "error");
      return;
    }
    const arrayBuffer = await blob.arrayBuffer();
    viewerState.pdfDoc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    pageControls.classList.remove("hidden");
    loading.classList.add("hidden");
    canvas.classList.remove("hidden");
    await renderPdfPage();
  } catch (err) {
    loading.classList.add("hidden");
    unsupported.classList.remove("hidden");
    showToast(`⛔ Aperçu impossible : ${err.message}`, "error");
  }
}

async function renderPdfPage() {
  if (!viewerState.pdfDoc) return;
  const page = await viewerState.pdfDoc.getPage(viewerState.pageNum);
  const viewport = page.getViewport({ scale: viewerState.scale });
  const canvas = document.getElementById("viewer-pdf-canvas");
  const ctx = canvas.getContext("2d");
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  await page.render({ canvasContext: ctx, viewport }).promise;
  document.getElementById("viewer-page-indicator").textContent =
    `${viewerState.pageNum} / ${viewerState.pdfDoc.numPages}`;
}

function closeDocumentViewer() {
  document.getElementById("viewer-modal").classList.add("hidden");
  viewerState.pdfDoc = null;
  if (viewerState.objectUrl) {
    URL.revokeObjectURL(viewerState.objectUrl);
    viewerState.objectUrl = null;
  }
}

// Printing: pdf.js draws to a <canvas>, and a canvas alone doesn't survive
// a straightforward print (browsers often skip its pixels). Simplest
// reliable approach here — including inside a pywebview window, which
// has no native print dialog of its own — is to hand the ORIGINAL file
// bytes to a hidden <iframe> and print that frame's own rendering:
// native for a PDF (the browser's built-in PDF viewer), and a plain
// <img> wrapper for a picture.
async function printCurrentDocument(messageId) {
  const frame = document.getElementById("print-frame");
  try {
    if (viewerState.kind === "pdf") {
      frame.src = `/api/messages/${messageId}/download?inline=1`;
    } else if (viewerState.kind === "image" && viewerState.objectUrl) {
      frame.srcdoc = `<html><body style="margin:0"><img src="${viewerState.objectUrl}" ` +
                      `style="max-width:100%" onload="window.print()"></body></html>`;
    } else {
      return;
    }
    frame.onload = () => {
      try { frame.contentWindow.focus(); frame.contentWindow.print(); }
      catch (e) { showToast("⛔ Impression indisponible pour ce document.", "error"); }
    };
  } catch (err) {
    showToast(`⛔ Impression impossible : ${err.message}`, "error");
  }
}

function setupDocumentViewer() {
  document.getElementById("viewer-close-btn").onclick = closeDocumentViewer;
  document.getElementById("viewer-modal").addEventListener("click", (e) => {
    if (e.target.id === "viewer-modal") closeDocumentViewer();  // click on the dim backdrop
  });
  document.getElementById("viewer-zoom-in").onclick = async () => {
    if (viewerState.kind !== "pdf") return;
    viewerState.scale = Math.min(3.0, viewerState.scale + 0.25);
    document.getElementById("viewer-zoom-indicator").textContent = `${Math.round(viewerState.scale * 100)}%`;
    await renderPdfPage();
  };
  document.getElementById("viewer-zoom-out").onclick = async () => {
    if (viewerState.kind !== "pdf") return;
    viewerState.scale = Math.max(0.25, viewerState.scale - 0.25);
    document.getElementById("viewer-zoom-indicator").textContent = `${Math.round(viewerState.scale * 100)}%`;
    await renderPdfPage();
  };
  document.getElementById("viewer-prev-page").onclick = async () => {
    if (!viewerState.pdfDoc || viewerState.pageNum <= 1) return;
    viewerState.pageNum -= 1;
    await renderPdfPage();
  };
  document.getElementById("viewer-next-page").onclick = async () => {
    if (!viewerState.pdfDoc || viewerState.pageNum >= viewerState.pdfDoc.numPages) return;
    viewerState.pageNum += 1;
    await renderPdfPage();
  };
  document.getElementById("viewer-print-btn").onclick = () => {
    // The currently open message id is stashed on the modal itself by
    // openDocumentViewer (avoids a second global just for this).
    const id = document.getElementById("viewer-modal").dataset.messageId;
    if (id) printCurrentDocument(id);
  };
}

function timeAgo(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "à l'instant";
  if (mins < 60) return `il y a ${mins} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `il y a ${hours} h`;
  return `il y a ${Math.floor(hours / 24)} j`;
}

function setupThemeToggle() {
  document.getElementById("theme-toggle").addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("tashil_theme", next);
    fetch("/api/profile/theme", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme: next }),
    }).catch(() => {});
  });
}

// ------------------------------------------------------------------ //
// Dashboard
// ------------------------------------------------------------------ //

// v2.8.4: short one-line preview shown under the message title —
// prefers the body text; falls back to the attached filename when the
// body is empty (still gives the reader something concrete to scan).
function messageExcerpt(row) {
  const body = (row.body || "").trim();
  if (body) return body.length > 60 ? body.slice(0, 60) + "…" : body;
  if (row.file_original_name) return `📎 ${row.file_original_name}`;
  return "—";
}

// v2.8.7: a simple colored dot per the requested convention:
// 🟢 received/acknowledged successfully, 🟠 sent but still awaiting
// accusé, 🔴 archived but never actually transmitted anywhere (no local
// match found, no Cloud Bridge configured/reachable). An entrant
// message is always green here — it already successfully arrived in
// this inbox by definition; the traffic-light states describe an
// outgoing message's delivery lifecycle, not a received one's.
function messageStatusDot(row) {
  if (row.direction === "entrant") return "🟢";
  if (row.status === "accuse") return "🟢";
  if (!row.delivery_method) return "🔴";
  return "🟠";
}

async function loadDashboard() {
  const data = await fetch("/api/dashboard").then(r => r.json());
  document.getElementById("stat-sent").textContent = data.total_sent;
  document.getElementById("stat-received").textContent = data.total_received;
  document.getElementById("stat-pending").textContent = data.pending;
  if (state.lastKnownReceived === null) state.lastKnownReceived = data.total_received;

  const container = document.getElementById("recent-activity");
  if (!data.recent.length) {
    container.innerHTML = `<p class="empty-state">Aucune activité pour le moment.</p>`;
    return;
  }
  container.innerHTML = data.recent.map(row => {
    const institution = row.direction === "sortant"
      ? (row.recipient_institution || "—")
      : (row.sender_institution || "—");
    return `
    <div class="list-row">
      <div class="list-row-main">
        <span class="list-row-title">${messageStatusDot(row)} ${row.direction === "sortant" ? "📤" : "📥"} ${escapeHtml(row.subject && row.subject.trim() ? row.subject : "Sans objet")}</span>
        <span class="list-row-sub">${escapeHtml(institution)} — ${escapeHtml(messageExcerpt(row))}</span>
        <span class="tracking-badge">${escapeHtml(row.tracking_number)}</span>
      </div>
      <span class="list-row-badge">${escapeHtml(row.status)}</span>
      <div class="list-row-actions">
        ${row.file_path ? `<button class="row-btn" data-preview="${row.id}" data-name="${escapeHtml(row.file_original_name || "")}" title="Aperçu">👁️</button>` : ""}
        ${row.file_path ? `<button class="row-btn" data-download="${row.id}" title="Télécharger">📥</button>` : ""}
        <button class="row-btn danger" data-delete="${row.id}" data-scope="dashboard" title="Supprimer">🗑️</button>
      </div>
    </div>
  `;
  }).join("");
  wireRowActions(container, loadDashboard);
}

// ------------------------------------------------------------------ //
// Shared row actions — download, delete, accusé de réception
// ------------------------------------------------------------------ //
function wireRowActions(container, onChanged) {
  container.querySelectorAll("[data-preview]").forEach(btn => {
    btn.addEventListener("click", () => {
      openDocumentViewer(btn.dataset.preview, btn.dataset.name || "document");
    });
  });

  container.querySelectorAll("[data-download]").forEach(btn => {
    btn.addEventListener("click", () => {
      window.open(`/api/messages/${btn.dataset.download}/download`, "_blank");
    });
  });

  container.querySelectorAll("[data-delete]").forEach(btn => {
    btn.addEventListener("click", async () => {
      if (!confirm("Supprimer définitivement ce document et son archive ?")) return;
      try {
        const res = await fetch(`/api/messages/${btn.dataset.delete}`, { method: "DELETE" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Échec de la suppression.");
        showToast("🗑️ Document supprimé", "success");
        if (onChanged) onChanged();
      } catch (err) {
        showToast(`⛔ ${err.message}`, "error");
      }
    });
  });

  container.querySelectorAll("[data-ack]").forEach(btn => {
    btn.addEventListener("click", async () => {
      try {
        const res = await fetch(`/api/messages/${btn.dataset.ack}/status`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "accuse" }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Échec de la confirmation.");
        showToast("✅ Réception confirmée", "success");
        if (onChanged) onChanged();
        // v2.8.7: an accusé always changes the sender's "En attente"
        // count on the Dashboard tab — refresh it here too, regardless
        // of which tab is currently visible, since this action can be
        // taken from the Inbox tab while Dashboard sits stale until the
        // person happens to switch back to it.
        if (onChanged !== loadDashboard) loadDashboard();
      } catch (err) {
        showToast(`⛔ ${err.message}`, "error");
      }
    });
  });
}

// ------------------------------------------------------------------ //
// Messaging
// ------------------------------------------------------------------ //

// v2.8.3: iPhones running Safari default their camera to HEIC — a
// perfectly valid photo, but Windows' built-in Photos app can't open
// it without an extra codec extension, which shows as "We can't open
// this file" to someone who has no reason to know the format even
// changed. Android camera captures are virtually always JPEG already,
// so this mainly affects iPhone-to-Windows sends specifically.
//
// Fix: if the selected/dropped file is HEIC/HEIF (or an image type the
// browser doesn't recognize as a standard displayable format), redraw
// it onto a canvas and re-export as a normal JPEG before it's ever
// attached to the send request. Non-image files (docx, pdf, xlsx...)
// and images already in a standard format (JPEG, PNG, WEBP, GIF) pass
// through completely untouched — this never re-encodes files that
// don't need it, and never touches non-image attachments.
//
// If the browser itself can't decode the source image (some non-Safari
// browsers can't decode HEIC either — canvas conversion depends on the
// browser being able to display it as an <img> first), the ORIGINAL
// file is sent unchanged rather than silently dropping the attachment.
// That's no worse than before this fix, and Android/Chrome camera
// captures were never HEIC to begin with, so this fallback path is
// rarely hit in practice.
const STANDARD_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp", "image/gif"]);

function looksLikeHeic(file) {
  const type = (file.type || "").toLowerCase();
  const name = (file.name || "").toLowerCase();
  return type.includes("heic") || type.includes("heif") ||
         name.endsWith(".heic") || name.endsWith(".heif");
}

function needsJpegNormalization(file) {
  if (!file.type || !file.type.startsWith("image/")) {
    // Non-image (docx, pdf, xlsx...) — leave untouched, UNLESS the
    // filename itself still hints at HEIC/HEIF (some camera capture
    // flows report an empty/generic MIME type for HEIC files).
    return looksLikeHeic(file);
  }
  return looksLikeHeic(file) || !STANDARD_IMAGE_TYPES.has(file.type.toLowerCase());
}

async function normalizeImageForUpload(file) {
  if (!needsJpegNormalization(file)) return file;

  let objectUrl;
  try {
    objectUrl = URL.createObjectURL(file);
    const img = await new Promise((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = () => reject(new Error("decode failed"));
      el.src = objectUrl;
    });

    const canvas = document.createElement("canvas");
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    canvas.getContext("2d").drawImage(img, 0, 0);

    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.92));
    if (!blob) return file; // conversion produced nothing usable — fall back to original

    const newName = (file.name || "photo").replace(/\.(heic|heif)$/i, "") + ".jpg";
    return new File([blob], newName, { type: "image/jpeg" });
  } catch (err) {
    // Browser couldn't decode the source (e.g. HEIC on a non-Safari
    // browser) — send the original file rather than lose the attachment.
    console.warn("TASHIL: image normalization skipped —", err);
    return file;
  } finally {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  }
}

// v2.8.8: shared French labels for role values — used by both the
// onboarding role selector and the send form's service selector, so
// the two never drift into showing different wording for the same role.
const ROLE_LABELS = {
  DIRECTEUR: "Directeur",
  DRH: "DRH",
  DAS: "DAS",
  SECRETARIAT_DIRECTION: "Secrétariat de Direction",
  SECRETARIAT_GENERAL: "Secrétariat Général",
  SECRETARIAT_POLYCLINIQUE: "Secrétariat de Polyclinique",
};
function roleLabel(role) {
  return ROLE_LABELS[role] || role;
}

// v2.8.8: the "Service destinataire" selector on the send form never
// actually filtered by which institution was typed/selected — it
// always showed the full static list of every possible role across
// every institution type, letting someone address a polyclinic's
// SECRETARIAT_POLYCLINIQUE-only inbox as "DIRECTEUR" (which the backend
// already tolerates via the single-profile fallback, but shouldn't be
// offered as a real choice in the first place). guessInstitutionType()
// reads the recipient's name using the SAME naming convention already
// used everywhere else in this app (app.py's own directory-building
// logic) to infer which type it belongs to, then asks the server
// (GET /api/roles — the same endpoint onboarding already uses) which
// roles actually apply, rather than duplicating ROLE_RULES here.
function guessInstitutionType(name) {
  const upper = (name || "").trim().toUpperCase();
  if (!upper) return null;
  if (upper.startsWith("POLYCLINIQUE") || upper.startsWith("SALLE DE SOIN")) return "EPSP";
  if (upper.startsWith("EPSP")) return "EPSP";
  if (upper.startsWith("DSP")) return "DSP";
  if (upper.startsWith("EHU")) return "EHU";
  if (upper.startsWith("EPH")) return "EPH";
  if (upper.startsWith("CHU")) return "CHU";
  return null; // unrecognized name — fall back to the full, unfiltered list
}

function resetSendServiceOptions() {
  const serviceSelect = document.getElementById("msg-service");
  serviceSelect.disabled = false;
  serviceSelect.innerHTML = `
    <option value="SECRETARIAT_DIRECTION">${roleLabel("SECRETARIAT_DIRECTION")} (par défaut)</option>
    <option value="SECRETARIAT_GENERAL">${roleLabel("SECRETARIAT_GENERAL")}</option>
    <option value="SECRETARIAT_POLYCLINIQUE">${roleLabel("SECRETARIAT_POLYCLINIQUE")}</option>
    <option value="DIRECTEUR">${roleLabel("DIRECTEUR")}</option>
    <option value="DRH">${roleLabel("DRH")}</option>
    <option value="DAS">${roleLabel("DAS")}</option>`;
}

async function refreshSendServiceOptions() {
  const recipient = document.getElementById("msg-recipient").value.trim();
  const serviceSelect = document.getElementById("msg-service");
  const guessedType = guessInstitutionType(recipient);
  if (!guessedType || !recipient) {
    resetSendServiceOptions();
    return;
  }
  try {
    const params = new URLSearchParams({ institution_type: guessedType, institution_name: recipient });
    const data = await fetch(`/api/roles?${params.toString()}`).then(r => r.json());
    if (!data.roles || !data.roles.length) { resetSendServiceOptions(); return; }
    serviceSelect.innerHTML = "";
    data.roles.forEach(role => {
      const opt = document.createElement("option");
      opt.value = role;
      opt.textContent = roleLabel(role);
      serviceSelect.appendChild(opt);
    });
    serviceSelect.disabled = !!data.locked;
  } catch (err) {
    resetSendServiceOptions();
  }
}

function resetMessagingForm() {
  state.selectedFile = null;
  const fileInput = document.getElementById("file-input");
  if (fileInput) fileInput.value = "";
  const dropText = document.getElementById("drop-zone-text");
  if (dropText) dropText.textContent = "📎 Glissez un fichier ici ou cliquez pour choisir";
  const statusEl = document.getElementById("msg-send-status");
  if (statusEl) { statusEl.textContent = ""; statusEl.className = "status-line"; }
  resetSendServiceOptions();
}

function setupMessaging() {
  document.querySelectorAll(".subtab[data-subview]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".subtab[data-subview]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".subview").forEach(v => v.classList.remove("active"));
      document.getElementById(`sub-${btn.dataset.subview}`).classList.add("active");
      if (btn.dataset.subview === "reception") loadInbox();
    });
  });

  document.querySelectorAll(".subtab[data-filter]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".subtab[data-filter]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      loadRegistre(btn.dataset.filter);
    });
  });

  document.getElementById("msg-recipient").addEventListener("input", refreshSendServiceOptions);
  document.getElementById("msg-recipient").addEventListener("change", refreshSendServiceOptions);

  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");

  dropZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    if (fileInput.files.length) {
      document.getElementById("drop-zone-text").textContent = "📎 Préparation…";
      state.selectedFile = await normalizeImageForUpload(fileInput.files[0]);
      document.getElementById("drop-zone-text").textContent = `📎 ${state.selectedFile.name}`;
    }
  });
  dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("dragover"); });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", async e => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      document.getElementById("drop-zone-text").textContent = "📎 Préparation…";
      state.selectedFile = await normalizeImageForUpload(e.dataTransfer.files[0]);
      document.getElementById("drop-zone-text").textContent = `📎 ${state.selectedFile.name}`;
    }
  });

  document.getElementById("msg-send-btn").addEventListener("click", async () => {
    const statusEl = document.getElementById("msg-send-status");
    statusEl.className = "status-line";
    statusEl.textContent = "";

    const recipient = document.getElementById("msg-recipient").value.trim();
    if (!state.selectedFile) {
      statusEl.textContent = "Veuillez sélectionner un fichier.";
      statusEl.classList.add("err");
      return;
    }
    if (!recipient) {
      statusEl.textContent = "Veuillez indiquer l'institution destinataire.";
      statusEl.classList.add("err");
      return;
    }

    const formData = new FormData();
    formData.append("file", state.selectedFile);
    formData.append("recipient", recipient);
    formData.append("service", document.getElementById("msg-service").value || "SECRETARIAT_DIRECTION");
    formData.append("subject", document.getElementById("msg-subject").value.trim());
    formData.append("body", document.getElementById("msg-body").value.trim());

    try {
      const res = await fetch("/api/messages/send", { method: "POST", body: formData });
      const data = await parseJsonResponse(res);
      if (!res.ok) throw new Error(data.error || "Échec de l'envoi.");

      if (data.delivered_locally) {
        statusEl.textContent = `✅ Document transmis et reçu — ${data.tracking_number}`;
        statusEl.classList.add("ok");
        showToast(`📤 Document remis à ${recipient}`, "success");
        showSystemNotification("TASHIL DOCUMENT HUB", `Document remis à ${recipient}`);
      } else if (data.delivered_via_bridge) {
        // This branch was previously missing entirely — a successful
        // Cloud Bridge delivery was incorrectly reported as "archived,
        // not transmitted" because only delivered_locally was checked.
        statusEl.textContent = `☁️ Document transmis via le Réseau TASHIL — ${data.tracking_number}. ` +
          `En attente de consultation par ${recipient}.`;
        statusEl.classList.add("ok");
        showToast(`☁️ Document transmis via le Cloud Bridge à ${recipient}`, "success");
        showSystemNotification("TASHIL DOCUMENT HUB", `Document transmis à ${recipient} via le Réseau TASHIL`);
      } else if (data.bridge_attempted) {
        statusEl.textContent = `⚠️ Document archivé — ${data.tracking_number}. ` +
          `La transmission via le Réseau TASHIL a échoué (vérifiez la connexion réseau ` +
          `dans Paramètres). Le document reste enregistré ici.`;
        statusEl.classList.add("err");
        showToast(`⚠️ Archivé — échec de la transmission distante`, "error");
      } else {
        statusEl.textContent = `📦 Document archivé — ${data.tracking_number}. ` +
          `Aucun profil "${recipient}" trouvé sur cet appareil, et le Réseau TASHIL n'est ` +
          `pas configuré ici : le document est enregistré mais n'a pas pu être transmis ` +
          `(voir Paramètres → Réseau TASHIL).`;
        statusEl.classList.add("err");
        showToast(`📦 Archivé — non transmis (${recipient} n'a pas de profil ici)`, "info");
      }

      resetMessagingForm();
      document.getElementById("msg-recipient").value = "";
      document.getElementById("msg-subject").value = "";
      document.getElementById("msg-body").value = "";
      loadDashboard();
    } catch (err) {
      statusEl.textContent = `⛔ ${err.message}`;
      statusEl.classList.add("err");
    }
  });
}

async function loadInbox() {
  const data = await fetch("/api/messages?direction=entrant").then(r => r.json());
  const container = document.getElementById("inbox-list");
  if (!data.messages.length) {
    container.innerHTML = `<p class="empty-state">Boîte de réception vide.</p>`;
    return;
  }
  container.innerHTML = data.messages.map(row => `
    <div class="list-row">
      <div class="list-row-main">
        <span class="list-row-title">📥 ${escapeHtml(row.subject && row.subject.trim() ? row.subject : "Sans objet")}</span>
        <span class="list-row-sub">De : ${escapeHtml(row.sender_institution || "—")} — ${escapeHtml(messageExcerpt(row))}</span>
        <span class="tracking-badge">${escapeHtml(row.tracking_number)}</span>
      </div>
      <div class="list-row-actions">
        ${row.status === "accuse"
          ? `<span class="list-row-badge">✅ accusé</span>`
          : `<button class="row-btn ack" data-ack="${row.id}" title="Confirmer réception">✅ Accusé</button>`}
        ${row.file_path ? `<button class="row-btn" data-preview="${row.id}" data-name="${escapeHtml(row.file_original_name || "")}" title="Aperçu">👁️</button>` : ""}
        ${row.file_path ? `<button class="row-btn" data-download="${row.id}" title="Télécharger">📥</button>` : ""}
        <button class="row-btn danger" data-delete="${row.id}" title="Supprimer">🗑️</button>
      </div>
    </div>
  `).join("");
  wireRowActions(container, loadInbox);
}

// ------------------------------------------------------------------ //
// Registre
// ------------------------------------------------------------------ //
async function loadRegistre(filter) {
  const data = await fetch(`/api/registre?direction=${filter}`).then(r => r.json());
  const container = document.getElementById("registre-list");
  if (!data.entries.length) {
    container.innerHTML = `<p class="empty-state">Aucun enregistrement.</p>`;
    return;
  }
  container.innerHTML = data.entries.map(row => {
    const institution = row.recipient_institution || row.sender_institution || "—";
    return `
    <div class="list-row">
      <div class="list-row-main">
        <span class="list-row-title">${row.direction === "sortant" ? "📤" : "📥"} ${escapeHtml(row.subject && row.subject.trim() ? row.subject : "Sans objet")}</span>
        <span class="list-row-sub">${escapeHtml(institution)} — ${escapeHtml(messageExcerpt(row))}</span>
        <span class="tracking-badge">${escapeHtml(row.tracking_number)}</span>
      </div>
      <span class="list-row-badge">${row.created_at.slice(0, 16).replace("T", " ")}</span>
      <div class="list-row-actions">
        ${row.file_path ? `<button class="row-btn" data-preview="${row.id}" data-name="${escapeHtml(row.file_original_name || "")}" title="Aperçu">👁️</button>` : ""}
        ${row.file_path ? `<button class="row-btn" data-download="${row.id}" title="Télécharger">📥</button>` : ""}
        <button class="row-btn danger" data-delete="${row.id}" title="Supprimer">🗑️</button>
      </div>
    </div>
  `;
  }).join("");
  wireRowActions(container, () => loadRegistre(filter));
}

// ------------------------------------------------------------------ //
// v2.9.1 — Diagnostic & Santé du système (Paramètres)
// ------------------------------------------------------------------ //
function diagRow(label, value, ok) {
  const cls = ok === undefined ? "" : (ok ? "diag-ok" : "diag-bad");
  return `<div class="diag-row ${cls}"><span>${escapeHtml(label)}</span><span class="diag-value">${escapeHtml(String(value))}</span></div>`;
}

function formatBytes(n) {
  if (n < 1024) return `${n} o`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} Ko`;
  return `${(n / (1024 * 1024)).toFixed(2)} Mo`;
}

async function runDiagnostics() {
  const out = document.getElementById("diag-results");
  out.innerHTML = `<p class="empty-state">Diagnostic en cours...</p>`;
  const rows = [];

  // 1) Serveur local & WebSocket
  try {
    const h = await fetch("/api/health").then(r => r.json());
    rows.push(diagRow("Serveur Flask", "en ligne", true));
    rows.push(diagRow("WebSocket (Flask-SocketIO)",
      h.socketio_available ? "disponible" : "indisponible (repli sur sondage 5 min)",
      h.socketio_available));
  } catch (err) {
    rows.push(diagRow("Serveur Flask", `injoignable (${err.message})`, false));
  }

  // 2) Intégrité SQLite
  try {
    const d = await fetch("/api/diagnostics/sqlite").then(r => parseJsonResponse(r));
    if (d.error) throw new Error(d.error);
    rows.push(diagRow("Intégrité SQLite (quick_check)", d.quick_check, d.healthy));
    rows.push(diagRow("Taille de la base", formatBytes(d.db_size_bytes)));
  } catch (err) {
    rows.push(diagRow("Intégrité SQLite", `⛔ ${err.message}`, false));
  }

  // 3) Quota GitHub Bridge
  try {
    const q = await fetch("/api/diagnostics/github-quota").then(r => parseJsonResponse(r));
    if (!q.bridge_enabled) {
      rows.push(diagRow("Quota Réseau TASHIL (GitHub)", "non configuré"));
    } else if (q.error) {
      rows.push(diagRow("Quota Réseau TASHIL (GitHub)", `⛔ ${q.error}`, false));
    } else {
      rows.push(diagRow("Quota Réseau TASHIL (GitHub)",
        `${q.remaining} / ${q.limit} requêtes restantes`, q.remaining > 100));
    }
  } catch (err) {
    rows.push(diagRow("Quota Réseau TASHIL (GitHub)", `⛔ ${err.message}`, false));
  }

  out.innerHTML = rows.join("");
}

function setupDiagnostics() {
  document.getElementById("diag-run-btn").onclick = runDiagnostics;

  document.getElementById("diag-vacuum-btn").onclick = async () => {
    const statusEl = document.getElementById("diag-action-status");
    statusEl.textContent = "Optimisation en cours (peut prendre quelques secondes)...";
    try {
      const d = await fetch("/api/maintenance/vacuum", { method: "POST" }).then(r => parseJsonResponse(r));
      if (d.error) throw new Error(d.error);
      statusEl.textContent = `✅ Base optimisée — ${formatBytes(d.reclaimed_bytes)} récupéré(s) ` +
        `(${formatBytes(d.size_before_bytes)} → ${formatBytes(d.size_after_bytes)}).`;
    } catch (err) {
      statusEl.textContent = `⛔ ${err.message}`;
    }
  };

  document.getElementById("diag-clear-cache-btn").onclick = async () => {
    const statusEl = document.getElementById("diag-action-status");
    statusEl.textContent = "Nettoyage en cours...";
    try {
      const d = await fetch("/api/maintenance/clear-cache", { method: "POST" }).then(r => parseJsonResponse(r));
      if (d.error) throw new Error(d.error);
      statusEl.textContent = d.files_removed > 0
        ? `✅ ${d.files_removed} fichier(s) temporaire(s) supprimé(s) (${formatBytes(d.freed_bytes)} libérés).`
        : "✅ Aucun fichier temporaire obsolète à nettoyer.";
    } catch (err) {
      statusEl.textContent = `⛔ ${err.message}`;
    }
  };
}

// ------------------------------------------------------------------ //
// Paramètres
// ------------------------------------------------------------------ //
function renderParametres() {
  if (!state.profile) return;
  document.getElementById("pf-wilaya").textContent = `Wilaya : ${state.profile.wilaya_name}`;
  document.getElementById("pf-type").textContent = `Type : ${state.profile.institution_type}`;
  document.getElementById("pf-name").textContent = `Nom : ${state.profile.institution_name}`;
  document.getElementById("pf-serial").textContent = state.profile.serial_key;
  document.getElementById("pf-routing-id").textContent = state.profile.institution_key;
}

// ------------------------------------------------------------------ //
// OTA update checker (GitHub Releases API)
// ------------------------------------------------------------------ //
function setupUpdateChecker() {
  document.getElementById("check-update-btn").addEventListener("click",
    () => checkForUpdate({ status: "update-status", banner: "update-banner",
                            message: "update-message", link: "update-download-link" }));
}

// v2.9.1: the same check is now also offered from the lock screen and the
// onboarding screen (see setupLockAndOnboardingUpdateCheck below) — wired
// once at boot, since those screens exist before any profile is ever
// unlocked. checkForUpdate() itself takes no session/profile: it is a
// plain public GET to GitHub's release API (client-side, same call as
// before), so it works identically whether the app is locked or not.
function parseVersion(tag) {
  // Accepts "v2.1.0" or "2.1.0"; returns [2,1,0] for comparison
  const clean = tag.replace(/^v/i, "");
  return clean.split(".").map(n => parseInt(n, 10) || 0);
}

function isNewer(remote, current) {
  for (let i = 0; i < Math.max(remote.length, current.length); i++) {
    const r = remote[i] || 0;
    const c = current[i] || 0;
    if (r > c) return true;
    if (r < c) return false;
  }
  return false;
}

async function checkForUpdate(ids) {
  const statusEl = document.getElementById(ids.status);
  const banner = document.getElementById(ids.banner);
  statusEl.className = "status-line";
  statusEl.textContent = "Recherche en cours...";
  banner.classList.add("hidden");

  try {
    const res = await fetch(
      `https://api.github.com/repos/${state.meta.github_repo}/releases/latest`,
      { headers: { "Accept": "application/vnd.github+json" } }
    );
    if (!res.ok) throw new Error(`GitHub a répondu avec le statut ${res.status}`);
    const release = await res.json();

    const remoteVersion = parseVersion(release.tag_name || "0.0.0");
    const currentVersion = parseVersion(state.meta.app_version);

    if (isNewer(remoteVersion, currentVersion)) {
      const asset = (release.assets || []).find(a => a.name.endsWith(".exe"));
      document.getElementById(ids.message).textContent =
        `Nouvelle version disponible : ${release.tag_name} (actuelle : v${state.meta.app_version})`;
      document.getElementById(ids.link).href =
        asset ? asset.browser_download_url : release.html_url;
      banner.classList.remove("hidden");
      statusEl.textContent = "";
    } else {
      statusEl.textContent = "✅ TASHIL est à jour.";
    }
  } catch (err) {
    statusEl.textContent = `⛔ Impossible de vérifier les mises à jour : ${err.message}`;
  }
}

// v2.9.1: wired ONCE at boot (.onclick= assignment, not addEventListener —
// same v2.8.6 lesson as showOnboarding()'s <select> handlers: these two
// screens can each be (re)shown many times in one session, and stacking
// listeners on every show would fire the check N times per click).
function setupLockAndOnboardingUpdateCheck() {
  document.getElementById("lock-check-update-btn").onclick = () =>
    checkForUpdate({ status: "lock-update-status", banner: "lock-update-banner",
                      message: "lock-update-message", link: "lock-update-download-link" });
  document.getElementById("ob-check-update-btn").onclick = () =>
    checkForUpdate({ status: "ob-update-status", banner: "ob-update-banner",
                      message: "ob-update-message", link: "ob-update-download-link" });
}

// ------------------------------------------------------------------ //
// Cloud Bridge (GitHub-backed remote transmission)
// ------------------------------------------------------------------ //
function setupCloudBridge() {
  document.getElementById("bridge-save-btn").addEventListener("click", saveBridgeConfig);
  document.getElementById("bridge-import-btn").addEventListener("click", importBridgeCode);
  document.getElementById("bridge-poll-btn").addEventListener("click", () => pollBridge(true));
  document.getElementById("bridge-disable-btn").addEventListener("click", disableBridge);
  document.getElementById("bridge-show-qr-btn").addEventListener("click", toggleProvisioningQr);
  document.getElementById("network-test-btn").addEventListener("click", runNetworkTest);
  setupQrImageInput();
  refreshBridgeUI();
}

function setupQrImageInput() {
  const dropZone = document.getElementById("qr-drop-zone");
  const fileInput = document.getElementById("qr-file-input");

  dropZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) decodeQrImageFile(fileInput.files[0]);
  });
  dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("dragover"); });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", e => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length) decodeQrImageFile(e.dataTransfer.files[0]);
  });
}

async function decodeQrImageFile(file) {
  const statusEl = document.getElementById("qr-decode-status");
  statusEl.className = "status-line";
  statusEl.textContent = "Décodage de l'image...";

  const formData = new FormData();
  formData.append("image", file);

  try {
    const res = await fetch("/api/bridge/decode-qr-image", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Échec du décodage.");

    document.getElementById("bridge-import-input").value = data.code;
    statusEl.textContent = "✅ QR décodé — vérifiez puis cliquez sur Importer.";
    statusEl.classList.add("ok");
  } catch (err) {
    statusEl.textContent = `⛔ ${err.message}`;
    statusEl.classList.add("err");
  }
}

async function runNetworkTest() {
  const statusEl = document.getElementById("network-test-status");
  statusEl.className = "status-line";
  statusEl.textContent = "Test en cours...";

  try {
    const res = await fetch("/api/bridge/network-test");
    const data = await res.json();
    if (data.ok) {
      statusEl.textContent = `✅ ${data.message} (${data.elapsed_ms} ms)`;
      statusEl.classList.add("ok");
    } else {
      statusEl.textContent = `⛔ ${data.message}${data.hint ? " — " + data.hint : ""}`;
      statusEl.classList.add("err");
    }
  } catch (err) {
    statusEl.textContent = "⛔ Impossible de lancer le test.";
    statusEl.classList.add("err");
  }
}

async function refreshBridgeUI() {
  try {
    const cfg = await fetch("/api/bridge/config").then(r => r.json());
    state.bridgeEnabled = cfg.enabled;
    const configuredView = document.getElementById("bridge-configured-view");
    const setupView = document.getElementById("bridge-setup-view");
    const connectedBadge = document.getElementById("bridge-connected-badge");
    const disconnectedBadge = document.getElementById("bridge-disconnected-badge");

    if (cfg.configured && cfg.enabled) {
      connectedBadge.classList.remove("hidden");
      disconnectedBadge.classList.add("hidden");
      configuredView.classList.remove("hidden");
      setupView.classList.add("hidden");
      document.getElementById("bridge-repo-display").textContent =
        `${cfg.github_owner}/${cfg.github_repo}`;
    } else {
      connectedBadge.classList.add("hidden");
      disconnectedBadge.classList.remove("hidden");
      configuredView.classList.add("hidden");
      setupView.classList.remove("hidden");
      document.getElementById("bridge-qr-reveal").classList.add("hidden");
    }
  } catch (err) {
    // Bridge status is a progressive enhancement — leave the setup form visible
  }
}

function toggleProvisioningQr() {
  const reveal = document.getElementById("bridge-qr-reveal");
  const nowHidden = reveal.classList.toggle("hidden");
  if (!nowHidden) {
    document.getElementById("bridge-qr-img").src = `/api/bridge/provisioning-qr.png?t=${Date.now()}`;
  }
}

async function saveBridgeConfig() {
  const statusEl = document.getElementById("bridge-status-line");
  statusEl.className = "status-line";
  statusEl.textContent = "Vérification du dépôt...";

  const payload = {
    github_owner: document.getElementById("bridge-owner").value.trim(),
    github_repo: document.getElementById("bridge-repo").value.trim(),
    github_token: document.getElementById("bridge-token").value.trim(),
  };

  try {
    const res = await fetch("/api/bridge/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Échec de la configuration.");

    statusEl.textContent = "✅ Dépôt privé vérifié — Réseau TASHIL connecté.";
    statusEl.classList.add("ok");
    document.getElementById("bridge-token").value = "";
    showToast("🌉 Réseau TASHIL connecté", "success");
    await refreshBridgeUI();
  } catch (err) {
    statusEl.textContent = `⛔ ${err.message}`;
    statusEl.classList.add("err");
  }
}

async function importBridgeCode() {
  const statusEl = document.getElementById("bridge-status-line");
  statusEl.className = "status-line";
  statusEl.textContent = "Vérification du code...";

  const code = document.getElementById("bridge-import-input").value.trim();
  if (!code) {
    statusEl.textContent = "Veuillez coller un code de provisioning.";
    statusEl.classList.add("err");
    return;
  }

  try {
    const res = await fetch("/api/bridge/import-code", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Échec de l'import.");

    statusEl.textContent = "✅ Réseau TASHIL connecté.";
    statusEl.classList.add("ok");
    document.getElementById("bridge-import-input").value = "";
    showToast("🌉 Réseau TASHIL connecté", "success");
    await refreshBridgeUI();
  } catch (err) {
    statusEl.textContent = `⛔ ${err.message}`;
    statusEl.classList.add("err");
  }
}

async function disableBridge() {
  if (!confirm("Désactiver le Réseau TASHIL ? Les messages en attente distants ne seront plus relevés.")) {
    return;
  }
  await fetch("/api/bridge/disable", { method: "POST" });
  state.bridgeEnabled = false;
  showToast("🚫 Réseau TASHIL désactivé", "info");
  await refreshBridgeUI();
}

async function pollBridge(manual) {
  if (!state.bridgeEnabled) return;
  try {
    const res = await fetch("/api/bridge/poll", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      if (manual) showToast(`⛔ ${data.error || "Échec de la vérification distante."}`, "error");
      return;
    }
    if (data.new_messages > 0) {
      showToast(`📥 ${data.new_messages} message(s) reçu(s) via le Cloud Bridge`, "success");
      showSystemNotification("TASHIL DOCUMENT HUB",
        `${data.new_messages} nouveau(x) message(s) distant(s) reçu(s)`);
      playNotificationSound();
      if (state.currentView === "dashboard") loadDashboard();
      if (state.currentView === "messagerie") loadInbox();
    } else if (manual) {
      showToast("✅ Aucun nouveau message distant.", "info");
    }

    if (data.receipts && data.receipts.length > 0) {
      data.receipts.forEach(receipt => {
        const message = `📄 Le document ${receipt.tracking_number} a été consulté / réceptionné par ${receipt.acknowledged_by}`;
        showToast(message, "success");
        showSystemNotification("TASHIL DOCUMENT HUB", message);
        playNotificationSound();
      });
      if (state.currentView === "dashboard") loadDashboard();
      if (state.currentView === "messagerie") loadInbox();
    }
  } catch (err) {
    if (manual) showToast("⛔ Impossible de contacter le Cloud Bridge.", "error");
  }
}

// ------------------------------------------------------------------ //
// Logout = lock (switch institutions without deleting anything)
// ------------------------------------------------------------------ //
function setupLogout() {
  document.getElementById("logout-btn").onclick = () => {
    if (!confirm("Verrouiller cet établissement et revenir à l'écran de sélection ?")) {
      return;
    }
    lockSession();
  };
}

// ------------------------------------------------------------------ //
// Delete profile (irreversible — requires PIN re-entry, not just a
// dismissible dialog, since this permanently destroys archived documents)
// ------------------------------------------------------------------ //
function setupDeleteProfile() {
  document.getElementById("delete-profile-btn").onclick = openDeleteProfileModal;
  document.getElementById("delete-profile-cancel-btn").onclick = closeDeleteProfileModal;
  document.getElementById("delete-profile-confirm-btn").onclick = confirmDeleteProfile;
}

function openDeleteProfileModal() {
  document.getElementById("delete-profile-institution-name").textContent =
    state.profile ? state.profile.institution_name : "";
  document.getElementById("delete-profile-pin").value = "";
  document.getElementById("delete-profile-error").classList.add("hidden");
  document.getElementById("delete-profile-overlay").classList.remove("hidden");
}

function closeDeleteProfileModal() {
  document.getElementById("delete-profile-overlay").classList.add("hidden");
}

async function confirmDeleteProfile() {
  const errorEl = document.getElementById("delete-profile-error");
  errorEl.classList.add("hidden");

  const pin = document.getElementById("delete-profile-pin").value.trim();
  if (!/^\d{4,6}$/.test(pin)) {
    errorEl.textContent = "Le code PIN doit contenir 4 à 6 chiffres.";
    errorEl.classList.remove("hidden");
    return;
  }

  let deleteData;
  try {
    const res = await fetch("/api/profile/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin }),
    });
    deleteData = await res.json();
    if (!res.ok) throw new Error(deleteData.error || "Échec de la suppression.");
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
    return;
  }

  // The delete itself has now genuinely succeeded — anything below this
  // point is just redirect bookkeeping and must never be reported back
  // as a deletion failure if it hiccups.
  closeDeleteProfileModal();
  if (deleteData.warning) {
    showToast(`⚠️ ${deleteData.warning}`, "error");
  } else {
    showToast("🗑️ Profil supprimé définitivement", "success");
  }

  state.profile = null;
  document.getElementById("app").classList.add("hidden");

  try {
    const session = await fetch("/api/session").then(r => r.json());
    state.session = session;
    if (session.first_launch) {
      showOnboarding({ allowCancel: false });
      return;
    }
  } catch (err) {
    // Fall through to showLockScreen() below regardless — it has its own
    // retry-capable error handling rather than leaving the user stuck.
  }
  await showLockScreen();
}

// v2.9.1: state.meta is populated a few lines above, before onboarding/
// lock-screen branching — safe to wire immediately after boot() sets it.
setupLockAndOnboardingUpdateCheck();

// ------------------------------------------------------------------ //
// Utils
// ------------------------------------------------------------------ //
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

boot();
