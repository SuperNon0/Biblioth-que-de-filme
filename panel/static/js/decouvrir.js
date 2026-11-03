/* =========================================================================
   cinéthèque — Découvrir : le catalogue TMDB par genre et tri, avec les
   filtres rangés dans un petit menu (D1 : « 2020 et + », « Moins de 2 h »,
   note, plateforme, pays) et l'interrupteur « Sur mes plateformes » gardé
   dans la barre (D4). Les choix restent sur cet appareil.
   ========================================================================= */
"use strict";

const PAYS_DEC = [["", "Tous les pays"], ["FR", "France"], ["US", "États-Unis"], ["GB", "Royaume-Uni"],
  ["JP", "Japon"], ["KR", "Corée du Sud"], ["ES", "Espagne"], ["IT", "Italie"], ["DE", "Allemagne"],
  ["BE", "Belgique"], ["CA", "Canada"], ["DK", "Danemark"], ["SE", "Suède"], ["IN", "Inde"]];
const PERIODES_DEC = [["", "Toutes"], ["2020", "2020 et +"], ["2010", "2010 et +"], ["2000", "2000 et +"]];
const DUREES_DEC = [["", "Peu importe"], ["120", "Moins de 2 h"], ["90", "Moins de 1 h 30"]];
const NOTES_DEC = [["", "Toutes"], ["6", "6 et +"], ["7", "7 et +"], ["8", "8 et +"]];

const Dec = Object.assign({
  type: "film", genre: "", tri: "populaire", depuis: "", annee: "", duree_max: "", note: "",
  plateforme: "", pays: "", mes: false,
}, (() => { try { return JSON.parse(localStorage.getItem("ct-dec") || "{}"); } catch (_) { return {}; } })(),
{ page: 1, total: 1, req: 0, charge: false });
const _genresDec = {};
const _platsDec = {};

function sauverDec() {
  const { type, genre, tri, depuis, annee, duree_max, note, plateforme, pays, mes } = Dec;
  try { localStorage.setItem("ct-dec", JSON.stringify({ type, genre, tri, depuis, annee, duree_max, note, plateforme, pays, mes })); }
  catch (_) { /* privé */ }
}
/* Filtres du petit menu actuellement posés (la pastille en donne le nombre). */
function nbFiltresDec() {
  return [Dec.depuis || Dec.annee, Dec.type === "film" && Dec.duree_max, Dec.note, !Dec.mes && Dec.plateforme, Dec.pays]
    .filter(Boolean).length;
}
function majBarreDec() {
  $$("#dec-type [data-type]").forEach((b) => {
    const on = b.dataset.type === Dec.type;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
  });
  const tri = $("#dec-tri");
  if (tri) tri.value = Dec.tri;
  const mes = $("#dec-mes");
  if (mes) mes.checked = !!Dec.mes;
  const n = nbFiltresDec();
  const p = $("#dec-nb-filtres");
  if (p) { p.hidden = !n; p.textContent = n ? String(n) : ""; }
}

async function chargerGenresDec() {
  const box = $("#dec-genres");
  const type = Dec.type;
  if (!_genresDec[type]) {
    const cache = cacheGet(`genres:${type}`);
    if (cache) _genresDec[type] = cache;
    else box.innerHTML = `<span class="sk ln" style="width:240px;height:32px;border-radius:99px"></span>`;
    try {
      const { genres = [] } = await api(`/api/genres?type=${type}`);
      _genresDec[type] = genres;
      cacheSet(`genres:${type}`, genres);
    } catch (e) {
      if (!_genresDec[type]) { box.innerHTML = ""; return; }
    }
  }
  if (type !== Dec.type) return;
  const genres = _genresDec[type] || [];
  if (Dec.genre && !genres.some((g) => String(g.id) === String(Dec.genre))) Dec.genre = "";
  box.innerHTML = [`<button type="button" class="chip${Dec.genre ? "" : " on"}" data-genre="">Tous</button>`]
    .concat(genres.map((g) => `<button type="button" class="chip${String(g.id) === String(Dec.genre) ? " on" : ""}" data-genre="${g.id}">${esc(g.name)}</button>`))
    .join("");
  box.querySelector(".chip.on")?.scrollIntoView({ block: "nearest", inline: "center" });
}

