/* =========================================================================
   cinéthèque — logique de l'interface (JavaScript vanilla, sans dépendance).
   Organisation : utilitaires → navigation → recherche → chaque page →
   fiche détaillée (modale). Le back-end expose tout via /api/*.
   ========================================================================= */
"use strict";

/* ----------------------------------------------------------- utilitaires */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

async function api(path, { method = "GET", body } = {}) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(path, opts);
  let data = {};
  try { data = await resp.json(); } catch (_) { /* réponse vide */ }
  if (!resp.ok) throw new Error(data.error || `Erreur ${resp.status}`);
  return data;
}

function esc(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

let toastTimer;
function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 2800);
}

const STATUTS = { vu: "Vu", a_voir: "À voir", en_cours: "En cours", abandonne: "Abandonné" };
const posterSrc = (u) => u || "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E";

/* Carte d'affiche réutilisée partout (bibliothèque, carrousels, découverte). */
function posterCard(item) {
  // Note TMDB (communauté, sur 10) : à droite de la ligne d'infos, pour ne pas
  // chevaucher le badge de statut sur les cartes étroites.
  const note = item.note_tmdb ? `<span class="meta-note">★ ${item.note_tmdb}</span>` : "";
  const statut = item.statut
    ? `<span class="poster-badge badge-${item.statut}">${STATUTS[item.statut] || ""}</span>` : "";
  const fav = item.favori ? `<span class="poster-fav">♥</span>` : "";
  const annee = item.annee || "";
  const type = item.type === "serie" ? "Série" : "Film";
  // Barre de progression pour les séries (épisodes vus / total).
  let prog = "";
  if (item.total_ep) {
    const pct = Math.round((item.vus_ep || 0) / item.total_ep * 100);
    prog = `<div class="poster-prog" title="${item.vus_ep || 0}/${item.total_ep} épisodes">
      <span style="width:${pct}%"></span></div>`;
  }
  return `<div class="poster" data-id="${item.id || ""}" data-tmdb="${item.tmdb_id || ""}"
       data-type="${item.type || ""}">
    <img class="poster-img" loading="lazy" src="${posterSrc(item.affiche)}" alt="">
    ${statut}${fav}
    <div class="poster-body">
      <div class="poster-title">${esc(item.titre)}</div>
      <div class="poster-meta"><span>${type}${annee ? " · " + annee : ""}</span>${note}</div>
      ${prog}
    </div>
  </div>`;
}

/* Ouvre l'élément cliqué : titre local → fiche ; résultat TMDB → ajout + fiche. */
async function openItem(el) {
  const id = el.dataset.id;
  if (id) return openDetail(Number(id));
  const tmdb = Number(el.dataset.tmdb), type = el.dataset.type;
  if (!tmdb || !type) return;
  try {
    const r = await api("/api/library", { method: "POST", body: { tmdb_id: tmdb, type } });
    toast("Ajouté à la bibliothèque");
    openDetail(r.id);
  } catch (e) { toast(e.message); }
}

function bindGrid(container) {
  container.addEventListener("click", (e) => {
    const card = e.target.closest(".poster");
    if (card) openItem(card);
  });
}

/* ------------------------------------------------------------ navigation */
const MAIN_TABS = ["suggestions", "bibliotheque", "decouverte", "futur"];
const moreSheet = $("#more-sheet");
const filterBackdrop = $("#filter-backdrop");

function closeSheet() { moreSheet && moreSheet.classList.add("hidden"); }
function closeToolbars() {
  $$(".toolbar.open").forEach((t) => t.classList.remove("open"));
  filterBackdrop && filterBackdrop.classList.add("hidden");
}

function showTab(name) {
  $$("#main-tabs .tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $$(".page").forEach((p) => p.classList.toggle("active", p.id === `page-${name}`));
  // synchronise la barre du bas (mobile) + état du bouton « Plus »
  $$(".bnav[data-tab]").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  const more = $("#bnav-more");
  if (more) more.classList.toggle("active", !MAIN_TABS.includes(name));
  closeSheet(); closeToolbars();
  window.scrollTo(0, 0);
  LOADERS[name] && LOADERS[name]();
}

document.addEventListener("click", (e) => {
  const tab = e.target.closest("[data-tab]");
  if (tab) return showTab(tab.dataset.tab);
  const goto = e.target.closest("[data-goto]");
  if (goto) { e.preventDefault(); showTab(goto.dataset.goto); }
});

/* Barre du bas : bouton « Plus » → panneau ; filtres → feuille du bas. */
$("#bnav-more").addEventListener("click", () => moreSheet.classList.toggle("hidden"));
document.addEventListener("click", (e) => {
  if (e.target.closest("[data-close-sheet]")) closeSheet();
  const fb = e.target.closest(".filter-btn");
  if (fb) {
    const tb = document.getElementById(fb.dataset.toolbar);
    if (tb) { tb.classList.add("open"); filterBackdrop.classList.remove("hidden"); }
    return;
  }
  if (e.target.closest(".filter-done")) closeToolbars();
});
filterBackdrop.addEventListener("click", closeToolbars);

/* --------------------------------------------------------------- recherche */
let searchTimer;
const searchInput = $("#search-input");
const searchBox = $("#search-results");

searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  const q = searchInput.value.trim();
  if (q.length < 2) { searchBox.classList.add("hidden"); return; }
  searchTimer = setTimeout(() => runSearch(q), 350);
});
document.addEventListener("click", (e) => {
  if (!e.target.closest(".search")) searchBox.classList.add("hidden");
});

