/* =========================================================================
   cinéthèque — Profil : tuiles (P1) dont le temps total avec son calcul
   dans une bulle « ? », titres vus par année de sortie (P2), temps par
   série et partage films / séries (P3), genres en français (P4), records,
   et le journal regroupé en séances, avec les doublons signalés (P5).
   ========================================================================= */
"use strict";

BULLES.journal = {
  t: "Journal",
  d: "Chaque visionnage noté, du plus récent au plus ancien. Les épisodes regardés à la suite sont regroupés en une séance. Une ligne notée deux fois est signalée : tu peux la retirer du journal, tes épisodes vus ne changent pas.",
};

const Profil = { stats: null, events: [], suite: false, _perime: true, _req: 0 };
document.addEventListener("ct:titre", () => { Profil._perime = true; if (Nav.page === "profil") majProfilBientot(); });
const majProfilBientot = plusTard(() => chargerProfil(), 900);

/* ----------------------------------------------------------- statistiques */
function htmlStats(s) {
  const T = s.temps_total || {};
  const R = s.repartition || {};
  BULLES.temps = {
    t: "Temps total",
    d: "Tout ce que tu as regardé, revisionnages compris. Sans durée connue, un épisode compte pour 42 minutes et un film pour 1 h 40.",
    k: "Le calcul",
    pre: `films vus × leur durée      ${R.films_texte || "0 min"}\n+ épisodes vus × leur durée ${R.series_texte || "0 min"}\n(chaque revisionnage compte)\n= ${T.texte || "0 min"}`,
  };
  const rev = s.revisionnages || {};
  const rec = s.records || {};
  const totalMin = (R.films_min || 0) + (R.series_min || 0);
  // Records : le film et la série les plus revus, réunis dans une tuile.
  const ligneRec = (r, nom) => r && r.n > 1 ? `<div class="rec-l"><div class="mini">${r.affiche ? `<img src="${posterSrc(r.affiche)}" alt="" loading="lazy">` : ""}</div>
      <div class="tx"><span>${esc(nom)}</span><b>${esc(r.titre)}</b><span>vu ${nb(r.n)} fois</span></div></div>` : "";
  const recs = ligneRec(rec.film_plus_revu, "Film") + ligneRec(rec.serie_plus_revue, "Série");
  const tuiles = `<div class="tuiles">
    <div class="tuile big"><div class="k">${ic("clock", "s16")}Temps total
        <button type="button" class="q" data-q="temps" aria-label="Comment c'est calculé">?</button></div>
      <div class="v">${esc(T.texte || "0 min")}</div>
      <div class="s">soit ${esc(T.converti || "0 min")}</div>
      ${totalMin ? `<div class="split" role="img" aria-label="Films ${esc(R.films_texte)}, séries ${esc(R.series_texte)}">
          <i class="f" style="flex:${R.films_min || 0}"></i><i class="s" style="flex:${R.series_min || 0}"></i></div>
        <div class="leg"><span><i class="f"></i>Films · ${esc(R.films_texte)}</span><span><i class="s"></i>Séries · ${esc(R.series_texte)}</span></div>` : ""}
    </div>
    <div class="tuile"><div class="k">${ic("film", "s16")}Films vus</div><div class="v">${nb(s.nb_films)}</div>
      <div class="s">${rev.films ? `${pluriel(rev.films, "revu")} plusieurs fois` : "&nbsp;"}</div></div>
    <div class="tuile"><div class="k">${ic("tv", "s16")}Séries</div><div class="v">${nb(s.nb_series)}</div>
      <div class="s">${pluriel(s.nb_episodes, "épisode vu", "épisodes vus")}</div></div>
    <div class="tuile"><div class="k">${ic("rotate", "s16")}Revisionnages</div><div class="v">${nb((rev.films || 0) + (rev.series || 0))}</div>
      <div class="s">${pluriel(rev.films || 0, "film")} · ${pluriel(rev.series || 0, "série")}</div></div>
    <div class="tuile recs"><div class="k">${ic("staron", "s16")}Les plus revus</div>
      ${recs || `<div class="s">Aucun titre revu pour l'instant.</div>`}</div>
  </div>`;

  // Titres vus par année de sortie (P2) ; regroupés par décennie au-delà de 40 ans.
  let annees = "";
  const pa = (s.par_annee || []).filter((r) => r.annee);
  if (pa.length) {
    const min = pa[0].annee, max = pa[pa.length - 1].annee;
    const parDecennie = max - min > 40;
    const seaux = new Map();
    if (parDecennie) { for (let d = Math.floor(min / 10) * 10; d <= max; d += 10) seaux.set(d, 0); }
    else { for (let a = min; a <= max; a++) seaux.set(a, 0); }
    for (const r of pa) {
      const k = parDecennie ? Math.floor(r.annee / 10) * 10 : r.annee;
      seaux.set(k, (seaux.get(k) || 0) + r.n);
    }
    const vals = [...seaux];
    const haut = Math.max(...vals.map(([, n]) => n), 1);
    const [pic] = vals.reduce((m, v) => (v[1] > m[1] ? v : m), vals[0]);
    const lib = (k) => parDecennie ? `années ${k}` : String(k);
    const repere = [vals[0][0], vals[Math.floor(vals.length / 2)][0], vals[vals.length - 1][0]];
    annees = `<div class="bloc"><h3 class="fi-h3">${ic("cal", "s18")}Par année de sortie</h3>
      <p class="muted petit" style="margin:-4px 0 12px">Tes titres vus, selon l'année où ils sont sortis. Le plus de titres : <b>${esc(lib(pic))}</b>.</p>
      <div class="vb" role="img" aria-label="Titres vus par ${parDecennie ? "décennie" : "année"} de sortie, le plus : ${esc(lib(pic))}">
        ${vals.map(([k, n]) => `<i${k === pic ? "" : " class=\"dim\""} style="height:${Math.max(2, Math.round(n / haut * 100))}%" title="${esc(lib(k))} : ${pluriel(n, "titre")}"></i>`).join("")}
      </div>
      <div class="vbx">${repere.map((k) => `<span>${parDecennie ? k + "s" : k}</span>`).join("")}</div></div>`;
  }

  // Séries qui t'ont pris le plus de temps (P3).
  let series = "";
  const top = s.top_series_temps || [];
  if (top.length) {
    const hautS = Math.max(...top.map((x) => x.minutes), 1);
    series = `<div class="bloc"><h3 class="fi-h3">${ic("tv", "s18")}Le temps par série</h3>
      <div class="hb">${top.map((x) => `<span class="l lien-t" data-pro-titre="${x.id}" data-type="serie" title="${esc(x.titre)}">${esc(x.titre)}</span>
        <span class="b alt" style="width:${Math.max(2, Math.round(x.minutes / hautS * 100))}%"></span><span class="n">${esc(x.texte)}</span>`).join("")}</div></div>`;
  }
  // Genres (P4).
  let genres = "";
  const gs = s.genres || [];
  if (gs.length) {
    const hautG = Math.max(...gs.map((g) => g.n), 1);
    genres = `<div class="bloc"><h3 class="fi-h3">${ic("sparkle", "s18")}Tes genres</h3>
      <div class="hb">${gs.map((g) => `<span class="l">${esc(g.nom)}</span><span class="b" style="width:${Math.max(2, Math.round(g.n / hautG * 100))}%"></span>
        <span class="n">${nb(g.n)}</span>`).join("")}</div></div>`;
  }
  if (!s.nb_films && !s.nb_series) {
    return tuiles + videHtml("chart", "Pas encore de statistiques",
      "Marque des films ou des épisodes comme vus : le temps passé et tes goûts s'afficheront ici.");
  }
  return `${tuiles}<div class="profil-g">${annees ? `<div class="large">${annees}</div>` : ""}${series}${genres}</div>`;
}

/* ------------------------------------------------------- journal (P5) */
function seancesDe(events) {
  // Épisodes d'une même série notés à la suite, le même jour → une séance.
  const out = [];
  for (const e of events) {
    const jour = isoDeTs(e.cree);
    const der = out[out.length - 1];
    if (der && e.type === "episode" && der.type === "episode" && der.titre_id === e.titre_id && der.jour === jour) {
      der.events.push(e);
      continue;
    }
    out.push({ type: e.type, titre_id: e.titre_id, titre: e.titre, affiche: e.affiche, media: e.media, jour, events: [e] });
  }
  return out;
}
function libelleSeance(g) {
  const evs = g.events;
  if (g.type === "episode") {
    const eps = evs.filter((e) => e.saison).slice().sort((a, b) => a.saison - b.saison || a.numero - b.numero);
    const duree = evs.reduce((m, e) => m + (e.duree || DUREE_EP_DEFAUT), 0);
    if (eps.length > 1) {
      const a = eps[0], z = eps[eps.length - 1];
      const plage = a.saison === z.saison ? `${codeEp(a.saison, a.numero)} → É${z.numero}` : `${codeEp(a.saison, a.numero)} → ${codeEp(z.saison, z.numero)}`;
      return `${plage} · ${pluriel(evs.length, "épisode")} · ${fmtDuree(duree)}`;
    }
    const e = evs[0];
    const nom = (e.label || "").split(" — ")[1] || "";
    return [e.saison ? codeEp(e.saison, e.numero) : e.label, nom, fmtDuree(e.duree || DUREE_EP_DEFAUT)].filter(Boolean).join(" · ");
  }
  const e = evs[0];
  if (g.type === "film") return ["Film vu", fmtDuree(e.duree)].filter(Boolean).join(" · ");
  if (g.type === "saison") return e.label ? `${e.label} marquée vue` : "Saison marquée vue";
  if (g.type === "serie") return "Série entière marquée vue";
  return e.label || "";
}
/* Doublons : la même ligne notée deux fois le même jour. */
function doublonsDe(events) {
  const vus = new Map(), doublons = new Set();
  for (const e of events.slice().reverse()) {      // du plus ancien au plus récent
    const k = `${e.titre_id}|${e.type}|${e.label || ""}|${isoDeTs(e.cree)}`;
    if (e.type === "film" || !e.label) continue;    // un film revu le même jour est possible
    if (vus.has(k)) doublons.add(e.id); else vus.set(k, e.id);
  }
  return doublons;
}
function jourJournal(iso) {
  const n = joursJusqua(iso);
  if (n === 0) return "Aujourd'hui";
  if (n === -1) return "Hier";
  return fmtJour(iso) + (dateDe(iso).getFullYear() !== new Date().getFullYear() ? ` ${dateDe(iso).getFullYear()}` : "");
}
function rendreJournal() {
  const box = $("#pro-journal");
  if (!Profil.events.length) {
    box.innerHTML = videHtml("clock", "Journal vide", "Chaque film ou épisode marqué vu s'inscrit ici, avec la date et l'heure.");
    box.classList.add("sans-ligne");
    $("#pro-journal-plus").hidden = true;
    return;
  }
  box.classList.remove("sans-ligne");
  const doublons = doublonsDe(Profil.events);
  let html = "", jour = null;
  for (const g of seancesDe(Profil.events)) {
    if (g.jour !== jour) { jour = g.jour; html += `<div class="d">${esc(jourJournal(jour))}</div>`; }
    const ids = g.events.map((e) => e.id);
    const dbl = g.events.filter((e) => doublons.has(e.id));
    html += `<div class="e${dbl.length ? " anomalie" : ""}" data-titre="${g.titre_id}" data-type="${esc(g.media)}" data-ids="${ids.join(",")}" role="button" tabindex="0">
      <div class="mini">${g.affiche ? `<img src="${posterSrc(g.affiche)}" alt="" loading="lazy">` : ""}</div>
      <div class="tx"><b>${esc(g.titre)}</b><span>${esc(libelleSeance(g))}</span>
        ${dbl.length ? `<div class="alerte-j">${ic("alert", "s16")}${dbl.length > 1 ? `${dbl.length} lignes notées deux fois` : "Noté deux fois"}
          <button type="button" data-pro-doublon="${dbl.map((e) => e.id).join(",")}">Retirer le doublon</button></div>` : ""}</div>
      <span class="h">${esc(fmtHeure(g.events[0].cree))}</span>
      <button type="button" class="ib" data-pro-menu aria-label="Actions">${ic("dots", "s18")}</button>
    </div>`;
  }
  box.innerHTML = html;
  $("#pro-journal-plus").hidden = !Profil.suite;
}

async function chargerJournal({ plus = false } = {}) {
  const avant = plus && Profil.events.length ? Profil.events[Profil.events.length - 1].cree : null;
  const d = await api(`/api/journal?limite=150${avant ? `&avant=${avant}` : ""}`);
  Profil.events = plus ? Profil.events.concat(d.events || []) : (d.events || []);
  Profil.suite = !!d.suite;
  rendreJournal();
}

async function chargerProfil() {
  const my = ++Profil._req;
  if (!Profil.stats) {
    $("#pro-stats").innerHTML = `<div class="tuiles">${'<div class="sk" style="height:96px;border-radius:14px"></div>'.repeat(4)}</div>`;
    $("#pro-journal").innerHTML = squeletteLignes(4);
  }
  try {
    const [stats] = await Promise.all([api("/api/stats"), chargerJournal()]);
    if (my !== Profil._req) return;
    const premier = !Profil.stats;
    Profil.stats = stats;
    Profil._perime = false;
    $("#pro-stats").innerHTML = htmlStats(stats);
    if (premier) animerEntree($("#pro-stats .tuiles"));
  } catch (e) {
    if (my !== Profil._req) return;
    if (!Profil.stats) $("#pro-stats").innerHTML = erreurHtml(e);
    else toastErr(e);
  }
}

async function retirerDuJournal(ids, { confirmerAvant = true } = {}) {
  if (confirmerAvant) {
    const ok = await confirmer(ids.length > 1 ? `Retirer ces ${ids.length} lignes du journal ?` : "Retirer cette ligne du journal ?", {
      ok: "Retirer", danger: true, detail: "Seul le journal change : le titre, ses épisodes vus et le temps total restent les mêmes." });
    if (!ok) return;
  }
  let n = 0;
  for (const id of ids) {
    try { await api(`/api/journal/${id}`, { method: "DELETE" }); n++; } catch (_) { /* déjà retirée */ }
  }
  Profil.events = Profil.events.filter((e) => !ids.includes(e.id));
  rendreJournal();
  toast(n > 1 ? `${n} lignes retirées du journal` : "Ligne retirée du journal");
}

$("#pro-journal")?.addEventListener("click", (e) => {
  const dbl = e.target.closest("[data-pro-doublon]");
  if (dbl) { retirerDuJournal(dbl.dataset.proDoublon.split(",").map(Number), { confirmerAvant: false }); return; }
  const ligne = e.target.closest(".e[data-titre]");
  if (!ligne) return;
  const g = { lid: Number(ligne.dataset.titre), type: ligne.dataset.type };
  const ids = ligne.dataset.ids.split(",").map(Number);
  const t = titreLocal(g.lid, { type: g.type, titre: ligne.querySelector("b").textContent });
  const menu = e.target.closest("[data-pro-menu]");
  if (menu) {
    menuAdapte([["fiche", "info", "Ouvrir la fiche"],
      ["retirer", "trash", ids.length > 1 ? `Retirer ces ${ids.length} lignes du journal` : "Retirer du journal", true]],
    menu, (a) => { if (a === "fiche") ouvrirFiche(t); else retirerDuJournal(ids); }, t.titre);
    return;
  }
  ouvrirFiche(t);
});
$("#pro-journal")?.addEventListener("keydown", (e) => {
  if ((e.key !== "Enter" && e.key !== " ") || !e.target.matches(".e[data-titre]")) return;
  e.preventDefault();
  e.target.click();
});
$("#pro-stats")?.addEventListener("click", (e) => {
  const l = e.target.closest("[data-pro-titre]");
  if (l) ouvrirFiche(titreLocal(Number(l.dataset.proTitre), { type: l.dataset.type, titre: l.textContent }));
});
$("#pro-journal-plus")?.addEventListener("click", (e) => occupe(e.currentTarget, async () => {
  try { await chargerJournal({ plus: true }); } catch (err) { toastErr(err); }
}));

Pages.profil = {
  afficher() { if (!Profil.stats || Profil._perime) chargerProfil(); },
};