function paramsDec(page) {
  const qs = new URLSearchParams({ type: Dec.type, tri: Dec.tri, page: String(page) });
  if (Dec.genre) qs.set("genre", Dec.genre);
  if (Dec.annee) qs.set("annee", Dec.annee);
  else if (Dec.depuis) qs.set("depuis", Dec.depuis);
  if (Dec.type === "film" && Dec.duree_max) qs.set("duree_max", Dec.duree_max);
  if (Dec.note) qs.set("note", Dec.note);
  if (Dec.pays) qs.set("pays", Dec.pays);
  if (Dec.mes) qs.set("mes", "1");
  else if (Dec.plateforme) qs.set("plateforme", Dec.plateforme);
  return qs;
}

async function chargerDec({ plus = false } = {}) {
  const box = $("#dec-resultats");
  const bPlus = $("#dec-plus");
  const my = ++Dec.req;
  const page = plus ? Dec.page + 1 : 1;
  if (!plus) {
    box.innerHTML = squeletteGrille(12);
    bPlus.hidden = true;
  }
  try {
    const d = await api(`/api/discover?${paramsDec(page)}`);
    if (my !== Dec.req) return;
    Dec.page = d.page || page;
    Dec.total = d.total_pages || 1;
    Dec.charge = true;
    const items = d.results || [];
    if (!plus) {
      if (d.sans_plateformes) {
        box.innerHTML = videHtml("tv", "Aucune plateforme indiquée",
          "Indique d'abord tes abonnements de streaming : ce filtre ne garde que ce qui y est inclus.",
          SUPER_ADMIN ? `<a class="btn sm pri" href="#parametres/plateformes">${ic("tv", "s18")}Mes plateformes</a>` : "");
      } else if (!items.length) {
        box.innerHTML = videHtml("compass", "Aucun titre avec ces filtres", "Élargis la période ou retire un filtre.",
          nbFiltresDec() || Dec.genre || Dec.mes ? `<button type="button" class="btn sm" data-dec-effacer>${ic("x", "s18")}Retirer les filtres</button>` : "");
      } else {
        box.innerHTML = htmlCartes(items);
        animerEntree(box);
      }
    } else {
      box.insertAdjacentHTML("beforeend", htmlCartes(items));
    }
    bPlus.hidden = !(items.length && Dec.page < Dec.total);
  } catch (e) {
    if (my !== Dec.req) return;
    if (!plus) box.innerHTML = erreurHtml(e);
    else toastErr(e);
  }
}

function relancerDec() {
  sauverDec();
  majBarreDec();
  chargerDec();
}

