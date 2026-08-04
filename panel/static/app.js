/* =========================================================================
   cinéthèque — logique de l'interface (JavaScript vanilla, sans dépendance).
   Organisation : utilitaires → navigation → recherche → chaque page →
   fiche détaillée (modale). Le back-end expose tout via /api/*.
   ========================================================================= */
"use strict";

/* ----------------------------------------------------------- utilitaires */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/* Icônes SVG en ligne (au thème via currentColor) — remplacent les émojis. */
const SVG = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"';
const ICONS = {
  bell: `<svg class="ic" ${SVG}><path d="M6.5 9.5a5.5 5.5 0 0 1 11 0c0 4.5 2 5.5 2 5.5H4.5s2-1 2-5.5z"/><path d="M10 19a2 2 0 0 0 4 0"/></svg>`,
  dice: `<svg class="ic" ${SVG}><rect x="4" y="4" width="16" height="16" rx="3.5"/><circle cx="8.5" cy="8.5" r="1" fill="currentColor" stroke="none"/><circle cx="15.5" cy="8.5" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="8.5" cy="15.5" r="1" fill="currentColor" stroke="none"/><circle cx="15.5" cy="15.5" r="1" fill="currentColor" stroke="none"/></svg>`,
  film: `<svg class="ic" ${SVG}><rect x="3" y="4.5" width="18" height="15" rx="2"/><path d="M8 4.5v15M16 4.5v15M3 9.5h5M16 9.5h5M3 14.5h5M16 14.5h5"/></svg>`,
};

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

const STATUTS = { vu: "Vu", a_voir: "À voir", en_cours: "En cours" };
const posterSrc = (u) => u || "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E";

/* Couleur par genre — un peu de vie dans les fiches et les cartes. */
const GENRE_COLORS = {
  "Action": "#e85c47", "Aventure": "#e8a24a", "Comédie": "#f2c14e",
  "Drame": "#a78bfa", "Science-Fiction": "#4fc3a1", "Horreur": "#c0392b",
  "Thriller": "#e87c47", "Romance": "#e86ea4", "Animation": "#5aa9e6",
  "Fantastique": "#9b6dff", "Familial": "#5fce8f", "Crime": "#d1495b",
  "Mystère": "#7c6df2", "Guerre": "#b08968", "Histoire": "#c9a26b",
  "Documentaire": "#4fc3a1", "Musique": "#e86ea4", "Western": "#c98a3b",
};
function genreTag(name) {
  const c = GENRE_COLORS[name];
  const style = c ? ` style="color:${c};border-color:${c}66;background:${c}22"` : "";
  return `<span class="tag"${style}>${esc(name)}</span>`;
}

/* Carte d'affiche réutilisée partout (bibliothèque, carrousels, découverte). */
function posterCard(item) {
  // Note TMDB (communauté, sur 10) : à droite de la ligne d'infos, pour ne pas
  // chevaucher le badge de statut sur les cartes étroites.
  const note = item.note_tmdb ? `<span class="meta-note">★ ${item.note_tmdb}</span>` : "";
  const vues = item.nb_vues > 1 ? `<span class="meta-vues">↻ ×${item.nb_vues}</span>` : "";
  const statut = item.statut
    ? `<span class="poster-badge badge-${item.statut}">${STATUTS[item.statut] || ""}</span>` : "";
  const fav = item.favori ? `<span class="poster-fav">♥</span>` : "";
  const annee = item.annee || "";
  const type = item.type === "serie" ? "Série" : "Film";
  // Genre principal coloré (quand connu) — un peu de couleur dans la grille.
  let genre0 = "";
  if (item.genres && item.genres.length) {
    const g = item.genres[0], c = GENRE_COLORS[g];
    const st = c ? ` style="color:${c};border-color:${c}66;background:${c}22"` : "";
    genre0 = `<span class="poster-genre"${st}>${esc(g)}</span>`;
  }
  // Barre de progression pour les séries (épisodes vus / total) + où j'en suis.
  let prog = "";
  if (item.total_ep) {
    const pct = Math.round((item.vus_ep || 0) / item.total_ep * 100);
    // Position courante : prochain épisode non vu (sinon série terminée).
    // Compact (« ▸ S2 E5 ») pour que la saison/épisode reste toujours lisible.
    let pos = "";
    if (item.next_saison) {
      const started = (item.vus_ep || 0) > 0;
      pos = `<span class="poster-pos" title="${started ? "Reprendre à" : "Commencer par"} la saison ${item.next_saison}, épisode ${item.next_numero}">` +
        `${started ? "▸" : "○"} S${item.next_saison} E${item.next_numero}</span>`;
    } else if ((item.vus_ep || 0) >= item.total_ep) {
      pos = `<span class="poster-pos done">✓ Terminée</span>`;
    }
    prog = `<div class="poster-progline">${pos}<span class="poster-epcount">${item.vus_ep || 0}/${item.total_ep}</span></div>
      <div class="poster-prog" title="${item.vus_ep || 0}/${item.total_ep} épisodes">
        <span style="width:${pct}%"></span></div>`;
  }
  return `<div class="poster" data-id="${item.id || ""}" data-tmdb="${item.tmdb_id || ""}"
       data-type="${item.type || ""}" data-localid="${item.local_id || ""}"
       data-statut="${item.statut || ""}" data-nbvues="${item.nb_vues || 0}"
       data-nexts="${item.next_saison || ""}" data-nexte="${item.next_numero || ""}">
    <img class="poster-img" loading="lazy" decoding="async" src="${posterSrc(item.affiche)}" alt="">
    ${statut}${fav}
    <div class="poster-body">
      <div class="poster-title">${esc(item.titre)}</div>
      <div class="poster-meta"><span>${type}${annee ? " · " + annee : ""}</span><span class="meta-right">${vues}${note}</span></div>
      ${genre0}${prog}
    </div>
  </div>`;
}