async function runSearch(q) {
  try {
    const { results } = await api(`/api/search?q=${encodeURIComponent(q)}`);
    if (!results.length) {
      searchBox.innerHTML = `<div class="sr-item muted">Aucun résultat.</div>`;
    } else {
      searchBox.innerHTML = results.map((r) => `
        <div class="sr-item" data-tmdb="${r.tmdb_id}" data-type="${r.type}">
          <img loading="lazy" src="${posterSrc(r.affiche)}" alt="">
          <div class="sr-info">
            <div class="sr-title">${esc(r.titre)}</div>
            <div class="sr-meta">${r.type === "serie" ? "Série" : "Film"} · ${r.annee || "—"}
              ${r.note_tmdb ? "· ★ " + r.note_tmdb : ""}</div>
          </div>
        </div>`).join("");
    }
    searchBox.classList.remove("hidden");
  } catch (e) { toast(e.message); }
}
searchBox.addEventListener("click", (e) => {
  const item = e.target.closest(".sr-item");
  if (!item || !item.dataset.tmdb) return;
  searchBox.classList.add("hidden");
  searchInput.value = "";
  openItem(item);
});

/* ============================ SUGGESTIONS ============================== */
let sugMedia = "all";
async function loadSuggestions() {
  const wrap = $("#suggestions-rows");
  wrap.innerHTML = `<p class="muted">Chargement…</p>`;
  try {
    const { blocs } = await api(`/api/suggestions?media=${sugMedia}`);
    if (!blocs || !blocs.length) { wrap.innerHTML = `<p class="muted">Rien à afficher.</p>`; return; }
    wrap.innerHTML = blocs.map((b) => `
      <div class="row-block">
        <h3>${esc(b.titre)}</h3>
        <div class="row-scroll">${b.items.map(posterCard).join("")}</div>
      </div>`).join("");
  } catch (e) { wrap.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
}
$("[data-filter='suggestions']").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip"); if (!chip) return;
  $$("[data-filter='suggestions'] .chip").forEach((c) => c.classList.remove("active"));
  chip.classList.add("active");
  sugMedia = chip.dataset.media;
  loadSuggestions();
});
bindGrid($("#suggestions-rows"));