/* ---------------------------------------- petit menu des filtres (D1) */
async function ouvrirFiltresDec() {
  const choix = (nom, options, val) => `<div class="chips filtre-c" role="group" aria-label="${esc(nom)}" data-filtre="${nom}">${options.map(([v, l]) =>
    `<button type="button" class="chip${String(val) === v ? " on" : ""}" data-v="${v}">${esc(l)}</button>`).join("")}</div>`;
  const f = feuille({
    titre: "Filtres",
    classe: "filtres-f",
    html: `<div class="form">
      <div><div class="lbl">Sortie</div>${choix("depuis", PERIODES_DEC, Dec.annee ? "x" : Dec.depuis)}
        <div class="ligne filtre-annee"><label class="lbl" for="fd-annee">ou une année précise</label>
          <input class="input" id="fd-annee" type="number" inputmode="numeric" min="1900" max="2100" placeholder="ex. 1999" value="${esc(Dec.annee)}"></div></div>
      ${Dec.type === "film" ? `<div><div class="lbl">Durée</div>${choix("duree_max", DUREES_DEC, Dec.duree_max)}</div>` : ""}
      <div><div class="lbl">Note TMDB</div>${choix("note", NOTES_DEC, Dec.note)}</div>
      <div><label class="lbl" for="fd-plat">Plateforme</label>
        <select class="select" id="fd-plat"${Dec.mes ? " disabled" : ""}><option value="">Toutes les plateformes</option></select>
        ${Dec.mes ? `<p class="muted petit">« Sur mes plateformes » est activé : il remplace ce choix.</p>` : ""}</div>
      <div><label class="lbl" for="fd-pays">Pays d'origine</label>
        <select class="select" id="fd-pays">${PAYS_DEC.map(([v, l]) => `<option value="${v}"${v === Dec.pays ? " selected" : ""}>${esc(l)}</option>`).join("")}</select></div>
      <div class="conf"><div class="bts"><button type="button" class="btn" data-fd-effacer>Tout effacer</button>
        <button type="button" class="btn pri" data-fd-ok>Voir les résultats</button></div></div>
    </div>`,
  });
  const brouillon = { depuis: Dec.depuis, annee: Dec.annee, duree_max: Dec.duree_max, note: Dec.note, plateforme: Dec.plateforme, pays: Dec.pays };
  const sel = f.el.querySelector("#fd-plat");
  // Plateformes de la région, chargées une fois par type.
  (async () => {
    try {
      if (!_platsDec[Dec.type]) _platsDec[Dec.type] = (await api(`/api/providers?type=${Dec.type}`)).providers || [];
      if (f.ferme) return;
      sel.insertAdjacentHTML("beforeend", _platsDec[Dec.type].slice(0, 60).map((p) =>
        `<option value="${esc(p.id)}"${String(p.id) === String(brouillon.plateforme) ? " selected" : ""}>${esc(p.nom)}</option>`).join(""));
    } catch (_) { /* la liste reste à « Toutes » */ }
  })();
  f.el.addEventListener("click", (e) => {
    const c = e.target.closest("[data-filtre] [data-v]");
    if (c) {
      const groupe = c.closest("[data-filtre]");
      $$(".chip", groupe).forEach((x) => x.classList.toggle("on", x === c));
      brouillon[groupe.dataset.filtre] = c.dataset.v;
      if (groupe.dataset.filtre === "depuis") { brouillon.annee = ""; f.el.querySelector("#fd-annee").value = ""; }
      return;
    }
    if (e.target.closest("[data-fd-effacer]")) {
      Object.assign(Dec, { depuis: "", annee: "", duree_max: "", note: "", plateforme: "", pays: "" });
      f.fermer();
      relancerDec();
      return;
    }
    if (e.target.closest("[data-fd-ok]")) {
      Object.assign(Dec, brouillon);
      f.fermer();
      relancerDec();
    }
  });
  f.el.querySelector("#fd-annee").addEventListener("input", (e) => {
    brouillon.annee = e.target.value.replace(/\D/g, "").slice(0, 4);
    if (brouillon.annee) {
      brouillon.depuis = "";
      $$('[data-filtre="depuis"] .chip', f.el).forEach((x) => x.classList.remove("on"));
    }
  });
  sel.addEventListener("change", () => { brouillon.plateforme = sel.value; });
  f.el.querySelector("#fd-pays").addEventListener("change", (e) => { brouillon.pays = e.target.value; });
}

/* ----------------------------------------------------------- évènements */
$("#dec-type")?.addEventListener("click", (e) => {
  const b = e.target.closest("[data-type]");
  if (!b || b.dataset.type === Dec.type) return;
  Dec.type = b.dataset.type;
  Dec.genre = "";
  Dec.plateforme = "";          // les identifiants diffèrent entre films et séries
  majBarreDec();
  chargerGenresDec();
  relancerDec();
});
$("#dec-genres")?.addEventListener("click", (e) => {
  const b = e.target.closest("[data-genre]");
  if (!b || b.dataset.genre === String(Dec.genre)) return;
  Dec.genre = b.dataset.genre;
  $$("#dec-genres .chip").forEach((x) => x.classList.toggle("on", x === b));
  relancerDec();
});
$("#dec-tri")?.addEventListener("change", (e) => { Dec.tri = e.target.value; relancerDec(); });
$("#dec-mes")?.addEventListener("change", (e) => { Dec.mes = e.target.checked; relancerDec(); });
$("#dec-filtres")?.addEventListener("click", () => ouvrirFiltresDec());
$("#dec-plus")?.addEventListener("click", (e) => occupe(e.currentTarget, () => chargerDec({ plus: true })));
$("#dec-roulette")?.addEventListener("click", () => ouvrirRoulette("catalog", Dec.type));
$("#dec-resultats")?.addEventListener("click", (e) => {
  if (!e.target.closest("[data-dec-effacer]")) return;
  Object.assign(Dec, { genre: "", depuis: "", annee: "", duree_max: "", note: "", plateforme: "", pays: "", mes: false });
  chargerGenresDec();
  relancerDec();
});

Pages.decouvrir = {
  afficher() {
    majBarreDec();
    if (!Dec.charge) { chargerGenresDec(); chargerDec(); }
  },
};