/* Clic sur un titre → petit menu 3 options (À voir / Déjà vu / Plus d'infos). */
function openItem(el) {
  const tmdb = Number(el.dataset.tmdb) || null, type = el.dataset.type || null;
  const localid = Number(el.dataset.id || el.dataset.localid) || null;
  if (!localid && !(tmdb && type)) return;
  const titleEl = el.querySelector(".poster-title, .sr-title");
  const imgEl = el.querySelector("img");
  openQuickMenu({ el, tmdb, type, localid,
    statut: el.dataset.statut || "", nbvues: Number(el.dataset.nbvues || 0),
    nextS: el.dataset.nexts || "", nextE: el.dataset.nexte || "",
    titre: titleEl ? titleEl.textContent.trim() : "", affiche: imgEl ? imgEl.src : "" });
}

/* --------------------------------------------- menu rapide 3 options (clic) */
const quickMenu = $("#quick-menu");
let qmContext = null;
function closeQuickMenu() { quickMenu.classList.add("hidden"); qmContext = null; }

function openQuickMenu(ctx) {
  qmContext = ctx;
  $("#qm-poster").src = ctx.affiche || posterSrc(null);
  $("#qm-title").textContent = ctx.titre || "";
  const inAvoir = ctx.statut === "a_voir";
  const enCours = ctx.statut === "en_cours";
  const seen = ctx.statut === "vu" || ctx.nbvues > 0;
  const avoirBtn = $("#quick-menu [data-qm='a_voir']");
  avoirBtn.textContent = inAvoir ? "✓ Dans « À voir »" : "＋ À voir";
  avoirBtn.classList.toggle("current", inAvoir);
  const vuBtn = $("#quick-menu [data-qm='vu']");
  if (enCours && ctx.type === "serie") {
    // Série déjà commencée : on montre où reprendre, pas « Déjà vu ».
    vuBtn.textContent = ctx.nextS ? `▸ Reprendre S${ctx.nextS} E${ctx.nextE}` : "▸ En cours";
    vuBtn.classList.add("current");
  } else {
    vuBtn.textContent = seen ? ("✓ Déjà vu" + (ctx.nbvues > 1 ? ` ×${ctx.nbvues}` : "")) : "Déjà vu";
    vuBtn.classList.toggle("current", seen);
  }
  quickMenu.classList.remove("hidden");
}

