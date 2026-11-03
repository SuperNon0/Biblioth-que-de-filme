/* =========================================================================
   cinéthèque — Futur : l'agenda des sorties au cinéma, jour par jour
   (« Mercredi 4 novembre · dans 6 jours »), rangé par semaines en colonnes
   sur ordinateur (D2). La cloche pose ou retire l'alerte en un geste (D3).
   ========================================================================= */
"use strict";

BULLES.futur = {
  t: "Alertes de sortie",
  d: "Touche la cloche d'un film : le jour de sa sortie, une notification part sur Discord (si elle est réglée dans Paramètres → Discord). Le film rejoint aussi « À voir plus tard ». Un second toucher retire l'alerte.",
};

const Futur = { items: null, filtre: "tout", _quand: 0, _req: 0 };

/* Lundi de la semaine d'une date (ISO). */
function lundiDe(iso) {
  const d = dateDe(iso);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return isoLocal(d);
}
function nomSemaine(lundi) {
  const ecart = Math.round((dateDe(lundi) - dateDe(lundiDe(isoLocal()))) / (7 * 86400000));
  if (ecart <= 0) return "Cette semaine";
  if (ecart === 1) return "La semaine prochaine";
  return `Semaine du ${fmtDate(lundi)}`;
}

function htmlCloche(t) {
  return `<button type="button" class="cloche${t.alerte ? " on" : ""}" data-cloche-f aria-pressed="${t.alerte ? "true" : "false"}"
    aria-label="${t.alerte ? "Retirer l'alerte de sortie" : "M'alerter à la sortie"}" title="${t.alerte ? "Alerte posée" : "M'alerter à la sortie"}">${ic(t.alerte ? "bellon" : "bell")}</button>`;
}
function etatAgenda(t) {
  if (t.alerte) return "Alerte posée";
  if (t.statut === "a_voir") return "Dans « À voir plus tard »";
  if (t.statut) return etiquetteStatut(t);
  return "";
}
function htmlItemAgenda(t) {
  const etat = etatAgenda(t);
  const sous = t.resume ? t.resume : [t.note_tmdb ? "★ " + noteTxt(t.note_tmdb) : "", "Film"].filter(Boolean).join(" · ");
  return `<div class="ag-it" data-k="${cleDe(t)}" tabindex="0" role="button" aria-label="${esc(t.titre)}, sortie le ${esc(fmtDate(t.date_sortie))}">
    <div class="mini">${t.affiche ? `<img src="${posterSrc(t.affiche)}" alt="" loading="lazy" decoding="async">` : ""}</div>
    <div class="tx"><b>${esc(t.titre)}</b><span>${esc(sous)}</span>${etat ? `<span class="st">${esc(etat)}</span>` : ""}</div>
    ${htmlCloche(t)}
  </div>`;
}

function rendreFutur() {
  const box = $("#fut-agenda");
  $$("#fut-filtre [data-f]").forEach((b) => {
    const on = b.dataset.f === Futur.filtre;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
  });
  if (!Futur.items) return;
  const items = Futur.filtre === "alertes" ? Futur.items.filter((t) => t.alerte) : Futur.items;
  if (!items.length) {
    box.innerHTML = Futur.filtre === "alertes"
      ? videHtml("bell", "Aucune alerte posée", "Touche la cloche d'un film à venir pour être prévenu le jour de sa sortie.",
        `<button type="button" class="btn sm" data-fut-tout>Voir toutes les sorties</button>`)
      : videHtml("cal", "Aucune sortie annoncée", "TMDB n'annonce pas encore de film à venir pour la France.");
    return;
  }
  // Semaine → jours → films.
  const semaines = new Map();
  for (const t of items) {
    const jour = String(t.date_sortie).slice(0, 10);
    const lundi = lundiDe(jour);
    if (!semaines.has(lundi)) semaines.set(lundi, new Map());
    const jours = semaines.get(lundi);
    if (!jours.has(jour)) jours.set(jour, []);
    jours.get(jour).push(t);
  }
  box.innerHTML = [...semaines].map(([lundi, jours]) => `<section class="ag-sem" aria-label="${esc(nomSemaine(lundi))}">
      <div class="lbl-mono">${esc(nomSemaine(lundi))}</div>
      ${[...jours].map(([jour, films]) => `<h2 class="ag-j"><b>${esc(fmtJour(jour))}</b><span>${esc(dans(joursJusqua(jour)))}</span></h2>
        ${films.map(htmlItemAgenda).join("")}`).join("")}
    </section>`).join("");
}

async function chargerFutur({ forcer = false } = {}) {
  const my = ++Futur._req;
  const box = $("#fut-agenda");
  if (!Futur.items) {
    const c = cacheGet("futur");
    if (c && Array.isArray(c.items) && Date.now() - (c.t || 0) < 12 * 3600 * 1000) {
      Futur.items = c.items.map(retenir);
      rendreFutur();
    } else box.innerHTML = squeletteLignes(6);
  }
  try {
    const { results = [] } = await api("/api/upcoming");
    if (my !== Futur._req) return;
    if (!CT.imp) cacheSet("futur", { t: Date.now(), items: results });
    const premier = !Futur._quand;
    Futur.items = results.map(retenir);
    Futur._quand = Date.now();
    rendreFutur();
    if (premier || forcer) animerEntree(box);
  } catch (e) {
    if (my !== Futur._req) return;
    if (!Futur.items) box.innerHTML = erreurHtml(e);
    else if (forcer) toastErr(e);
  }
}

/* Une alerte posée ici ou ailleurs (accueil, fiche) : la ligne suit. */
function majAgenda() {
  for (const el of $$("#fut-agenda .ag-it[data-k]")) {
    const t = TITRES.get(el.dataset.k);
    if (!t) continue;
    const tmp = document.createElement("div");
    tmp.innerHTML = htmlItemAgenda(t);
    const neuf = tmp.firstElementChild;
    neuf.dataset.k = el.dataset.k;          // garde la clé connue du registre
    const focus = document.activeElement === el || el.contains(document.activeElement);
    el.replaceWith(neuf);
    if (focus) (neuf.querySelector("[data-cloche-f]") || neuf).focus({ preventScroll: true });
  }
}
document.addEventListener("ct:titre", () => { if (Futur.items) majAgenda(); });

$("#fut-filtre")?.addEventListener("click", (e) => {
  const b = e.target.closest("[data-f]");
  if (!b || b.dataset.f === Futur.filtre) return;
  Futur.filtre = b.dataset.f;
  rendreFutur();
});
$("#fut-agenda")?.addEventListener("click", async (e) => {
  if (e.target.closest("[data-fut-tout]")) { Futur.filtre = "tout"; rendreFutur(); return; }
  const it = e.target.closest(".ag-it[data-k]");
  if (!it) return;
  const t = TITRES.get(it.dataset.k);
  if (!t) return;
  const cloche = e.target.closest("[data-cloche-f]");
  if (cloche) {
    if (await agir(t, "alerte", cloche)) vibrer();
    return;
  }
  ouvrirFiche(t);
});
$("#fut-agenda")?.addEventListener("keydown", (e) => {
  if ((e.key !== "Enter" && e.key !== " ") || !e.target.matches(".ag-it")) return;
  e.preventDefault();
  const t = TITRES.get(e.target.dataset.k);
  if (t) ouvrirFiche(t);
});

Pages.futur = {
  afficher() {
    if (!Futur.items || Date.now() - Futur._quand > 3 * 3600 * 1000) chargerFutur();
    else rendreFutur();
  },
};
