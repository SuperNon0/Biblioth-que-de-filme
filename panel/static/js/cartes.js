/* =========================================================================
   cinéthèque — affiches (C1 à C4), grilles, rangées qui défilent et
   squelettes de chargement (A4).
   Chaque titre affiché est gardé dans TITRES : la carte ne porte que sa clé.
   Le menu rapide et les mises à jour sur place (après un marquage ou un
   « Annuler ») repartent de cet objet, sans recharger la page.
   ========================================================================= */
"use strict";

const TITRES = new Map();

/* État « dans ma bibliothèque » : toujours posé (null = rien), pour qu'une
   donnée plus récente efface bien l'ancienne. */
const ETAT_LOCAL = {
  lid: null, statut: null, favori: false, nb_vues: 0, date_ajout: null, vu_le: null,
  total_ep: 0, vus_ep: 0, next_saison: null, next_numero: null, next_nom: null,
  next_duree: null, revoit: false, a_venir: 0, prochaine_diffusion: null, dispo: null,
};
const INFOS_TITRE = ["tmdb_id", "type", "titre", "annee", "affiche", "fond", "note_tmdb",
  "genres", "date_sortie", "nb_saisons", "resume", "alerte", "personnage"];

/* Même forme qu'un titre vienne de la bibliothèque (id local) ou de TMDB
   (local_id quand il y est déjà). */
function normTitre(it) {
  const n = {};
  for (const k of INFOS_TITRE) if (it[k] !== undefined && it[k] !== null) n[k] = it[k];
  for (const k of Object.keys(ETAT_LOCAL)) n[k] = it[k] ?? ETAT_LOCAL[k];
  n.lid = it.lid ?? it.local_id ?? it.id ?? null;
  n.favori = !!it.favori;
  return n;
}
const cleDe = (t) => t.lid ? "l" + t.lid : `t${t.type === "serie" ? "s" : "f"}${t.tmdb_id}`;

/* Range un titre dans le registre (fusion avec ce qu'on en savait déjà). */
function retenir(it) {
  const n = normTitre(it);
  const k = cleDe(n);
  const deja = TITRES.get(k);
  if (deja) {
    // Un résultat TMDB ne dit rien du cœur ni de la plateforme incluse :
    // on garde ce que la bibliothèque en savait.
    if (it.favori === undefined) delete n.favori;
    if (it.dispo === undefined) delete n.dispo;
    Object.assign(deja, n);
    return deja;
  }
  TITRES.set(k, n);
  return n;
}
/* Titre de ma bibliothèque connu par son id local (journal, statistiques) :
   l'objet du registre s'il existe, sans écraser son état par des valeurs vides. */
function titreLocal(lid, infos = {}) {
  return TITRES.get("l" + lid) || retenir({ ...infos, id: lid });
}
const titreDe = (el) => {
  const c = el && el.closest("[data-k]");
  return c ? TITRES.get(c.dataset.k) || null : null;
};
const memeTitre = (a, b) => a === b || (a.lid && a.lid === b.lid)
  || (!!a.tmdb_id && a.tmdb_id === b.tmdb_id && a.type === b.type);

const libType = (t) => t.type === "serie" ? "Série" : "Film";
const noteTxt = (n) => n ? Number(n).toFixed(1).replace(".", ",") : "";
const aVenir = (iso) => !!iso && iso.slice(0, 10) > isoLocal();
const dejaVu = (t) => t.statut === "vu" || (t.type === "film" && t.nb_vues > 0);

/* Ligne d'info sous l'affiche (C2, C4) : épisode à voir, date de sortie… */
function legendeCarte(t) {
  if (t.type === "serie" && t.lid && t.total_ep) {
    if (t.next_saison && (t.vus_ep > 0 || t.revoit)) {
      return { cls: "p", txt: (t.revoit ? "↻ " : "") + codeEp(t.next_saison, t.next_numero)
        + (t.revoit ? "" : ` · ${t.vus_ep} / ${t.total_ep}`) };
    }
    if (t.statut === "vu") {
      const pd = t.prochaine_diffusion;
      if (pd && pd.date) return { cls: "a", txt: `S${pd.saison} le ${fmtDate(pd.date, { court: true })}` };
      return { cls: "", txt: `Terminée · ${pluriel(t.total_ep, "épisode")}` };
    }
  }
  if (aVenir(t.date_sortie)) {
    return { cls: "a", txt: `${t.type === "serie" ? "Dès le" : "Sortie le"} ${fmtDate(t.date_sortie, { court: true })}` };
  }
  if (t.type === "film" && t.statut === "vu" && t.vu_le) {
    return { cls: "", txt: `Vu le ${fmtDate(t.vu_le, { court: true })}${t.nb_vues > 1 ? ` · ×${t.nb_vues}` : ""}` };
  }
  const bits = [libType(t), t.annee].filter(Boolean);
  if (t.note_tmdb) bits.push("★ " + noteTxt(t.note_tmdb));
  return { cls: "", txt: bits.join(" · ") };
}