quickMenu.addEventListener("click", async (e) => {
  if (e.target.closest("[data-qm-close]")) return closeQuickMenu();
  const btn = e.target.closest("[data-qm]");
  if (!btn || !qmContext) return;
  const { el, tmdb, type, localid } = qmContext;
  const act = btn.dataset.qm;
  if (act === "infos") { closeQuickMenu(); return localid ? openDetail(localid) : openPreview(tmdb, type); }
  // Série + « Déjà vu » : on ouvre la fiche directement sur les Saisons, pour
  // marquer saison par saison (au lieu de tout marquer d'un coup).
  if (act === "vu" && type === "serie") {
    closeQuickMenu();
    return localid ? openDetail(localid, { seasons: true })
                   : openPreview(tmdb, type, { seasons: true });
  }
  try {
    let newId = localid;
    if (act === "vu") {
      if (localid) await api(`/api/title/${localid}/watch`, { method: "POST", body: {} });
      else newId = (await api("/api/library", { method: "POST", body: { tmdb_id: tmdb, type, statut: "vu" } })).id;
    } else {
      if (localid) await api(`/api/library/${localid}`, { method: "PATCH", body: { statut: "a_voir" } });
      else newId = (await api("/api/library", { method: "POST", body: { tmdb_id: tmdb, type, statut: "a_voir" } })).id;
    }
    if (el) {  // met à jour la carte source (statut + compteur) sans tout recharger
      el.dataset.localid = newId || "";
      el.dataset.statut = act === "vu" ? "vu" : "a_voir";
      if (act === "vu") el.dataset.nbvues = String(Number(el.dataset.nbvues || 0) + 1);
      el.classList.add("poster-added");
    }
    toast(act === "vu" ? "Marqué comme vu ✓" : "Ajouté à « À voir »");
    closeQuickMenu();
    if ($("#page-bibliotheque").classList.contains("active")) loadLibrary();
  } catch (err) { toast(err.message); }
});

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
  // Ne recharge que les pages « vivantes » ; les autres sont mises en cache
  // après la 1re visite (moins de chargements, notamment les Suggestions).
  if (LOADERS[name] && (RELOAD_ALWAYS.has(name) || !_tabLoaded.has(name))) {
    _tabLoaded.add(name);
    LOADERS[name]();
  }
}
const RELOAD_ALWAYS = new Set(["bibliotheque", "listes", "profil"]);
const _tabLoaded = new Set();

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
        <div class="row-wrap">
          <button class="row-arrow left" aria-label="Précédent">‹</button>
          <div class="row-scroll">${b.items.map(posterCard).join("")}</div>
          <button class="row-arrow right" aria-label="Suivant">›</button>
        </div>
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
$("#sug-refresh").addEventListener("click", async (e) => {
  const b = e.currentTarget; b.disabled = true; b.classList.add("spin");
  try { await loadSuggestions(); } finally { b.disabled = false; b.classList.remove("spin"); }
});
bindGrid($("#suggestions-rows"));

/* Carrousels : flèches gauche/droite + défilement à la molette. */
$("#suggestions-rows").addEventListener("click", (e) => {
  const arrow = e.target.closest(".row-arrow");
  if (!arrow) return;
  const scroll = arrow.parentElement.querySelector(".row-scroll");
  const dx = scroll.clientWidth * 0.85;
  scroll.scrollBy({ left: arrow.classList.contains("left") ? -dx : dx, behavior: "smooth" });
});
$("#suggestions-rows").addEventListener("wheel", (e) => {
  const scroll = e.target.closest(".row-scroll");
  if (!scroll) return;
  if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
    scroll.scrollLeft += e.deltaY;
    e.preventDefault();
  }
}, { passive: false });

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
  modal.classList.remove("hidden"); modal.classList.remove("full");
  modalContent.innerHTML = `<div class="detail-body"><h2>${ICONS.dice}Que regarder ?</h2>
    <p class="muted">Tirage en cours…</p></div>`;
  rollRoulette(source);
}
async function rollRoulette(source) {
  const params = new URLSearchParams({ source, count: source === "catalog" ? 12 : 10 });
  if (source === "catalog") params.set("type", dec.type);
  try {
    const { results } = await api(`/api/roulette?${params}`);
    const vide = source === "library"
      ? "Ta liste « À voir » est vide — ajoute des titres d'abord."
      : "Aucun résultat.";
    const intro = source === "library"
      ? "Piochés dans ta liste « À voir » :" : "Piochés au hasard dans le catalogue :";
    modalContent.innerHTML = `<div class="detail-body"><h2>${ICONS.dice}Que regarder ?</h2>
      ${(!results || !results.length) ? `<p class="muted">${vide}</p>`
        : `<p class="muted">${intro}</p><div class="grid">${results.map(posterCard).join("")}</div>
           <div class="row-inline"><button class="btn primary" data-reroll="${source}">${ICONS.dice}Relancer</button></div>`}
    </div>`;
  } catch (e) {
    modalContent.innerHTML = `<div class="detail-body"><h2>${ICONS.dice}Que regarder ?</h2>
      <p class="muted">${esc(e.message)}</p></div>`;
  }
}