/* ============================ BIBLIOTHÈQUE ============================= */
async function loadLibrary() {
  const grid = $("#lib-grid");
  const params = new URLSearchParams({
    statut: $("#lib-statut").value, type: $("#lib-type").value,
    genre: $("#lib-genre").value, tri: $("#lib-tri").value,
    q: $("#lib-search").value.trim(),
  });
  grid.innerHTML = `<p class="muted">Chargement…</p>`;
  try {
    const { titres } = await api(`/api/library?${params}`);
    grid.innerHTML = titres.length
      ? titres.map(posterCard).join("")
      : `<p class="muted">Bibliothèque vide — cherche un film ou une série en haut,
         ou explore l'onglet Découverte.</p>`;
  } catch (e) { grid.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
}
["lib-statut", "lib-type", "lib-genre", "lib-tri"].forEach((id) =>
  $("#" + id).addEventListener("change", loadLibrary));
let libSearchTimer;
$("#lib-search").addEventListener("input", () => {
  clearTimeout(libSearchTimer);
  libSearchTimer = setTimeout(loadLibrary, 300);
});
$("#lib-roulette").addEventListener("click", () => openRoulette("library"));
bindGrid($("#lib-grid"));

/* -------------------------------------------------- roulette « que regarder » */
async function openRoulette(source) {
  modal.classList.remove("hidden");
  modalContent.innerHTML = `<div class="detail-body"><h2>🎲 Que regarder ?</h2>
    <p class="muted">Tirage en cours…</p></div>`;
  rollRoulette(source);
}
async function rollRoulette(source) {
  const params = new URLSearchParams({ source, count: 6 });
  if (source === "catalog") params.set("type", dec.type);
  try {
    const { results } = await api(`/api/roulette?${params}`);
    const vide = source === "library"
      ? "Ta liste « À voir » est vide — ajoute des titres d'abord."
      : "Aucun résultat.";
    const intro = source === "library"
      ? "Piochés dans ta liste « À voir » :" : "Piochés au hasard dans le catalogue :";
    modalContent.innerHTML = `<div class="detail-body"><h2>🎲 Que regarder ?</h2>
      ${(!results || !results.length) ? `<p class="muted">${vide}</p>`
        : `<p class="muted">${intro}</p><div class="grid">${results.map(posterCard).join("")}</div>
           <div class="row-inline"><button class="btn primary" data-reroll="${source}">🎲 Relancer</button></div>`}
    </div>`;
  } catch (e) {
    modalContent.innerHTML = `<div class="detail-body"><h2>🎲 Que regarder ?</h2>
      <p class="muted">${esc(e.message)}</p></div>`;
  }
}

async function fillGenres(selectId, type = "movie") {
  try {
    const { genres } = await api(`/api/genres?type=${type === "movie" ? "film" : "serie"}`);
    const sel = $("#" + selectId);
    const current = sel.value;
    sel.innerHTML = `<option value="">Tous genres</option>` +
      genres.map((g) => `<option value="${g.id}">${esc(g.name)}</option>`).join("");
    sel.value = current;
  } catch (_) { /* TMDB non configuré : on garde le menu vide */ }
}

$("#btn-manuel").addEventListener("click", openManualModal);

/* ============================ DÉCOUVERTE ============================== */
const dec = { type: "film", page: 1 };
async function loadDiscover() {
  const grid = $("#dec-grid");
  const params = new URLSearchParams({
    type: dec.type, page: dec.page, tri: $("#dec-tri").value,
    genre: $("#dec-genre").value, annee: $("#dec-annee").value, pays: $("#dec-pays").value,
  });
  grid.innerHTML = `<p class="muted">Chargement…</p>`;
  try {
    const data = await api(`/api/discover?${params}`);
    grid.innerHTML = data.results.length
      ? data.results.map(posterCard).join("")
      : `<p class="muted">Aucun résultat.</p>`;
    $("#dec-page").textContent = `Page ${data.page} / ${data.total_pages}`;
  } catch (e) { grid.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
}
$("[data-filter='decouverte']").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip"); if (!chip) return;
  $$("[data-filter='decouverte'] .chip").forEach((c) => c.classList.remove("active"));
  chip.classList.add("active");
  dec.type = chip.dataset.type; dec.page = 1;
  fillGenres("dec-genre", dec.type === "film" ? "movie" : "tv");
  loadDiscover();
});
["dec-tri", "dec-genre", "dec-annee", "dec-pays"].forEach((id) =>
  $("#" + id).addEventListener("change", () => { dec.page = 1; loadDiscover(); }));
$("#dec-prev").addEventListener("click", () => { if (dec.page > 1) { dec.page--; loadDiscover(); } });
$("#dec-next").addEventListener("click", () => { dec.page++; loadDiscover(); });
$("#dec-roulette").addEventListener("click", () => openRoulette("catalog"));
bindGrid($("#dec-grid"));

/* ============================== FUTUR ================================= */
async function loadFutur() {
  const grid = $("#futur-grid");
  grid.innerHTML = `<p class="muted">Chargement…</p>`;
  try {
    const { results } = await api(`/api/upcoming`);
    grid.innerHTML = results.map((r) => `
      <div class="poster" data-tmdb="${r.tmdb_id}" data-type="film">
        <img class="poster-img" loading="lazy" src="${posterSrc(r.affiche)}" alt="">
        ${r.note_tmdb ? `<span class="poster-note">★ ${r.note_tmdb}</span>` : ""}
        <div class="poster-body">
          <div class="poster-title">${esc(r.titre)}</div>
          <div class="poster-meta"><span>${r.date_sortie || "—"}</span></div>
          <button class="ep-btn ${r.alerte ? "vu" : ""}" data-alert="${r.tmdb_id}"
            style="margin-top:6px">${r.alerte ? "🔔 Alerte posée" : "🔔 M'alerter"}</button>
        </div>
      </div>`).join("");
  } catch (e) { grid.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
}
$("#futur-grid").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-alert]");
  if (btn) {
    e.stopPropagation();
    try {
      await api("/api/alerts", { method: "POST",
        body: { tmdb_id: Number(btn.dataset.alert), type: "film", canal: "cine" } });
      toast("Alerte posée — tu la retrouveras dans ta bibliothèque");
      loadFutur();
    } catch (err) { toast(err.message); }
    return;
  }
  const card = e.target.closest(".poster");
  if (card) openItem(card);
});