function etiquetteStatut(t) {
  if (t.statut === "vu") return t.type === "serie" ? "série vue" : "vu";
  if (t.statut === "a_voir") return "à voir";
  if (t.statut === "en_cours") return "en cours";
  return "";
}

/* Badges (C1) : coche verte « vu », marque-page « à voir », barre violette de
   progression, date pour ce qui n'est pas encore sorti. */
function badgesCarte(t, o = {}) {
  let h = "";
  if (o.cloche && t.type === "film" && aVenir(t.date_sortie)) {
    // « Bientôt au cinéma » (A5) : la date de sortie reste sur l'affiche.
    h += `<span class="po-b">${esc(fmtDate(t.date_sortie, { court: true, annee: false }))}</span>`;
  } else if (t.statut === "vu") {
    const fois = t.nb_vues > 1 ? t.nb_vues : 0;
    h += fois ? `<span class="po-b ok">${ic("check")}×${fois}</span>`
      : `<span class="po-b ok ic" title="Vu">${ic("check")}</span>`;
  } else if (t.statut === "a_voir") {
    h += `<span class="po-b acc ic" title="À voir plus tard">${ic("bookmarkon")}</span>`;
  } else if (!t.statut && aVenir(t.date_sortie)) {
    h += `<span class="po-b">${esc(fmtDate(t.date_sortie, { court: true, annee: false }))}</span>`;
  }
  if (t.favori) h += `<span class="po-b r ic coeur" title="Favori">${ic("heartfill")}</span>`;
  if (t.type === "serie" && t.total_ep && (t.vus_ep || t.statut === "vu")) {
    const pct = Math.min(100, Math.round((t.vus_ep || 0) / t.total_ep * 100));
    h += `<span class="po-pin${pct >= 100 ? " ok" : ""}"><i style="width:${pct}%"></i></span>`;
  }
  if (t.dispo && t.dispo.logo) {
    h += `<span class="po-plat" title="Inclus dans ${esc(t.dispo.nom)}"><img src="${posterSrc(t.dispo.logo)}" alt="" loading="lazy"></span>`;
  }
  return h;
}

/* Une affiche. o : options (cloche : alerte de sortie en un geste, A5). */
function htmlCarte(t, o = {}) {
  const lg = legendeCarte(t);
  const statut = etiquetteStatut(t);
  const aria = [t.titre, t.annee, libType(t).toLowerCase(), statut].filter(Boolean).join(", ");
  const img = t.affiche
    ? `<img src="${posterSrc(t.affiche)}" alt="" loading="lazy" decoding="async">`
    : `<div class="sans">${esc(t.titre)}</div>`;
  const cloche = o.cloche && t.type === "film"
    ? `<button type="button" class="po-cloche${t.alerte ? " on" : ""}" data-cloche aria-pressed="${t.alerte ? "true" : "false"}"
        aria-label="${t.alerte ? "Retirer l'alerte de sortie" : "M'alerter à la sortie"}">${ic(t.alerte ? "bellon" : "bell")}</button>` : "";
  return `<div class="po" data-k="${cleDe(t)}"${o.cloche ? ' data-o="c"' : ""} tabindex="0" role="button" aria-label="${esc(aria)}">
    <div class="po-img">${img}${badgesCarte(t, o)}${cloche}
      <button type="button" class="po-more" data-more tabindex="-1" aria-label="Actions">${ic("dots", "s18")}</button>
      <span class="po-sel" aria-hidden="true">${ic("check", "s16")}</span></div>
    <div class="po-cap"><b>${esc(t.titre)}</b><span${lg.cls ? ` class="${lg.cls}"` : ""}>${esc(lg.txt)}</span></div>
  </div>`;
}
const htmlCartes = (items, o) => (items || []).map((it) => htmlCarte(retenir(it), o)).join("");