const _genresFilled = new Set();
async function fillGenres(selectId, type = "movie") {
  const key = selectId + ":" + type;
  if (_genresFilled.has(key)) return;  // évite de recharger les genres à chaque visite
  try {
    const { genres } = await api(`/api/genres?type=${type === "movie" ? "film" : "serie"}`);
    const sel = $("#" + selectId);
    const current = sel.value;
    sel.innerHTML = `<option value="">Tous genres</option>` +
      genres.map((g) => `<option value="${g.id}">${esc(g.name)}</option>`).join("");
    sel.value = current;
    _genresFilled.add(key);
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
            style="margin-top:6px">${ICONS.bell}${r.alerte ? "Alerte posée" : "M'alerter"}</button>
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
  modal.classList.remove("hidden"); modal.classList.remove("full");
  modalContent.innerHTML = `<div class="detail-body"><h2>${ICONS.film}Listes prêtes</h2>
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
  loadVersion();
}
async function loadVersion() {
  try {
    const v = await api("/api/version");
    $("#app-version").textContent = v.version
      ? `${v.version}${v.message ? " — " + v.message : ""}` : "inconnue";
  } catch (_) { $("#app-version").textContent = "inconnue"; }
}
$("#btn-update").addEventListener("click", async () => {
  if (!confirm("Mettre à jour le site maintenant ? Il redémarrera quelques secondes.")) return;
  $("#update-status").textContent = "Mise à jour en cours…";
  $("#btn-update").disabled = true;
  try {
    const r = await api("/api/update", { method: "POST" });
    $("#update-status").textContent = "✅ " + r.message + " Rechargement automatique…";
    setTimeout(() => location.reload(), 9000);
  } catch (e) {
    $("#update-status").textContent = "❌ " + e.message;
    $("#btn-update").disabled = false;
  }
});
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
$("#btn-reset").addEventListener("click", async () => {
  if (!confirm("Effacer TOUTE ta bibliothèque ? Cette action est irréversible.")) return;
  if (!confirm("Confirmer une dernière fois : tout supprimer ?")) return;
  $("#reset-status").textContent = "Réinitialisation…";
  try {
    await api("/api/reset", { method: "POST" });
    $("#reset-status").textContent = "✅ Bibliothèque réinitialisée.";
    toast("Tout a été réinitialisé");
  } catch (e) { $("#reset-status").textContent = "❌ " + e.message; }
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
/* Molette → défilement horizontal des carrousels de la fiche. */
modalContent.addEventListener("wheel", (e) => {
  const sc = e.target.closest(".row-scroll");
  if (sc && Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
    sc.scrollLeft += e.deltaY; e.preventDefault();
  }
}, { passive: false });
function closeModal() {
  modal.classList.add("hidden"); modal.classList.remove("full");
  modalContent.innerHTML = "";
}
modal.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

const DV_LOADING = `<div class="dv-body"><p class="muted">Chargement…</p></div>`;
const dvErr = (e) => `<div class="dv-body"><p class="muted">${esc(e.message)}</p></div>`;

async function openDetail(id, opts = {}) {
  modal.classList.remove("hidden"); modal.classList.add("full");
  modalContent.innerHTML = DV_LOADING;
  try {
    const n = normLocal(await api(`/api/title/${id}`));
    modalContent.innerHTML = renderTitlePage(n);
    loadSimilar(n.tmdb, n.type);
    if (opts.seasons) scrollToSeasons();
    if (n.syncPending) pollSeasons(id);  // remplissage épisodes en arrière-plan
  } catch (e) { modalContent.innerHTML = dvErr(e); }
}

/* Fait défiler la fiche jusqu'à la section Saisons (ouverture « Déjà vu »). */
function scrollToSeasons() {
  const s = $(".dv-seasons");
  if (s) s.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* Rafraîchit le bloc des saisons quand les épisodes finissent de se remplir. */
function pollSeasons(id) {
  setTimeout(async () => {
    const box = document.querySelector(`.dv-seasons[data-localid="${id}"]`);
    if (!box || modal.classList.contains("hidden")) return;  // fiche fermée/changée
    try {
      const n = normLocal(await api(`/api/title/${id}`));
      const fresh = document.querySelector(`.dv-seasons[data-localid="${id}"]`);
      if (fresh) fresh.outerHTML = seasonsBlock(n);
      if (n.syncPending) pollSeasons(id);
    } catch (_) { /* on réessaiera à la prochaine ouverture */ }
  }, 1500);
}

async function openPreview(tmdb, type, opts = {}) {
  modal.classList.remove("hidden"); modal.classList.add("full");
  modalContent.innerHTML = DV_LOADING;
  try {
    const n = normTmdb(await api(`/api/preview?tmdb_id=${tmdb}&type=${type}`));
    modalContent.innerHTML = renderTitlePage(n);
    loadSimilar(n.tmdb, n.type);
    if (opts.seasons) scrollToSeasons();
  } catch (e) { modalContent.innerHTML = dvErr(e); }
}

/* Charge le carrousel « Parce que tu as aimé ce titre » (après affichage). */
async function loadSimilar(tmdb, type) {
  const box = $("#dv-similar");
  if (!box || !tmdb) return;
  try {
    const { results } = await api(`/api/similar?tmdb_id=${tmdb}&type=${type}`);
    box.innerHTML = results.length ? results.map(posterCard).join("")
      : `<p class="muted">Aucune suggestion pour l'instant.</p>`;
  } catch (_) { box.innerHTML = `<p class="muted">—</p>`; }
}