/* ============================== LISTES =============================== */
async function loadListes() {
  $("#liste-detail").classList.add("hidden");
  $("#listes-grid").classList.remove("hidden");
  const grid = $("#listes-grid");
  try {
    const { listes } = await api("/api/lists");
    grid.innerHTML = listes.map((l) => `
      <div class="list-card" data-list="${l.id}">
        <div class="lc-name ${l.systeme_flag ? "lc-sys" : ""}">${esc(l.nom)}</div>
        <div class="lc-count">${l.nb} titre(s)${l.systeme_flag ? " · liste système" : ""}</div>
      </div>`).join("");
  } catch (e) { grid.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
}
$("#listes-grid").addEventListener("click", (e) => {
  const card = e.target.closest("[data-list]");
  if (card) openListe(Number(card.dataset.list));
});
$("#liste-back").addEventListener("click", loadListes);

async function openListe(id) {
  try {
    const { liste, titres } = await api(`/api/lists/${id}`);
    $("#listes-grid").classList.add("hidden");
    $("#liste-detail").classList.remove("hidden");
    $("#liste-detail-nom").textContent = liste.nom;
    const grid = $("#liste-detail-grid");
    grid.innerHTML = titres.length ? titres.map(posterCard).join("")
      : `<p class="muted">Liste vide. Ouvre une fiche et « Ajouter à une liste ».</p>`;
    grid.onclick = (e) => { const c = e.target.closest(".poster"); if (c) openItem(c); };
  } catch (e) { toast(e.message); }
}

$("#btn-liste-new").addEventListener("click", async () => {
  const nom = prompt("Nom de la nouvelle liste :");
  if (!nom) return;
  try { await api("/api/lists", { method: "POST", body: { nom } }); loadListes(); }
  catch (e) { toast(e.message); }
});
$("#btn-liste-import").addEventListener("click", openImportListModal);
$("#btn-liste-presets").addEventListener("click", openPresetsModal);

async function openPresetsModal() {
  modal.classList.remove("hidden");
  modalContent.innerHTML = `<div class="detail-body"><h2>🎬 Listes prêtes</h2>
    <p class="muted">Choisis une saga : ses titres sont ajoutés à ta bibliothèque
      (« À voir ») et rangés dans une nouvelle liste, dans l'ordre.</p>
    <div id="presets-list" class="muted">Chargement…</div></div>`;
  try {
    const { presets } = await api("/api/lists/presets");
    $("#presets-list").innerHTML = presets.map((p) => `
      <div class="preset-row">
        <span>${esc(p.nom)} <span class="muted">(${p.nb} titres)</span></span>
        <button class="btn small primary" data-preset="${p.cle}">Importer</button>
      </div>`).join("");
  } catch (e) { $("#presets-list").textContent = e.message; }
}

/* ============================ STATISTIQUES =========================== */
async function loadStats() {
  const wrap = $("#stats-content");
  wrap.innerHTML = `<p class="muted">Calcul…</p>`;
  try {
    const s = await api("/api/stats");
    const maxG = Math.max(1, ...s.genres.map((g) => g.n));
    wrap.innerHTML = `
      <div class="stat-cards">
        <div class="stat-card">
          <div class="stat-value">${s.temps_total.texte}</div>
          <div class="stat-label">Temps total regardé</div>
          <div class="stat-sub">≈ ${s.temps_total.converti}</div>
        </div>
        <div class="stat-card"><div class="stat-value">${s.nb_films}</div>
          <div class="stat-label">Films vus</div></div>
        <div class="stat-card"><div class="stat-value">${s.nb_series}</div>
          <div class="stat-label">Séries suivies</div></div>
        <div class="stat-card"><div class="stat-value">${s.nb_episodes}</div>
          <div class="stat-label">Épisodes vus</div></div>
      </div>
      ${s.genres.length ? `<h3 class="sub-title">Genres les plus vus</h3>
        ${s.genres.map((g) => `<div class="bar-row">
          <span class="bar-label">${esc(g.nom)}</span>
          <span class="bar-track"><span class="bar-fill" style="width:${g.n / maxG * 100}%"></span></span>
          <span class="bar-num">${g.n}</span></div>`).join("")}` : ""}
      ${s.series.length ? `<h3 class="sub-title">Temps par série</h3>
        ${s.series.map((se) => `<div class="bar-row">
          <span class="bar-label">${esc(se.titre)}</span>
          <span class="bar-track"><span class="bar-fill"
            style="width:${se.minutes / s.series[0].minutes * 100}%"></span></span>
          <span class="bar-num">${se.duree.texte}</span></div>`).join("")}` : ""}`;
  } catch (e) { wrap.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
}

/* ============================ PARAMÈTRES ============================= */
async function loadSettings() {
  try {
    const s = await api("/api/settings");
    $("#set-region").value = s.tmdb_region || "FR";
    $("#tmdb-status").textContent = s.tmdb_configuree ? "✅ Clé configurée" : "⚠️ Non configurée";
    $("#set-cf-enabled").checked = !!s.cf_sso_enabled;
    $("#set-cf-email").value = s.cf_access_email || "";
    $("#set-discord-enabled").checked = !!s.notif_discord_enabled;
    $("#set-botpanel-url").value = s.botpanel_url || "";
    $("#set-slug-episode").value = s.botpanel_slug_episode || "";
    $("#set-slug-cine").value = s.botpanel_slug_cine || "";
    $("#set-slug-streaming").value = s.botpanel_slug_streaming || "";
    $("#set-ntfy-enabled").checked = !!s.notif_ntfy_enabled;
    $("#set-ntfy-url").value = s.ntfy_url || "https://ntfy.sh";
    $("#set-ntfy-topic").value = s.ntfy_topic || "";
  } catch (_) { /* ignore */ }
}
$("#btn-save-notif").addEventListener("click", async () => {
  try {
    await api("/api/settings", { method: "POST", body: {
      notif_discord_enabled: $("#set-discord-enabled").checked,
      botpanel_url: $("#set-botpanel-url").value.trim(),
      botpanel_slug_episode: $("#set-slug-episode").value.trim(),
      botpanel_slug_cine: $("#set-slug-cine").value.trim(),
      botpanel_slug_streaming: $("#set-slug-streaming").value.trim(),
      notif_ntfy_enabled: $("#set-ntfy-enabled").checked,
      ntfy_url: $("#set-ntfy-url").value.trim(),
      ntfy_topic: $("#set-ntfy-topic").value.trim(),
    } });
    $("#notif-status").textContent = "✅ Enregistré."; toast("Notifications enregistrées");
  } catch (e) { $("#notif-status").textContent = "❌ " + e.message; }
});
$("#btn-test-notif").addEventListener("click", async () => {
  $("#notif-status").textContent = "Envoi du test…";
  try {
    const r = await api("/api/settings/notif-test", { method: "POST" });
    $("#notif-status").textContent = "✅ Test envoyé sur : " + r.canaux.join(", ");
  } catch (e) { $("#notif-status").textContent = "❌ " + e.message; }
});
$("#btn-save-cf").addEventListener("click", async () => {
  try {
    await api("/api/settings", { method: "POST", body: {
      cf_sso_enabled: $("#set-cf-enabled").checked,
      cf_access_email: $("#set-cf-email").value.trim(),
    } });
    $("#cf-status").textContent = "✅ Enregistré.";
    toast("Réglage de connexion enregistré");
  } catch (e) { $("#cf-status").textContent = "❌ " + e.message; }
});
$("#btn-save-tmdb").addEventListener("click", async () => {
  const body = { tmdb_region: $("#set-region").value };
  if ($("#set-tmdb-key").value.trim()) body.tmdb_api_key = $("#set-tmdb-key").value.trim();
  try {
    await api("/api/settings", { method: "POST", body });
    $("#set-tmdb-key").value = "";
    toast("Réglages enregistrés"); loadSettings();
  } catch (e) { toast(e.message); }
});
$("#btn-test-tmdb").addEventListener("click", async () => {
  $("#tmdb-status").textContent = "Test en cours…";
  try { await api("/api/settings/tmdb-test", { method: "POST" });
    $("#tmdb-status").textContent = "✅ La clé fonctionne."; }
  catch (e) { $("#tmdb-status").textContent = "❌ " + e.message; }
});
$("#btn-save-password").addEventListener("click", async () => {
  const password = $("#set-password").value;
  try {
    await api("/api/settings/password", { method: "POST", body: { password } });
    $("#set-password").value = "";
    $("#password-status").textContent = "✅ Mot de passe changé.";
  } catch (e) { $("#password-status").textContent = "❌ " + e.message; }
});
$("#btn-import").addEventListener("click", () => $("#import-file").click());
$("#import-file").addEventListener("change", async (e) => {
  const file = e.target.files[0]; if (!file) return;
  try {
    const dump = JSON.parse(await file.text());
    await api("/api/import", { method: "POST", body: dump });
    $("#import-status").textContent = "✅ Import réussi.";
    toast("Données importées");
  } catch (err) { $("#import-status").textContent = "❌ " + err.message; }
});

/* ========================= FICHE DÉTAILLÉE (modale) ==================== */
const modal = $("#modal");
const modalContent = $("#modal-content");
function closeModal() { modal.classList.add("hidden"); modalContent.innerHTML = ""; }
modal.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

async function openDetail(id) {
  modal.classList.remove("hidden");
  modalContent.innerHTML = `<div class="detail-body"><p class="muted">Chargement…</p></div>`;
  try {
    const data = await api(`/api/title/${id}`);
    modalContent.innerHTML = data.titre.type === "film"
      ? renderFilm(data) : renderSerie(data);
  } catch (e) { modalContent.innerHTML = `<div class="detail-body"><p class="muted">${esc(e.message)}</p></div>`; }
}

function hero(t) {
  const genres = (t.genres || []).map((g) => `<span class="tag">${esc(g)}</span>`).join("");
  const note = t.note_tmdb ? `<span class="tag">★ ${t.note_tmdb}</span>` : "";
  const trailer = t.bande_annonce
    ? `<a class="btn small" target="_blank" rel="noopener"
         href="https://www.youtube.com/watch?v=${t.bande_annonce}">▶ Bande-annonce</a>` : "";
  return `<div class="detail-hero" style="background-image:url('${t.fond || ""}')">
    <img class="detail-poster" src="${posterSrc(t.affiche)}" alt="">
    <div class="detail-info">
      <h2>${esc(t.titre)}</h2>
      <div class="detail-tags"><span class="tag">${t.type === "serie" ? "Série" : "Film"}</span>
        <span class="tag">${t.annee || "—"}</span>${note}${genres}</div>
      <div class="detail-actions" data-id="${t.id}">
        ${["en_cours", "a_voir", "vu", "abandonne"].map((s) =>
          `<button class="btn small ${t.statut === s ? "primary" : ""}"
             data-statut="${s}">${STATUTS[s]}</button>`).join("")}
        <button class="btn small ${t.favori ? "primary" : ""}" data-fav>♥ Favori</button>
        <button class="btn small" data-addlist>+ Liste</button>
        ${trailer}
        <button class="btn small danger" data-del>Supprimer</button>
      </div>
    </div></div>`;
}

function renderFilm(data) {
  const t = data.titre;
  const providers = (t.plateformes || []).length
    ? `<h3 class="sub-title">Où le regarder</h3><div class="providers">
       ${t.plateformes.map((p) => `<img title="${esc(p.nom)}" src="${p.logo}" alt="${esc(p.nom)}">`).join("")}</div>`
    : "";
  const watches = data.visionnages || [];
  return hero(t) + `<div class="detail-body" data-id="${t.id}">
    <p class="detail-resume">${esc(t.resume) || "Pas de résumé."}</p>
    ${t.duree ? `<p class="muted">Durée : ${t.duree} min · Vu ${watches.length} fois</p>` : ""}
    ${providers}
    <h3 class="sub-title">Mes visionnages</h3>
    <div class="row-inline">
      <input type="date" class="input small-input" id="watch-date">
      <button class="btn small primary" data-addwatch>+ Ajouter un visionnage</button>
    </div>
    <ul class="watch-list">${watches.map((w) => `<li><span>${w.date}</span>
      <button class="ep-btn" data-delwatch="${w.id}">✕</button></li>`).join("")
      || `<li class="muted">Aucun visionnage enregistré.</li>`}</ul>
    ${castingBlock(t.casting)}
  </div>`;
}

/* Grille du casting : clic sur un acteur → sa fiche (filmographie + infos). */
function castingBlock(cast) {
  if (!cast || !cast.length) return "";
  return `<h3 class="sub-title">Casting</h3><div class="cast-row">${cast.map((c) => `
    <div class="cast" data-person="${c.id}">
      <img loading="lazy" src="${posterSrc(c.photo)}" alt="">
      <div class="cast-name">${esc(c.nom)}</div>
      ${c.personnage ? `<div class="cast-role">${esc(c.personnage)}</div>` : ""}
    </div>`).join("")}</div>`;
}

async function openPerson(id) {
  modal.classList.remove("hidden");
  modalContent.innerHTML = `<div class="detail-body"><p class="muted">Chargement…</p></div>`;
  try {
    const p = await api(`/api/person/${id}`);
    modalContent.innerHTML = renderPerson(p);
  } catch (e) {
    modalContent.innerHTML = `<div class="detail-body"><p class="muted">${esc(e.message)}</p></div>`;
  }
}

function renderPerson(p) {
  const infos = [
    p.metier, p.naissance ? `Né(e) le ${p.naissance}` : "", p.lieu,
  ].filter(Boolean).map((t) => `<span class="tag">${esc(t)}</span>`).join("");
  const bio = p.bio ? `<p class="detail-resume">${esc(p.bio.slice(0, 700))}${p.bio.length > 700 ? "…" : ""}</p>` : "";
  return `<div class="detail-hero">
    <img class="detail-poster" src="${posterSrc(p.photo)}" alt="">
    <div class="detail-info"><h2>${esc(p.nom)}</h2><div class="detail-tags">${infos}</div></div>
  </div>
  <div class="detail-body">${bio}
    <h3 class="sub-title">Filmographie</h3>
    <div class="grid">${p.films.map(posterCard).join("")}</div>
  </div>`;
}

function renderSerie(data) {
  const t = data.titre;
  const next = data.prochain_episode;
  const providers = (t.plateformes || []).length
    ? `<h3 class="sub-title">Où la regarder</h3><div class="providers">
       ${t.plateformes.map((p) => `<img title="${esc(p.nom)}" src="${p.logo}" alt="${esc(p.nom)}">`).join("")}</div>`
    : "";
  const seasons = (data.saisons || []).map((s) => `
    <div class="season" data-season="${s.numero}">
      <div class="season-head">
        <span><span class="chevron">▸</span> <span class="season-title">Saison ${s.numero}</span></span>
        <span class="season-prog">${s.vus}/${s.total} vus
          <button class="ep-btn" data-markseason="${s.numero}" style="margin-left:8px">Tout marquer</button></span>
      </div>
      <div class="season-body">${s.episodes.map(episodeRow).join("")}</div>
    </div>`).join("");
  return hero(t) + `<div class="detail-body" data-id="${t.id}">
    <p class="detail-resume">${esc(t.resume) || "Pas de résumé."}</p>
    ${next ? `<p class="muted">Prochain épisode : S${next.saison}E${next.numero}
       « ${esc(next.nom || "")} » le ${next.date_diff}</p>` : ""}
    ${providers}
    <div class="row-inline"><button class="btn small" data-markseries>✓ Marquer la série vue</button></div>
    <h3 class="sub-title">Saisons &amp; épisodes</h3>
    ${seasons || `<p class="muted">Épisodes indisponibles.</p>`}
    ${castingBlock(t.casting)}
  </div>`;
}

function episodeRow(e) {
  return `<div class="episode">
    <img loading="lazy" src="${posterSrc(e.image)}" alt="">
    <div class="ep-info">
      <div class="ep-title">${e.numero}. ${esc(e.nom || "Épisode " + e.numero)}</div>
      <div class="ep-meta">${e.date_diff || ""}${e.duree ? " · " + e.duree + " min" : ""}
        ${e.nb_vues > 1 ? " · vu ×" + e.nb_vues : ""}</div>
      <div class="ep-resume">${esc(e.resume)}</div>
    </div>
    <div class="ep-check">
      <button class="ep-btn ${e.vu ? "vu" : ""}" data-ep="${e.id}">${e.vu ? "✓ Revu" : "Vu"}</button>
    </div></div>`;
}

/* Actions dans la fiche (délégation d'événements sur la modale). */
modalContent.addEventListener("click", async (e) => {
  // Interactions transverses : acteur, relance roulette, import preset, affiche.
  const personEl = e.target.closest("[data-person]");
  if (personEl) return openPerson(Number(personEl.dataset.person));
  const rerollEl = e.target.closest("[data-reroll]");
  if (rerollEl) return rollRoulette(rerollEl.dataset.reroll);
  const presetEl = e.target.closest("[data-preset]");
  if (presetEl) {
    presetEl.disabled = true; presetEl.textContent = "Import…";
    try {
      const r = await api("/api/lists/import-preset",
        { method: "POST", body: { cle: presetEl.dataset.preset } });
      toast(`${r.ajoutes} titre(s) importé(s)`); closeModal();
      if ($("#page-listes").classList.contains("active")) loadListes();
    } catch (err) { toast(err.message); presetEl.disabled = false; presetEl.textContent = "Importer"; }
    return;
  }
  const posterEl = e.target.closest(".poster");
  if (posterEl) return openItem(posterEl);

  const idEl = e.target.closest("[data-id]");
  const id = idEl && Number(idEl.dataset.id);
  try {
    if (e.target.closest("[data-statut]")) {
      await api(`/api/library/${id}`, { method: "PATCH",
        body: { statut: e.target.closest("[data-statut]").dataset.statut } });
      openDetail(id); refreshAll();
    } else if (e.target.closest("[data-fav]")) {
      const on = !e.target.closest("[data-fav]").classList.contains("primary");
      await api(`/api/library/${id}`, { method: "PATCH", body: { favori: on } });
      openDetail(id);
    } else if (e.target.closest("[data-del]")) {
      if (confirm("Supprimer ce titre de la bibliothèque ?")) {
        await api(`/api/library/${id}`, { method: "DELETE" });
        closeModal(); refreshAll(); toast("Titre supprimé");
      }
    } else if (e.target.closest("[data-addlist]")) {
      addToListPrompt(id);
    } else if (e.target.closest("[data-addwatch]")) {
      await api(`/api/title/${id}/watch`, { method: "POST",
        body: { date: $("#watch-date").value || undefined } });
      openDetail(id); refreshAll();
    } else if (e.target.closest("[data-delwatch]")) {
      await api(`/api/watch/${e.target.closest("[data-delwatch]").dataset.delwatch}`,
        { method: "DELETE" }); openDetail(id);
    } else if (e.target.closest("[data-ep]")) {
      await api(`/api/episode/${e.target.closest("[data-ep]").dataset.ep}/toggle`,
        { method: "POST" }); openDetail(id);
    } else if (e.target.closest("[data-markseason]")) {
      await api(`/api/title/${id}/season/${e.target.closest("[data-markseason]").dataset.markseason}/mark`,
        { method: "POST", body: { vu: true } }); openDetail(id);
    } else if (e.target.closest("[data-markseries]")) {
      await api(`/api/title/${id}/mark`, { method: "POST", body: { vu: true } });
      openDetail(id); refreshAll();
    } else {
      const head = e.target.closest(".season-head");
      if (head) head.parentElement.classList.toggle("open");
    }
  } catch (err) { toast(err.message); }
});

async function addToListPrompt(titreId) {
  try {
    const { listes } = await api("/api/lists");
    const choix = listes.map((l, i) => `${i + 1}. ${l.nom}`).join("\n");
    const n = prompt("Ajouter à quelle liste ?\n" + choix);
    const idx = Number(n) - 1;
    if (isNaN(idx) || !listes[idx]) return;
    await api(`/api/lists/${listes[idx].id}/items`, { method: "POST", body: { titre_id: titreId } });
    toast("Ajouté à « " + listes[idx].nom + " »");
  } catch (e) { toast(e.message); }
}

/* ------------------------------------------- modales simples (ajout/import) */
function openManualModal() {
  modal.classList.remove("hidden");
  modalContent.innerHTML = `<div class="detail-body">
    <h2>Ajout manuel</h2>
    <p class="muted">Pour un titre absent de TMDB.</p>
    <input class="input" id="m-titre" placeholder="Titre">
    <div class="row-inline">
      <select class="select" id="m-type"><option value="film">Film</option>
        <option value="serie">Série</option></select>
      <input class="input small-input" id="m-annee" type="number" placeholder="Année">
      <input class="input small-input" id="m-duree" type="number" placeholder="Durée (min)">
    </div>
    <textarea class="input" id="m-resume" placeholder="Résumé" rows="3"></textarea>
    <button class="btn primary" id="m-save">Ajouter</button></div>`;
  $("#m-save").addEventListener("click", async () => {
    const body = { titre: $("#m-titre").value.trim(), type: $("#m-type").value,
      annee: Number($("#m-annee").value) || null, duree: Number($("#m-duree").value) || null,
      resume: $("#m-resume").value.trim() };
    if (!body.titre) return toast("Titre requis");
    try { await api("/api/library/manual", { method: "POST", body });
      closeModal(); toast("Ajouté"); loadLibrary(); }
    catch (e) { toast(e.message); }
  });
}

function openImportListModal() {
  modal.classList.remove("hidden");
  modalContent.innerHTML = `<div class="detail-body">
    <h2>Importer une liste</h2>
    <p class="muted">Colle une liste de titres au format JSON, par exemple celle que
      je te génère (ex. ordre Marvel) :
      <code>[{"tmdb_id":1726,"type":"film"}, ...]</code></p>
    <input class="input" id="il-nom" placeholder="Nom de la liste (ex. Ordre Marvel)">
    <textarea class="input" id="il-json" rows="7"
      placeholder='[{"tmdb_id":1726,"type":"film"}]'></textarea>
    <button class="btn primary" id="il-save">Importer</button>
    <span class="muted" id="il-status"></span></div>`;
  $("#il-save").addEventListener("click", async () => {
    let items;
    try { items = JSON.parse($("#il-json").value); }
    catch (_) { $("#il-status").textContent = "JSON invalide."; return; }
    try {
      const r = await api("/api/lists/import", { method: "POST",
        body: { nom: $("#il-nom").value.trim() || "Liste importée", items } });
      $("#il-status").textContent = `✅ ${r.ajoutes} titre(s) importé(s).`;
      loadListes();
    } catch (e) { $("#il-status").textContent = "❌ " + e.message; }
  });
}

/* ------------------------------------------------------- chargeurs par page */
const LOADERS = {
  suggestions: loadSuggestions,
  bibliotheque: () => { fillGenres("lib-genre"); loadLibrary(); },
  decouverte: () => { fillGenres("dec-genre"); loadDiscover(); },
  futur: loadFutur,
  listes: loadListes,
  profil: loadStats,
  parametres: loadSettings,
};

/* Rafraîchit les vues potentiellement impactées par une modif. */
function refreshAll() {
  if ($("#page-bibliotheque").classList.contains("active")) loadLibrary();
  if ($("#page-suggestions").classList.contains("active")) loadSuggestions();
}

/* Service worker (PWA : app installable + démarrage rapide). */
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () =>
    navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

/* Au démarrage : onglet Suggestions. */
loadSuggestions();