/* Ligne de la vue « liste » (B2) : mini-affiche, titre, info, statut. */
function htmlLigne(t) {
  const lg = legendeCarte(t);
  const statut = etiquetteStatut(t);
  const etat = statut ? `<span class="etat ${esc(t.statut)}">${t.statut === "vu" ? ic("check", "s16") : ""}${esc(statut)}</span>` : "";
  return `<div class="lt" data-k="${cleDe(t)}" tabindex="0" role="button" aria-label="${esc([t.titre, t.annee, statut].filter(Boolean).join(", "))}">
    <span class="po-sel" aria-hidden="true">${ic("check", "s16")}</span>
    <div class="mini">${t.affiche ? `<img src="${posterSrc(t.affiche)}" alt="" loading="lazy" decoding="async">` : ""}</div>
    <div class="tx"><b>${esc(t.titre)}${t.favori ? ` <span class="coeur-l" title="Favori">${ic("heartfill", "s16")}</span>` : ""}</b>
      <span${lg.cls ? ` class="${lg.cls}"` : ""}>${esc(lg.txt)}</span></div>
    ${etat}
  </div>`;
}

/* Redessine sur place toutes les affiches (et lignes) d'un même titre. */
function majCartes(t) {
  for (const el of $$(".po[data-k], .lt[data-k]")) {
    const e = TITRES.get(el.dataset.k);
    if (!e || !memeTitre(e, t)) continue;
    if (e !== t) for (const k of Object.keys(ETAT_LOCAL)) e[k] = t[k];
    if (t.alerte !== undefined) e.alerte = t.alerte;
    // Ajouté ou retiré : la clé change (« t… » ↔ « l… ») ; on l'inscrit.
    const k = cleDe(e);
    if (!TITRES.get(k)) TITRES.set(k, e);
    const tmp = document.createElement("div");
    tmp.innerHTML = el.classList.contains("lt") ? htmlLigne(e) : htmlCarte(e, { cloche: el.dataset.o === "c" });
    const neuf = tmp.firstElementChild;
    if (el.classList.contains("choisi")) neuf.classList.add("choisi");
    const focus = document.activeElement === el;
    el.replaceWith(neuf);
    if (focus) neuf.focus({ preventScroll: true });
  }
}

/* Recharge l'état local d'un titre depuis le serveur (après un marquage ou un
   « Annuler »), redessine ses affiches et prévient les pages concernées. */
async function actualiserTitre(t, { signal = true } = {}) {
  if (t.lid) {
    try {
      const { titre } = await api(`/api/library/${t.lid}`);
      const n = normTitre(titre);
      for (const k of Object.keys(ETAT_LOCAL)) t[k] = n[k];
    } catch (e) {
      if (!/introuvable/i.test(e.message)) throw e;
      Object.assign(t, ETAT_LOCAL);       // retiré de la bibliothèque
    }
  }
  majCartes(t);
  if (signal) signaler("titre", { lid: t.lid, tmdb_id: t.tmdb_id, type: t.type });
  return t;
}

/* Une personne (casting d'une fiche, recherche d'acteurs) : sa page s'ouvre
   au toucher, où qu'elle soit affichée. */
const htmlPersonne = (p, role = "") => `<button type="button" class="pers" data-pers="${Number(p.id) || 0}">
    <span class="ph">${p.photo ? `<img src="${posterSrc(p.photo)}" alt="" loading="lazy">` : esc((p.nom || "?")[0])}</span>
    <b>${esc(p.nom)}</b>${role ? `<span>${esc(role)}</span>` : ""}</button>`;
document.addEventListener("click", (e) => {
  const p = e.target.closest("[data-pers]");
  if (!p || e.defaultPrevented || !Number(p.dataset.pers)) return;
  e.preventDefault();
  ouvrirPersonne(Number(p.dataset.pers));
});

/* ------------------------------------------------------------ squelettes */
const SK_CARTE = `<div class="po" aria-hidden="true"><div class="sk po-sk"></div>
  <div class="sk-cap"><div class="sk ln"></div><div class="sk ln"></div></div></div>`;