function normLocal(data) {
  const t = data.titre;
  return { inLib: true, localId: t.id, tmdb: t.tmdb_id, type: t.type, titre: t.titre,
    annee: t.annee, date_sortie: t.date_sortie, duree: t.duree, resume: t.resume,
    genres: t.genres || [], note_tmdb: t.note_tmdb, fond: t.fond, affiche: t.affiche,
    bande_annonce: t.bande_annonce, plateformes: t.plateformes || [], casting: t.casting || [],
    equipe: t.equipe || [], statut: t.statut, favori: t.favori,
    watches: data.visionnages || [], saisons: data.saisons || [], next: data.prochain_episode,
    syncPending: data.sync_pending || false };
}
function normTmdb(t) {
  return { inLib: false, localId: null, tmdb: t.tmdb_id, type: t.type, titre: t.titre,
    annee: t.annee, date_sortie: t.date_sortie, duree: t.duree, resume: t.resume,
    genres: t.genres || [], note_tmdb: t.note_tmdb, fond: t.fond, affiche: t.affiche,
    bande_annonce: t.bande_annonce, plateformes: t.plateformes || [], casting: t.casting || [],
    equipe: t.equipe || [], statut: null, favori: false, watches: [],
    saisons: t.saisons || [], next: t.prochain_episode,
    nb_saisons: t.nb_saisons, nb_episodes: t.nb_episodes };
}

function fmtRuntime(min) {
  if (!min) return "";
  const h = Math.floor(min / 60), m = min % 60;
  return h ? (m ? `${h}h${String(m).padStart(2, "0")}` : `${h}h`) : `${m}min`;
}
const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
              "sept.", "oct.", "nov.", "déc."];
function fmtDate(s) {
  if (!s) return "";
  const p = s.split("-");
  return p.length < 3 ? s : `${+p[2]} ${MOIS[+p[1] - 1] || ""} ${p[0]}`;
}

