/* =========================================================================
   cinéthèque — Accueil : grande carte « Reprendre » (A2), rangées de
   suggestions dans l'ordre choisi (A1, A3), « Bientôt au cinéma » avec la
   cloche en un geste (A5) et squelettes pendant le chargement (A4).
   Le dernier accueil connu s'affiche tout de suite (cache local), puis se
   rafraîchit ; un épisode marqué ailleurs remet la série en tête sans
   recharger les suggestions.
   ========================================================================= */
"use strict";

const Accueil = {
  media: (() => { try { return localStorage.getItem("ct-acc-media") || "all"; } catch (_) { return "all"; } })(),
  blocs: null,        // rangées reçues (titres du registre)
  reprendre: [],      // séries en cours, la plus récemment regardée d'abord
  _etat: new Map(),   // lid → empreinte de progression (repère un épisode vu)
  _quand: 0,          // heure du dernier chargement réussi
  _req: 0,
  _perime: false,
};
const PERIME_ACCUEIL = 30 * 60 * 1000;   // suggestions renouvelées après 30 min
const empreinte = (t) => [t.statut, t.vus_ep, t.next_saison, t.next_numero, t.nb_vues].join("|");
// Pas de cache pendant « voir en tant que » : ce ne sont pas tes suggestions.
const cleAccueil = (m) => CT.imp ? null : `sug2:${m}`;

function majSegMedia() {
  $$("#acc-media [data-media]").forEach((b) => {
    const on = b.dataset.media === Accueil.media;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
  });
}

function squeletteAccueil() {
  $("#acc-reprendre").innerHTML = PREFS.reprendre !== "rangee" ? `<div class="sk sk-res" aria-hidden="true"></div>` : "";
  $("#acc-rangees").innerHTML = squeletteRangees(3);
}

/* Range la réponse du serveur : chaque titre passe par le registre. */
function recevoirAccueil(blocs) {
  Accueil.blocs = blocs.map((b) => ({ cle: b.cle, titre: b.titre, items: (b.items || []).map(retenir) }));
  const rep = Accueil.blocs.find((b) => b.cle === "reprendre");
  Accueil.reprendre = rep ? rep.items.filter((t) => t.lid) : [];
  Accueil._etat.clear();
  Accueil.reprendre.forEach((t) => Accueil._etat.set(t.lid, empreinte(t)));
}

async function chargerAccueil({ forcer = false } = {}) {
  const n = ++Accueil._req;
  const media = Accueil.media;
  const cle = cleAccueil(media);
  if (!Accueil.blocs) {
    const c = cle && cacheGet(cle);
    if (c && Array.isArray(c.blocs)) { recevoirAccueil(c.blocs); rendreAccueil(); }
    else squeletteAccueil();
  }
  try {
    const { blocs = [] } = await api(`/api/suggestions?media=${encodeURIComponent(media)}`);
    if (n !== Accueil._req) return;
    if (cle) cacheSet(cle, { blocs });
    const premier = !Accueil._quand;
    recevoirAccueil(blocs);
    Accueil._quand = Date.now();
    Accueil._perime = false;
    rendreAccueil();
    if (premier || forcer) animerEntree($("#acc-rangees"));
  } catch (e) {
    if (n !== Accueil._req) return;
    if (!Accueil.blocs) {
      $("#acc-reprendre").innerHTML = "";
      $("#acc-rangees").innerHTML = videHtml("alert", "Impossible de charger les suggestions", e.message,
        `<button type="button" class="btn sm" data-acc-reessayer>${ic("refresh", "s18")}Réessayer</button>`);
    } else if (forcer) toastErr(e);
  }
}

const lienTout = (href, txt = "Tout voir") => `<a class="lien-r" href="${href}">${txt}${ic("chev", "s16")}</a>`;

function htmlBlocReprendre() {
  const carte = PREFS.reprendre !== "rangee";
  const items = carte ? Accueil.reprendre.slice(1) : Accueil.reprendre;
  if (!items.length) return "";
  return htmlRangee(carte ? "Tes autres séries en cours" : "Reprendre", items,
    { cle: "reprendre", lien: lienTout("#bibliotheque/en_cours") });
}

function rendreAccueil() {
  if (!Accueil.blocs) return;
  rendreHeroReprendre();
  const h = Accueil.blocs.map((b) => {
    if (b.cle === "reprendre") return `<div data-bloc="reprendre">${htmlBlocReprendre()}</div>`;
    return htmlRangee(b.titre, b.items, {
      cle: b.cle, cloche: b.cle === "bientot", lien: b.cle === "bientot" ? lienTout("#futur", "Agenda") : "",
    });
  }).join("");
  const box = $("#acc-rangees");
  const vide = !Accueil.blocs.some((b) => b.items.length);
  box.innerHTML = vide
    ? videHtml("sparkle", "Rien à te proposer pour l'instant",
      "Ajoute quelques films ou séries que tu aimes : les suggestions s'en inspirent.",
      `<button type="button" class="btn sm pri" data-palette>${ic("search", "s18")}Chercher un titre</button>`)
    : h;
  majToutesFleches(box);
}

