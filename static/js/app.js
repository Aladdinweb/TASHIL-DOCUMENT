// TASHIL DOCUMENT HUB — Web Edition — app.js
// Vanilla JS, no build step required (runs identically via Termux + browser).

const state = {
  profile: null,
  meta: null,
  currentView: "dashboard",
};

// ------------------------------------------------------------------ //
// Boot
// ------------------------------------------------------------------ //
async function boot() {
  const theme = localStorage.getItem("tashil_theme") || "dark";
  document.documentElement.setAttribute("data-theme", theme);

  const [metaRes, profileRes] = await Promise.all([
    fetch("/api/meta").then(r => r.json()),
    fetch("/api/profile").then(r => r.json()),
  ]);
  state.meta = metaRes;
  state.profile = profileRes.profile;

  if (profileRes.first_launch) {
    showOnboarding();
  } else {
    showApp();
  }
}

// ------------------------------------------------------------------ //
// Onboarding
// ------------------------------------------------------------------ //
function showOnboarding() {
  document.getElementById("onboarding-overlay").classList.remove("hidden");

  const wilayaSelect = document.getElementById("ob-wilaya");
  state.meta.wilayas.forEach(([code, name]) => {
    const opt = document.createElement("option");
    opt.value = code;
    opt.textContent = `${String(code).padStart(2, "0")} - ${name}`;
    if (code === 31) opt.selected = true; // default Oran
    wilayaSelect.appendChild(opt);
  });

  const typeSelect = document.getElementById("ob-type");
  state.meta.institution_types.forEach(t => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    typeSelect.appendChild(opt);
  });

  document.getElementById("ob-submit").addEventListener("click", submitOnboarding);
}

async function submitOnboarding() {
  const errorEl = document.getElementById("ob-error");
  errorEl.classList.add("hidden");

  const payload = {
    wilaya_code: parseInt(document.getElementById("ob-wilaya").value, 10),
    institution_type: document.getElementById("ob-type").value,
    institution_name: document.getElementById("ob-name").value.trim(),
  };

  if (!payload.institution_name) {
    errorEl.textContent = "Veuillez saisir le nom de l'établissement.";
    errorEl.classList.remove("hidden");
    return;
  }

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
// App shell
// ------------------------------------------------------------------ //
function showApp() {
  document.getElementById("app").classList.remove("hidden");
  document.getElementById("institution-name").textContent =
    state.profile ? state.profile.institution_name : "—";

  setupNav();
  setupThemeToggle();
  setupMessaging();
  renderParametres();
  loadDashboard();

  document.getElementById("lan-url").textContent = state.meta.lan_url;
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
async function loadDashboard() {
  const data = await fetch("/api/dashboard").then(r => r.json());
  document.getElementById("stat-sent").textContent = data.total_sent;
  document.getElementById("stat-received").textContent = data.total_received;
  document.getElementById("stat-pending").textContent = data.pending;

  const container = document.getElementById("recent-activity");
  if (!data.recent.length) {
    container.innerHTML = `<p class="empty-state">Aucune activité pour le moment.</p>`;
    return;
  }
  container.innerHTML = data.recent.map(row => `
    <div class="list-row">
      <div class="list-row-main">
        <span class="list-row-title">${row.direction === "sortant" ? "📤" : "📥"} ${escapeHtml(row.tracking_number)}</span>
        <span class="list-row-sub">${escapeHtml(row.subject || "(sans objet)")}</span>
      </div>
      <span class="list-row-badge">${escapeHtml(row.status)}</span>
    </div>
  `).join("");
}

// ------------------------------------------------------------------ //
// Messaging
// ------------------------------------------------------------------ //
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

  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  let selectedFile = null;

  dropZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
      selectedFile = fileInput.files[0];
      document.getElementById("drop-zone-text").textContent = `📎 ${selectedFile.name}`;
    }
  });
  dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("dragover"); });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", e => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      selectedFile = e.dataTransfer.files[0];
      document.getElementById("drop-zone-text").textContent = `📎 ${selectedFile.name}`;
    }
  });

  document.getElementById("msg-send-btn").addEventListener("click", async () => {
    const statusEl = document.getElementById("msg-send-status");
    statusEl.className = "status-line";
    statusEl.textContent = "";

    const recipient = document.getElementById("msg-recipient").value.trim();
    if (!selectedFile) {
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
    formData.append("file", selectedFile);
    formData.append("recipient", recipient);
    formData.append("subject", document.getElementById("msg-subject").value.trim());
    formData.append("body", document.getElementById("msg-body").value.trim());

    try {
      const res = await fetch("/api/messages/send", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Échec de l'envoi.");

      statusEl.textContent = `✅ Document transmis — ${data.tracking_number}`;
      statusEl.classList.add("ok");

      selectedFile = null;
      fileInput.value = "";
      document.getElementById("drop-zone-text").textContent = "📎 Glissez un fichier ici ou cliquez pour choisir";
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
        <span class="list-row-title">📥 ${escapeHtml(row.tracking_number)} — ${escapeHtml(row.subject || "(sans objet)")}</span>
        <span class="list-row-sub">De : ${escapeHtml(row.sender_institution || "—")}</span>
      </div>
    </div>
  `).join("");
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
  container.innerHTML = data.entries.map(row => `
    <div class="list-row">
      <div class="list-row-main">
        <span class="list-row-title">${row.direction === "sortant" ? "📤" : "📥"} ${escapeHtml(row.tracking_number)}</span>
        <span class="list-row-sub">${escapeHtml(row.recipient_institution || row.sender_institution || "—")} — ${escapeHtml(row.subject || "(sans objet)")}</span>
      </div>
      <span class="list-row-badge">${row.created_at.slice(0, 16).replace("T", " ")}</span>
    </div>
  `).join("");
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
}

// ------------------------------------------------------------------ //
// Utils
// ------------------------------------------------------------------ //
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

boot();