/* Page plein écran d'un titre (fiche si en biblio, aperçu sinon). */
function renderTitlePage(n) {
  const seen = n.watches.length > 0 || n.statut === "vu";
  const genres = (n.genres || []).map(genreTag).join("");
  const meta = [fmtRuntime(n.duree), n.type === "serie" ? "Série" : "Film"].filter(Boolean).join(" · ");
  const trailer = n.bande_annonce ? `<a class="dv-trailer" target="_blank" rel="noopener"
       href="https://www.youtube.com/watch?v=${n.bande_annonce}">▶ Bande-annonce</a>` : "";
  const note = n.note_tmdb ? `<div class="dv-note">
       <span class="dv-note-val">★ ${n.note_tmdb}</span><span class="muted">/ 10 · TMDB</span></div>` : "";
  const providers = (n.plateformes || []).length ? `<h3 class="dv-h3">Où regarder</h3>
       <div class="providers">${n.plateformes.map((p) => `<img title="${esc(p.nom)}" src="${p.logo}" alt="${esc(p.nom)}">`).join("")}</div>` : "";
  const watchChips = n.watches.length ? `<div class="dv-watches">${n.watches.map((w) =>
      `<span class="watch-chip">${w.date ? fmtDate(w.date) : "déjà vu"}<button
         class="watch-del" data-delwatch="${w.id}" aria-label="Supprimer ce visionnage">✕</button></span>`).join("")}</div>` : "";
  const vuBlock = seen ? `<div class="dv-seen">
      <span class="dv-seen-count">Vu ${n.watches.length || 1} fois</span>
      ${watchChips}
      <button class="btn small" data-act="revu">↻ J'ai revu</button></div>` : "";
  const actions = `<div class="dv-actions" data-localid="${n.localId || ""}"
       data-tmdb="${n.tmdb || ""}" data-type="${n.type}">
    <button class="dv-act ${seen ? "done" : ""}" data-act="vu">
      <span class="dv-ic">${seen ? "✓" : "○"}</span><span>${seen ? "Vu" : "Marquer comme vu"}</span></button>
    <button class="dv-act ${n.statut === "a_voir" ? "done" : ""}" data-act="avoir">
      <span class="dv-ic">＋</span><span>Liste de suivi</span></button>
    <button class="dv-act" data-act="liste">
      <span class="dv-ic">≣</span><span>Ajouter à la liste…</span></button>
  </div>`;
  return `<div class="dv-hero" style="background-image:url('${n.fond || n.affiche || ""}')">
      <button class="dv-back" data-close aria-label="Retour">←</button>
      ${n.inLib ? `<button class="dv-fav ${n.favori ? "on" : ""}" data-fav data-localid="${n.localId}">♥</button>` : ""}
    </div>
    <div class="dv-head">
      <img class="dv-poster" src="${posterSrc(n.affiche)}" alt="">
      <div class="dv-headinfo">
        ${n.date_sortie ? `<div class="dv-date">${fmtDate(n.date_sortie)}</div>` : ""}
        <div class="dv-sub">${meta}</div>
        ${trailer}
      </div>
    </div>
    <div class="dv-body" data-localid="${n.localId || ""}">
      <h1 class="dv-title">${esc(n.titre)}</h1>
      <div class="dv-genres">${genres}</div>
      <p class="dv-resume">${esc(n.resume) || "Pas de résumé."}</p>
      ${actions}${vuBlock}${note}${providers}
      ${n.type === "serie" ? seasonsBlock(n) : ""}
      ${renderCastCrew(n.casting, n.equipe)}
      ${n.tmdb ? `<h3 class="dv-h3">Parce que tu as aimé « ${esc(n.titre)} »</h3>
        <div class="row-wrap">
          <button class="row-arrow left" aria-label="Précédent">‹</button>
          <div class="row-scroll" id="dv-similar"><p class="muted">Chargement…</p></div>
          <button class="row-arrow right" aria-label="Suivant">›</button>
        </div>` : ""}
      ${n.inLib ? `<div class="dv-remove"><button class="btn small danger" data-del data-localid="${n.localId}">Retirer de ma bibliothèque</button></div>` : ""}
    </div>`;
}

/* Distribution & équipe : grandes vignettes d'acteurs + membres de l'équipe. */
function renderCastCrew(cast, equipe) {
  cast = cast || []; equipe = equipe || [];
  if (!cast.length && !equipe.length) return "";
  const castHtml = cast.length ? `<div class="cast-row">${cast.map((c) => `
    <div class="cast" data-person="${c.id}">
      <img loading="lazy" src="${posterSrc(c.photo)}" alt="">
      <div class="cast-name">${esc(c.nom)}</div>
      ${c.personnage ? `<div class="cast-role">${esc(c.personnage)}</div>` : ""}
    </div>`).join("")}</div>` : "";
  const crewHtml = equipe.length ? `<div class="crew-row">${equipe.map((c) => `
    <div class="crew" data-person="${c.id}">
      <img loading="lazy" src="${posterSrc(c.photo)}" alt="">
      <div><div class="crew-name">${esc(c.nom)}</div><div class="crew-role">${esc(c.poste)}</div></div>
    </div>`).join("")}</div>` : "";
  return `<h3 class="dv-h3">Distribution &amp; équipe</h3>${castHtml}${crewHtml}`;
}