/* --------------------------------------------- carte « Reprendre » (A2) */
function htmlReprendre(t) {
  const code = t.next_saison ? codeEp(t.next_saison, t.next_numero) : "";
  const pct = t.total_ep ? Math.min(100, Math.round((t.vus_ep || 0) / t.total_ep * 100)) : 0;
  let ligne, bouton = "";
  if (code) {
    const bits = [t.next_nom ? `— ${esc(t.next_nom)}` : "", t.next_duree ? `· ${fmtDuree(t.next_duree)}` : ""].filter(Boolean).join(" ");
    ligne = `${t.revoit ? "Tu la revois · " : "Prochain : "}<b>${code}</b> ${bits}`;
    bouton = `<button type="button" class="btn pri" data-res="suivant">${ic("check", "s18")}Marquer ${code} ${t.revoit ? "revu" : "vu"}</button>`;
  } else {
    const pd = t.prochaine_diffusion;
    ligne = pd && pd.date
      ? `Tu es à jour · <b>${codeEp(pd.saison, pd.numero)}</b> ${dans(joursJusqua(pd.date))} (${fmtDate(pd.date)})`
      : "Tu es à jour : aucun épisode diffusé à voir.";
  }
  const fond = t.fond || t.affiche;
  return `<article class="res" data-k="${cleDe(t)}" aria-label="Reprendre ${esc(t.titre)}">
    ${fond ? `<div class="fond" style="background-image:url('${cssUrl(fond)}')"></div>` : ""}
    <div class="in">
      <button type="button" class="aff" data-res="fiche" aria-label="Fiche de ${esc(t.titre)}">${t.affiche ? `<img src="${posterSrc(t.affiche)}" alt="">` : ""}</button>
      <div class="tx">
        <span class="ey">${ic("play", "s16")}Reprendre</span>
        <h2 class="ttl" data-res="fiche">${esc(t.titre)}</h2>
        <p class="res-ep">${ligne}</p>
        ${t.total_ep ? `<div class="barre"><div class="pg"><i style="width:${pct}%"></i></div><span>${nb(t.vus_ep || 0)} / ${nb(t.total_ep)}</span></div>` : ""}
        <div class="bt">${bouton}
          <button type="button" class="btn" data-res="episodes">${ic("list", "s18")}Épisodes</button></div>
      </div>
    </div>
  </article>`;
}

function rendreHeroReprendre() {
  const box = $("#acc-reprendre");
  const t = PREFS.reprendre !== "rangee" ? Accueil.reprendre[0] : null;
  box.innerHTML = t ? htmlReprendre(t) : "";
}

/* Une série regardée remonte en tête ; terminée ou retirée, elle sort. */
function majReprendre(d) {
  const t = TITRES.get("l" + d.lid);
  const liste = Accueil.reprendre;
  const i = liste.findIndex((x) => x.lid === d.lid || x === t);
  const encours = !!t && !d.retire && !!t.lid && t.statut === "en_cours";
  const emp = t ? empreinte(t) : "";
  if (!encours) {
    if (i < 0) return;
    liste.splice(i, 1);
  } else if (i < 0) liste.unshift(t);
  else if (Accueil._etat.get(d.lid) !== emp) { liste.splice(i, 1); liste.unshift(t); }
  if (t) Accueil._etat.set(d.lid, emp);
  rendreHeroReprendre();
  const bloc = $('#acc-rangees [data-bloc="reprendre"]');
  if (bloc) { bloc.innerHTML = htmlBlocReprendre(); majToutesFleches(bloc); }
}

$("#acc-reprendre")?.addEventListener("click", async (e) => {
  const res = e.target.closest(".res");
  const b = e.target.closest("[data-res]");
  if (!res || !b) return;
  const t = TITRES.get(res.dataset.k);
  if (!t) return;
  if (b.dataset.res === "suivant") {
    const ok = await agir(t, "suivant", b);
    if (ok) vibrer();
    return;
  }
  ouvrirFiche(t, { onglet: b.dataset.res === "episodes" ? "episodes" : null });
});

/* ----------------------------------------------------------- réglages */
$("#acc-media")?.addEventListener("click", (e) => {
  const b = e.target.closest("[data-media]");
  if (!b || b.dataset.media === Accueil.media) return;
  Accueil.media = b.dataset.media;
  try { localStorage.setItem("ct-acc-media", Accueil.media); } catch (_) { /* privé */ }
  majSegMedia();
  Accueil.blocs = null;
  Accueil._quand = 0;
  chargerAccueil();
});
$("#acc-actu")?.addEventListener("click", (e) => {
  const b = e.currentTarget;
  if (b.disabled) return;
  b.disabled = true;
  b.querySelector("svg")?.classList.add("tourne");
  chargerAccueil({ forcer: true }).finally(() => {
    b.disabled = false;
    b.querySelector("svg")?.classList.remove("tourne");
  });
});
$("#acc-rangees")?.addEventListener("click", (e) => {
  if (e.target.closest("[data-acc-reessayer]")) chargerAccueil({ forcer: true });
});

document.addEventListener("ct:titre", (e) => {
  const d = e.detail || {};
  if (d.lot) Accueil._perime = true;          // marquage en lot : on recharge au retour
  else if (Accueil.blocs && d.type === "serie" && d.lid) majReprendre(d);
});
document.addEventListener("ct:prefs", (e) => {
  const d = e.detail || {};
  if ("rangees" in d) {          // les rangées viennent du serveur : à recharger
    Accueil._perime = true;
    if (Nav.page === "accueil") chargerAccueil({ forcer: true });
  } else if ("reprendre" in d && Accueil.blocs) rendreAccueil();
});

Pages.accueil = {
  afficher(_sous, { change }) {
    majSegMedia();
    if (!Accueil.blocs || Accueil._perime || Date.now() - Accueil._quand > PERIME_ACCUEIL) chargerAccueil();
    else if (change) majToutesFleches($("#acc-rangees"));
  },
};