const squeletteGrille = (n = 12) => SK_CARTE.repeat(n);
const squeletteRangees = (n = 3) => Array.from({ length: n }, () =>
  `<div aria-hidden="true"><div class="sk ln t"></div><div class="rangee"><div class="bande">${SK_CARTE.repeat(8)}</div></div></div>`).join("");
const squeletteLignes = (n = 5) => `<div aria-hidden="true">${'<div class="sk sk-l"></div>'.repeat(n)}</div>`;

function videHtml(icone, titre, texte = "", action = "") {
  return `<div class="vide">${ic(icone)}<b>${esc(titre)}</b>${texte ? `<span>${esc(texte)}</span>` : ""}${action}</div>`;
}
const erreurHtml = (e) => videHtml("alert", "Impossible d'afficher cette partie", e && e.message ? e.message : String(e || ""));

/* -------------------------------------------- rangées qui défilent (A1) */
function htmlRangee(titre, items, { cle = "", cloche = false, lien = "" } = {}) {
  return `<section class="rang"${cle ? ` data-cle="${esc(cle)}"` : ""}>
    <div class="sec-h"><h2 class="sec-t">${esc(titre)}</h2>${lien}</div>
    <div class="rangee">
      <button type="button" class="fl g cache" data-fl="-1" aria-label="Précédents" tabindex="-1">${ic("chevl")}</button>
      <div class="bande">${htmlCartes(items, { cloche })}</div>
      <button type="button" class="fl d" data-fl="1" aria-label="Suivants" tabindex="-1">${ic("chev")}</button>
    </div></section>`;
}
/* Flèches : masquées en butée. */
function majFleches(bande) {
  const r = bande.closest(".rangee");
  if (!r) return;
  const max = bande.scrollWidth - bande.clientWidth;
  r.querySelector(".fl.g")?.classList.toggle("cache", bande.scrollLeft <= 2);
  r.querySelector(".fl.d")?.classList.toggle("cache", bande.scrollLeft >= max - 2);
}
const majToutesFleches = (racine = document) => $$(".rangee .bande", racine).forEach(majFleches);

document.addEventListener("click", (e) => {
  const fl = e.target.closest(".rangee .fl");
  if (!fl) return;
  const bande = fl.parentElement.querySelector(".bande");
  bande.scrollBy({ left: Number(fl.dataset.fl) * bande.clientWidth * 0.85, behavior: "smooth" });
});
document.addEventListener("scroll", plusTard((e) => {
  if (e.target && e.target.classList && e.target.classList.contains("bande")) majFleches(e.target);
}, 80), { capture: true, passive: true });
/* Molette verticale → défilement horizontal d'une rangée, tant qu'elle peut
   avancer dans ce sens ; en butée, la page défile normalement. */
document.addEventListener("wheel", (e) => {
  const b = e.target.closest && e.target.closest(".bande");
  if (!b || Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
  const max = b.scrollWidth - b.clientWidth;
  if ((e.deltaY > 0 && b.scrollLeft >= max - 1) || (e.deltaY < 0 && b.scrollLeft <= 0)) return;
  b.scrollLeft += e.deltaY;
  e.preventDefault();
}, { passive: false });
addEventListener("resize", plusTard(() => majToutesFleches(), 150));

/* ---------------------------------------------------- ma bibliothèque */
/* Tous mes titres, chargés une fois puis gardés : filtres instantanés de la
   Bibliothèque (B1, B5), recherche Ctrl K (N3), compteur du menu de gauche.
   Un marquage la rend « périmée » : elle se recharge à la prochaine lecture. */
const MaBiblio = {
  titres: null,
  _p: null,
  _perimee: false,
  charger({ forcer = false } = {}) {
    if (this._p && !forcer && !this._perimee) return this._p;
    this._perimee = false;
    const p = api("/api/library?tri=ajout").then(({ titres }) => {
      if (this._p !== p) return this.titres;          // une lecture plus récente a pris la main
      this.titres = (titres || []).map(retenir);
      const n = $("#side-n-biblio");
      if (n) n.textContent = this.titres.length ? nb(this.titres.length) : "";
      signaler("biblio");
      return this.titres;
    });
    this._p = p;
    p.catch(() => { if (this._p === p) this._p = null; });
    return p;
  },
  perimer() { this._perimee = true; },
};
document.addEventListener("ct:titre", () => MaBiblio.perimer());