function seasonsBlock(n) {
  const next = n.next;
  const sais = n.saisons || [];
  const seasons = sais.map((s) => {
    // En biblio : chaque saison a ses épisodes (total/vus). En aperçu : seul
    // le nombre d'épisodes est connu, les épisodes se chargent au dépliage.
    const total = n.inLib ? (s.total || 0) : (s.nb_episodes || 0);
    const vus = n.inLib ? (s.vus || 0) : 0;
    const seen = n.inLib && total > 0 && vus >= total;
    const body = n.inLib
      ? (s.episodes || []).map((e) => episodeRow(e)).join("")
      : `<p class="muted ep-loading">Chargement des épisodes…</p>`;
    return `<div class="season" data-season="${s.numero}"${n.inLib ? "" : ' data-lazy="1"'}>
      <div class="season-head">
        <span class="season-toggle"><span class="chevron">▸</span>
          <span class="season-title">Saison ${s.numero}</span>
          <span class="season-prog">${vus}/${total}</span></span>
        <button class="ep-btn season-vu ${seen ? "vu" : ""}"
          data-markseason="${s.numero}" data-seen="${seen ? 1 : 0}">${seen ? "✓ Vue" : "Déjà vu"}</button>
      </div>
      <div class="season-body">${body}</div>
    </div>`;
  }).join("");
  const allSeen = n.inLib && sais.length > 0
    && sais.every((s) => s.total > 0 && s.vus >= s.total);
  return `<div class="dv-seasons" data-localid="${n.localId || ""}"
       data-tmdb="${n.tmdb || ""}" data-type="${n.type}">
    ${next ? `<p class="muted">Prochain épisode : S${next.saison}E${next.numero}
       « ${esc(next.nom || "")} » le ${fmtDate(next.date_diff)}</p>` : ""}
    <h3 class="dv-h3">Saisons</h3>
    ${seasons || `<p class="muted">${n.syncPending
        ? "Chargement des épisodes…" : "Épisodes indisponibles."}</p>`}
    ${sais.length ? `<button class="btn full dv-serievue ${allSeen ? "" : "primary"}"
       data-markseries>
       ${allSeen ? "↻ J'ai revu toute la série" : "✓ J'ai vu toute la série"}</button>` : ""}
  </div>`;
}

async function openPerson(id) {
  modal.classList.remove("hidden"); modal.classList.remove("full");
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

function episodeRow(e) {
  // En biblio : bouton lié à l'id local (bascule). En aperçu : pas encore
  // d'id local → on repère l'épisode par (saison, numéro) et l'action ajoute
  // d'abord la série à la bibliothèque.
  const btn = e.id
    ? `<button class="ep-btn ${e.vu ? "vu" : ""}" data-ep="${e.id}">${e.vu ? "✓ Revu" : "Vu"}</button>`
    : `<button class="ep-btn" data-epnum="${e.numero}" data-season="${e.saison}">Vu</button>`;
  return `<div class="episode">
    <img loading="lazy" src="${posterSrc(e.image)}" alt="">
    <div class="ep-info">
      <div class="ep-title">${e.numero}. ${esc(e.nom || "Épisode " + e.numero)}</div>
      <div class="ep-meta">${e.date_diff || ""}${e.duree ? " · " + e.duree + " min" : ""}
        ${e.nb_vues > 1 ? " · vu ×" + e.nb_vues : ""}</div>
      <div class="ep-resume">${esc(e.resume)}</div>
    </div>
    <div class="ep-check">${btn}</div></div>`;
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
  if (e.target.closest("[data-close]")) return closeModal();
  const arrowEl = e.target.closest(".row-arrow");
  if (arrowEl) {
    const sc = arrowEl.parentElement.querySelector(".row-scroll");
    if (sc) { const dx = sc.clientWidth * 0.85;
      sc.scrollBy({ left: arrowEl.classList.contains("left") ? -dx : dx, behavior: "smooth" }); }
    return;
  }
  const actEl = e.target.closest("[data-act]");
  if (actEl) return handleTitleAct(actEl);
  const posterEl = e.target.closest(".poster");
  if (posterEl) return openItem(posterEl);

  const idFrom = (sel) => { const el = e.target.closest("[data-localid]");
    return el && el.dataset.localid ? Number(el.dataset.localid) : null; };
  try {
    const favEl = e.target.closest("[data-fav]");
    const delEl = e.target.closest("[data-del]");
    if (favEl) {
      const id = Number(favEl.dataset.localid);
      await api(`/api/library/${id}`, { method: "PATCH",
        body: { favori: !favEl.classList.contains("on") } });
      openDetail(id);
    } else if (delEl) {
      if (confirm("Retirer ce titre de ta bibliothèque ?")) {
        await api(`/api/library/${delEl.dataset.localid}`, { method: "DELETE" });
        closeModal(); refreshAll(); toast("Titre retiré");
      }
    } else if (e.target.closest("[data-delwatch]")) {
      const w = e.target.closest("[data-delwatch]"), id = idFrom();
      await api(`/api/watch/${w.dataset.delwatch}`, { method: "DELETE" });
      if (id) openDetail(id); refreshAll();
    } else if (e.target.closest("[data-ep]")) {
      await api(`/api/episode/${e.target.closest("[data-ep]").dataset.ep}/toggle`,
        { method: "POST" });
      const id = idFrom(); if (id) openDetail(id);
    } else if (e.target.closest("[data-epnum]")) {
      // Épisode d'un aperçu : on ajoute d'abord la série, puis on marque.
      const b = e.target.closest("[data-epnum]");
      const id = await ensureInLib(seasonCtx(b));
      await api(`/api/title/${id}/episode/${b.dataset.season}/${b.dataset.epnum}/toggle`,
        { method: "POST" });
      openDetail(id); refreshAll();
    } else if (e.target.closest("[data-markseason]")) {
      const b = e.target.closest("[data-markseason]");
      const id = await ensureInLib(seasonCtx(b));
      await api(`/api/title/${id}/season/${b.dataset.markseason}/mark`,
        { method: "POST", body: { vu: b.dataset.seen !== "1" } });
      openDetail(id); refreshAll();
    } else if (e.target.closest("[data-markseries]")) {
      const b = e.target.closest("[data-markseries]");
      const id = await ensureInLib(seasonCtx(b));
      await api(`/api/title/${id}/mark`, { method: "POST", body: { vu: true } });
      openDetail(id); refreshAll();
    } else {
      const head = e.target.closest(".season-head");
      if (head) {
        const season = head.parentElement;
        season.classList.toggle("open");
        if (season.classList.contains("open")) loadSeasonEpisodes(season);
      }
    }
  } catch (err) { toast(err.message); }
});

/* Contexte série (id local / tmdb / type) partagé par les boutons de saison. */
function seasonCtx(el) {
  const box = el.closest(".dv-seasons") || {};
  const d = box.dataset || {};
  return { localid: d.localid ? Number(d.localid) : null,
           tmdb: d.tmdb ? Number(d.tmdb) : null, type: d.type };
}

/* Ajoute la série à la bibliothèque si besoin et renvoie son id local. */
async function ensureInLib(ctx) {
  if (ctx.localid) return ctx.localid;
  const r = await api("/api/library", { method: "POST",
    body: { tmdb_id: ctx.tmdb, type: ctx.type, statut: "a_voir" } });
  refreshAll();
  return r.id;
}

/* Charge les épisodes d'une saison en aperçu (au premier dépliage). */
async function loadSeasonEpisodes(season) {
  if (season.dataset.lazy !== "1" || season.dataset.loaded === "1") return;
  season.dataset.loaded = "1";
  const ctx = seasonCtx(season), body = season.querySelector(".season-body");
  try {
    const { episodes } = await api(
      `/api/preview/season?tmdb_id=${ctx.tmdb}&saison=${season.dataset.season}`);
    body.innerHTML = episodes.length ? episodes.map(episodeRow).join("")
      : `<p class="muted">Épisodes indisponibles.</p>`;
  } catch (_) {
    season.dataset.loaded = "0";
    body.innerHTML = `<p class="muted">Impossible de charger les épisodes.</p>`;
  }
}

/* Actions principales de la page titre (Vu / Revu / Liste de suivi / Liste). */
async function handleTitleAct(actEl) {
  const box = actEl.closest("[data-tmdb]") || actEl.closest("[data-localid]");
  const localid = box && box.dataset.localid ? Number(box.dataset.localid) : null;
  const tmdb = box && box.dataset.tmdb ? Number(box.dataset.tmdb) : null;
  const type = box ? box.dataset.type : null;
  const act = actEl.dataset.act;
  try {
    if (act === "liste") {
      if (localid) return addToListPrompt(localid);
      const r = await api("/api/library", { method: "POST",
        body: { tmdb_id: tmdb, type, statut: "a_voir" } });
      refreshAll(); return addToListPrompt(r.id);
    }
    if (act === "revu") {
      if (localid) { await api(`/api/title/${localid}/watch`, { method: "POST", body: {} });
        openDetail(localid); refreshAll(); }
      return;
    }
    const statut = act === "vu" ? "vu" : "a_voir";
    if (localid) {
      await api(`/api/library/${localid}`, { method: "PATCH", body: { statut } });
      openDetail(localid);
    } else {
      const r = await api("/api/library", { method: "POST",
        body: { tmdb_id: tmdb, type, statut } });
      toast(statut === "vu" ? "Marqué comme vu ✓" : "Ajouté à « À voir »");
      openDetail(r.id);
    }
    refreshAll();
  } catch (err) { toast(err.message); }
}

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
  modal.classList.remove("hidden"); modal.classList.remove("full");
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
  modal.classList.remove("hidden"); modal.classList.remove("full");
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

/* Au démarrage : onglet Suggestions (marqué chargé pour éviter un rechargement). */
_tabLoaded.add("suggestions");
loadSuggestions();
