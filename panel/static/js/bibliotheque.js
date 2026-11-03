/* =========================================================================
   cinéthèque — Bibliothèque : puces avec compteurs et tri (B1), grille,
   liste ou rangées par statut (B2, B3), sélection multiple par appui long
   (B4), recherche instantanée + TMDB + acteurs (B5). Aussi : « Que
   regarder ? » (au hasard) et l'ajout manuel d'un titre absent de TMDB.
   Les filtres travaillent sur MaBiblio (tous les titres chargés une fois).
   ========================================================================= */
"use strict";

const FILTRES_BIB = ["tout", "film", "serie", "en_cours", "a_voir", "vu", "favori"];
const PAR_LOT_BIB = 90;          // affiches dessinées à la fois (le reste au défilement)
const Biblio = {
  f: "tout", genre: "", tri: "ajout", q: "",
  vue: ["grille", "liste", "rangees"].includes(PREFS.vue_biblio) ? PREFS.vue_biblio : "grille",
  choix: null,                   // Set des clés choisies (B4), sinon null
  _liste: [], _n: 0, _obs: null, _ext: 0, _ctrl: null, _sel: null,
};

/* ------------------------------------------------------- filtres et tri */
function filtreBib(f) {
  if (f === "film" || f === "serie") return (t) => t.type === f;
  if (f === "favori") return (t) => t.favori;
  if (f === "tout") return () => true;
  return (t) => t.statut === f;
}
const TRIS_BIB = {
  ajout: (a, b) => (b.date_ajout || 0) - (a.date_ajout || 0),
  titre: (a, b) => String(a.titre).localeCompare(String(b.titre), "fr", { sensitivity: "base", numeric: true }),
  annee: (a, b) => (b.annee || -1) - (a.annee || -1) || TRIS_BIB.titre(a, b),
  note: (a, b) => (b.note_tmdb || -1) - (a.note_tmdb || -1) || TRIS_BIB.titre(a, b),
};

function calculBib() {
  const tous = MaBiblio.titres || [];
  const q = sansAccents(Biblio.q.trim());
  let base = tous;
  if (Biblio.genre) base = base.filter((t) => (t.genres || []).includes(Biblio.genre));
  if (q) base = base.filter((t) => sansAccents(t.titre).includes(q));
  const comptes = { tout: base.length, film: 0, serie: 0, en_cours: 0, a_voir: 0, vu: 0, favori: 0 };
  for (const t of base) {
    if (t.type in comptes) comptes[t.type]++;
    if (t.statut in comptes) comptes[t.statut]++;
    if (t.favori) comptes.favori++;
  }
  const liste = base.filter(filtreBib(Biblio.f)).sort(TRIS_BIB[Biblio.tri] || TRIS_BIB.ajout);
  return { tous, liste, comptes };
}

function majChipsBib(comptes) {
  $$("#bib-chips [data-f]").forEach((b) => {
    const on = b.dataset.f === Biblio.f;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
    const n = b.querySelector(".n");
    if (n) n.textContent = comptes ? nb(comptes[b.dataset.f] || 0) : "";
  });
  $$("#bib-vue [data-vue]").forEach((b) => {
    const on = b.dataset.vue === Biblio.vue;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
  });
}

/* Genres présents dans ma bibliothèque, du plus fréquent au plus rare. */
function majGenresBib(tous) {
  const sel = $("#bib-genre");
  if (!sel) return;
  const compte = new Map();
  for (const t of tous) for (const g of t.genres || []) compte.set(g, (compte.get(g) || 0) + 1);
  const genres = [...compte].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "fr"));
  if (Biblio.genre && !compte.has(Biblio.genre)) Biblio.genre = "";
  sel.innerHTML = `<option value="">Tous les genres</option>` + genres.map(([g, n]) =>
    `<option value="${esc(g)}"${g === Biblio.genre ? " selected" : ""}>${esc(g)} (${nb(n)})</option>`).join("");
}

/* ------------------------------------------------------------- affichage */
function rendreBib({ garder = false } = {}) {
  const box = $("#bib-contenu");
  if (!box) return;
  if (!MaBiblio.titres) { box.innerHTML = `<div class="grille">${squeletteGrille(12)}</div>`; return; }
  const { tous, liste, comptes } = calculBib();
  $("#bib-total").textContent = tous.length ? nb(tous.length) : "";
  majChipsBib(comptes);
  majGenresBib(tous);
  if (Biblio._obs) { Biblio._obs.disconnect(); Biblio._obs = null; }
  Biblio._liste = liste;

  if (!tous.length) {
    box.innerHTML = videHtml("lib", "Ta bibliothèque est vide",
      "Cherche un film ou une série pour l'ajouter, ou pioche dans les suggestions de l'accueil.",
      `<div class="ligne" style="justify-content:center"><button type="button" class="btn sm pri" data-palette>${ic("search", "s18")}Chercher un titre</button>
       <a class="btn sm" href="#decouvrir">${ic("compass", "s18")}Découvrir</a></div>`);
    return;
  }
  if (!liste.length) {
    const filtre = Biblio.f !== "tout" || Biblio.genre;
    box.innerHTML = videHtml("search", "Aucun titre ne correspond",
      Biblio.q.trim() ? `Rien pour « ${Biblio.q.trim()} » dans ta bibliothèque${filtre ? " avec ces filtres" : ""}.` : "Change de filtre ou de genre.",
      filtre ? `<button type="button" class="btn sm" data-bib-effacer>${ic("x", "s18")}Effacer les filtres</button>` : "");
    return;
  }
  const sel = Biblio.choix ? " selection" : "";
  // Rangées par statut (B3) : seulement quand aucun statut n'est filtré.
  if (Biblio.vue === "rangees" && ["tout", "film", "serie", "favori"].includes(Biblio.f)) {
    const groupes = [["en_cours", "En cours"], ["a_voir", "À voir plus tard"], ["vu", "Vus"]];
    box.innerHTML = `<div class="rangees-l${sel}">${groupes.map(([st, nom]) => {
      const items = liste.filter((t) => t.statut === st);
      if (!items.length) return "";
      const lien = items.length > 30 ? `<a class="lien-r" href="#bibliotheque/${st}">Tout voir · ${nb(items.length)}${ic("chev", "s16")}</a>`
        : `<span class="muted petit mono">${nb(items.length)}</span>`;
      return htmlRangee(nom, items.slice(0, 30), { cle: st, lien });
    }).join("")}</div>`;
    majToutesFleches(box);
    marquerChoisis();
    return;
  }
  const n = garder ? Math.max(Biblio._n, PAR_LOT_BIB) : PAR_LOT_BIB;
  Biblio._n = Math.min(n, liste.length);
  const morceau = liste.slice(0, Biblio._n);
  box.innerHTML = Biblio.vue === "liste"
    ? `<div class="liste-t${sel}" id="bib-items">${morceau.map(htmlLigne).join("")}</div>`
    : `<div class="grille${sel}" id="bib-items">${morceau.map((t) => htmlCarte(t)).join("")}</div>`;
  if (Biblio._n < liste.length) suiteBib(box);
  marquerChoisis();
}

/* La suite des affiches arrive quand on approche du bas (grandes bibliothèques). */
function suiteBib(box) {
  const repere = document.createElement("div");
  repere.className = "suite-l";
  repere.setAttribute("aria-hidden", "true");
  box.append(repere);
  if (!("IntersectionObserver" in window)) {
    const reste = Biblio._liste.slice(Biblio._n);
    $("#bib-items").insertAdjacentHTML("beforeend", reste.map((t) => Biblio.vue === "liste" ? htmlLigne(t) : htmlCarte(t)).join(""));
    Biblio._n = Biblio._liste.length;
    repere.remove();
    return;
  }
  Biblio._obs = new IntersectionObserver((entrees) => {
    if (!entrees.some((e) => e.isIntersecting)) return;
    const items = $("#bib-items");
    if (!items) return;
    const lot = Biblio._liste.slice(Biblio._n, Biblio._n + PAR_LOT_BIB);
    items.insertAdjacentHTML("beforeend", lot.map((t) => Biblio.vue === "liste" ? htmlLigne(t) : htmlCarte(t)).join(""));
    Biblio._n += lot.length;
    marquerChoisis();
    if (Biblio._n >= Biblio._liste.length) { Biblio._obs.disconnect(); Biblio._obs = null; repere.remove(); }
  }, { rootMargin: "900px 0px" });
  Biblio._obs.observe(repere);
}

async function chargerBib({ forcer = false } = {}) {
  if (!MaBiblio.titres) rendreBib();
  try {
    await MaBiblio.charger({ forcer });
    rendreBib({ garder: true });
  } catch (e) {
    if (!MaBiblio.titres) $("#bib-contenu").innerHTML = erreurHtml(e);
    else toastErr(e);
  }
}

/* Après un marquage : la bibliothèque se remet à jour un instant plus tard,
   pour ne pas faire disparaître une affiche sous le doigt. */
const rafraichirBib = plusTard(() => {
  if (Nav.page !== "bibliotheque" || Biblio.choix || Couches.pile.some((c) => !c.vue)) {
    if (Nav.page === "bibliotheque") rafraichirBib();
    return;
  }
  chargerBib({ forcer: true });
}, 1500);
document.addEventListener("ct:titre", () => { if (MaBiblio.titres) rafraichirBib(); });

/* ------------------------------------------------- recherche (B5) */
const chercherExtBib = plusTard(async () => {
  const box = $("#bib-ext");
  const q = Biblio.q.trim();
  const my = ++Biblio._ext;
  if (Biblio._ctrl) Biblio._ctrl.abort();
  if (q.length < 2 || !CT.tmdb) { box.innerHTML = ""; return; }
  Biblio._ctrl = new AbortController();
  box.innerHTML = `<div class="sec-h"><h2 class="sec-t">Sur TMDB</h2></div><div class="grille">${squeletteGrille(6)}</div>`;
  try {
    const [tm, pe] = await Promise.all([
      api(`/api/search?q=${encodeURIComponent(q)}`, { signal: Biblio._ctrl.signal }),
      q.length >= 3 ? api(`/api/search/person?q=${encodeURIComponent(q)}`, { signal: Biblio._ctrl.signal }).catch(() => ({ results: [] }))
        : Promise.resolve({ results: [] }),
    ]);
    if (my !== Biblio._ext) return;
    const locaux = new Set(calculBib().liste.map(cleDe));
    const ext = (tm.results || []).map(retenir).filter((t) => !locaux.has(cleDe(t)));
    const pers = (pe.results || []).filter((p) => p.id);
    let h = "";
    if (pers.length) {
      h += `<div class="sec-h"><h2 class="sec-t">${ic("users", "s18")}Personnes</h2></div>
        <div class="cast">${pers.slice(0, 8).map((p) => htmlPersonne(p, p.metier)).join("")}</div>`;
    }
    if (ext.length) {
      h += `<div class="sec-h"><h2 class="sec-t">${ic("sparkle", "s18")}Sur TMDB<span class="muted petit mono">pas encore chez toi</span></h2></div>
        <div class="grille">${ext.map((t) => htmlCarte(t)).join("")}</div>`;
    }
    box.innerHTML = h || `<p class="muted petit" style="text-align:center">Rien d'autre sur TMDB pour « ${esc(q)} ».</p>`;
  } catch (e) {
    if (e.name === "AbortError" || my !== Biblio._ext) return;
    box.innerHTML = `<p class="muted petit" style="text-align:center">${esc(e.message)}</p>`;
  }
}, 380);

/* ----------------------------------------------- sélection multiple (B4) */
function marquerChoisis() {
  $$("#bib-contenu .grille, #bib-contenu .liste-t, #bib-contenu .rangees-l").forEach((x) => x.classList.toggle("selection", !!Biblio.choix));
  $$("#bib-contenu [data-k]").forEach((el) => el.classList.toggle("choisi", !!Biblio.choix && Biblio.choix.has(el.dataset.k)));
}
function majBarreSel() {
  const b = Biblio._sel;
  if (!b) return;
  const n = Biblio.choix.size;
  b.el.querySelector(".compte").textContent = n ? pluriel(n, "choisi") : "Touche des affiches";
  $$("[data-sel]", b.el).forEach((x) => { if (x.dataset.sel !== "fin") x.disabled = !n; });
}
function entrerSelection(premier = null) {
  if (Biblio.choix) { if (premier) basculerChoix(premier); return; }
  Biblio.choix = new Set(premier && premier.dataset.k ? [premier.dataset.k] : []);
  document.body.classList.add("mode-sel");
  const el = document.createElement("div");
  el.className = "barre-act sel";
  el.setAttribute("role", "toolbar");
  el.setAttribute("aria-label", "Titres choisis");
  el.innerHTML = `<button type="button" class="ib" data-sel="fin" aria-label="Terminer la sélection">${ic("x")}</button>
    <span class="compte" aria-live="polite"></span>
    <button type="button" class="btn sm" data-sel="liste" title="Ajouter à une liste" aria-label="Ajouter à une liste">${ic("listplus", "s18")}<span class="lib">Liste</span></button>
    <button type="button" class="btn sm" data-sel="vu" title="Marquer vu" aria-label="Marquer vu">${ic("check", "s18")}<span class="lib">Vu</span></button>
    <button type="button" class="btn sm dn" data-sel="retirer" title="Retirer de ma bibliothèque" aria-label="Retirer de ma bibliothèque">${ic("trash", "s18")}<span class="lib">Retirer</span></button>`;
  document.body.append(el);
  const couche = Couches.ouvrir(() => sortirSelection(), { el, vue: true });
  Biblio._sel = { el, couche };
  el.addEventListener("click", (e) => {
    const b = e.target.closest("[data-sel]");
    if (!b) return;
    if (b.dataset.sel === "fin") { Couches.fermer(couche); return; }
    actionGroupee(b.dataset.sel, b);
  });
  $("#bib-choisir")?.classList.add("on");
  marquerChoisis();
  majBarreSel();
}
function sortirSelection() {
  if (!Biblio.choix) return;
  Biblio.choix = null;
  document.body.classList.remove("mode-sel");
  if (Biblio._sel) Biblio._sel.el.remove();
  Biblio._sel = null;
  $("#bib-choisir")?.classList.remove("on");
  marquerChoisis();
}
function basculerChoix(el) {
  const k = el.dataset.k;
  if (!k || !Biblio.choix) return;
  if (Biblio.choix.has(k)) Biblio.choix.delete(k); else Biblio.choix.add(k);
  el.classList.toggle("choisi", Biblio.choix.has(k));
  vibrer(6);
  majBarreSel();
}

/* Liste / Vu / Retirer pour tous les titres choisis, avec un seul « Annuler ». */
async function actionGroupee(nom, btn) {
  const titres = [...Biblio.choix].map((k) => TITRES.get(k)).filter((t) => t && t.lid);
  if (!titres.length) return;
  if (nom === "liste") { listeGroupee(titres); return; }
  if (nom === "retirer") {
    const ok = await confirmer(`Retirer ${pluriel(titres.length, "titre")} de ta bibliothèque ?`, {
      ok: "Retirer", danger: true, detail: "Leurs épisodes vus et visionnages partent avec eux. « Annuler » reste possible 5 secondes." });
    if (!ok) return;
  }
  await occupe(btn, async () => {
    const jetons = [];
    let echecs = 0;
    for (const t of titres) {
      try {
        let r;
        if (nom === "retirer") r = await api(`/api/library/${t.lid}`, { method: "DELETE" });
        else if (dejaVu(t)) continue;      // déjà vu : pas de revisionnage en lot
        else if (t.type === "serie") r = await api(`/api/title/${t.lid}/mark`, { method: "POST", body: { action: "seen" } });
        else r = await api(`/api/library/${t.lid}`, { method: "PATCH", body: { statut: "vu" } });
        if (r && r.annuler) jetons.push(r.annuler);
      } catch (_) { echecs++; }
    }
    const fait = nom === "retirer" ? `${pluriel(titres.length - echecs, "titre retiré", "titres retirés")}`
      : `${pluriel(jetons.length, "titre marqué vu", "titres marqués vus")}`;
    const apres = async () => { await MaBiblio.charger({ forcer: true }); titres.forEach((t) => actualiserTitre(t, { signal: false }).catch(() => {})); rendreBib({ garder: true }); };
    toast(echecs ? `${fait} · ${echecs} en échec` : fait, { annuler: jetons.length ? jetons : null, apres, erreur: !!echecs && !jetons.length });
    if (Biblio._sel) await Couches.fermer(Biblio._sel.couche);
    await MaBiblio.charger({ forcer: true }).catch(() => {});
    titres.forEach((t) => actualiserTitre(t, { signal: false }).catch(() => {}));
    rendreBib({ garder: true });
    signaler("titre", { lot: true });
  });
}

async function listeGroupee(titres) {
  const f = feuille({ titre: `Ranger ${pluriel(titres.length, "titre")} dans…`, html: squeletteLignes(3) });
  let listes = [];
  const rendre = async () => {
    try {
      ({ listes } = await api("/api/lists"));
      if (f.ferme) return;
      const perso = listes.filter((l) => l.systeme !== "a_voir");
      f.corps.innerHTML = `<div class="liste-r">${perso.map((l) => `<button type="button" class="li" data-liste="${l.id}">
          <span class="li-ic">${ic(l.systeme === "favoris" ? "heart" : l.ordonnee ? "hash" : "list")}</span>
          <span class="tx">${esc(l.nom)}<small>${pluriel(l.nb, "titre")}${l.ordonnee ? " · dans l'ordre" : ""}</small></span>
          ${ic("plus", "s18 muted")}</button>`).join("")}</div>
        <form class="ligne" data-nouvelle style="margin-top:12px">
          <input class="input" name="nom" placeholder="Nouvelle liste" autocomplete="off" aria-label="Nom de la nouvelle liste" maxlength="80">
          <button class="btn pri" type="submit">${ic("plus", "s18")}Créer</button></form>`;
    } catch (e) { f.corps.innerHTML = erreurHtml(e); }
  };
  const ranger = async (id, nom, btn) => occupe(btn, async () => {
    let n = 0;
    for (const t of titres) {
      try { await api(`/api/lists/${id}/items`, { method: "POST", body: { titre_id: t.lid } }); n++; } catch (_) { /* déjà dedans */ }
    }
    toast(`${pluriel(n, "titre rangé", "titres rangés")} dans « ${nom} »`);
    signaler("listes", { id: Number(id) });
    await f.fermer();
    if (Biblio._sel) Couches.fermer(Biblio._sel.couche);
  });
  await rendre();
  f.el.addEventListener("click", (e) => {
    const b = e.target.closest("[data-liste]");
    if (!b) return;
    const l = listes.find((x) => String(x.id) === b.dataset.liste);
    ranger(b.dataset.liste, l ? l.nom : "la liste", b);
  });
  f.el.addEventListener("submit", async (e) => {
    const form = e.target.closest("[data-nouvelle]");
    if (!form) return;
    e.preventDefault();
    const nom = form.nom.value.trim();
    if (!nom) { form.nom.focus(); return; }
    try {
      const r = await api("/api/lists", { method: "POST", body: { nom } });
      await ranger(r.id, nom, form.querySelector("button"));
    } catch (err) { toastErr(err); }
  });
}

/* --------------------------------------------- « Que regarder ? » (roulette) */
function ouvrirRoulette(source = "library", type = "film") {
  const catalogue = source === "catalog";
  const f = feuille({
    titre: catalogue ? "Au hasard dans le catalogue" : "Que regarder ?", large: true, classe: "roulette",
    html: `<p class="muted petit roul-intro">${catalogue ? "Des titres populaires tirés au sort sur TMDB."
      : "Tiré au sort dans ta liste « À voir plus tard »."}</p>
      ${catalogue ? `<div class="seg roul-type" role="group" aria-label="Films ou séries">
        <button type="button" data-type="film">Films</button><button type="button" data-type="serie">Séries</button></div>` : ""}
      <div class="grille roul-g"></div>
      <div class="plus-res"><button type="button" class="btn pri" data-relancer>${ic("dice", "s18")}Relancer</button></div>`,
  });
  const g = f.el.querySelector(".roul-g");
  const nbTitres = () => (ecranLarge() ? 8 : 6);
  const tirer = async () => {
    $$(".roul-type [data-type]", f.el).forEach((b) => b.classList.toggle("on", b.dataset.type === type));
    g.innerHTML = squeletteGrille(nbTitres());
    try {
      const qs = new URLSearchParams({ source, count: String(nbTitres()) });
      if (catalogue) qs.set("type", type);
      const { results = [] } = await api(`/api/roulette?${qs}`);
      if (f.ferme) return;
      g.innerHTML = results.length ? htmlCartes(results) : videHtml("bookmark", "Rien à tirer au sort",
        "Ajoute des titres « À voir plus tard » : le tirage se fera parmi eux.");
      animerEntree(g);
    } catch (e) { g.innerHTML = erreurHtml(e); }
  };
  f.el.addEventListener("click", (e) => {
    const relancer = e.target.closest("[data-relancer]");
    if (relancer) {
      relancer.querySelector("svg")?.classList.add("tourne");
      tirer().finally(() => relancer.querySelector("svg")?.classList.remove("tourne"));
      return;
    }
    const ty = e.target.closest(".roul-type [data-type]");
    if (ty) { type = ty.dataset.type; tirer(); return; }
    // Une affiche choisie : la feuille se ferme avant d'ouvrir la fiche.
    const po = e.target.closest(".po[data-k]");
    if (po && !e.target.closest("[data-more], [data-cloche]")) {
      const t = TITRES.get(po.dataset.k);
      if (!t) return;
      e.preventDefault();
      f.fermer().then(() => activerTitre(t));
    }
  });
  tirer();
  return f;
}

/* --------------------------------------------------- ajout manuel */
function ajoutManuel() {
  const f = feuille({
    titre: "Ajouter un titre absent de TMDB",
    html: `<form class="form" id="am-form">
      <div><label class="lbl" for="am-titre">Titre</label>
        <input class="input" id="am-titre" name="titre" required maxlength="200" autocomplete="off" autofocus></div>
      <div class="ligne am-l">
        <div class="seg" role="group" aria-label="Type"><button type="button" class="on" data-am-type="film">Film</button><button type="button" data-am-type="serie">Série</button></div>
        <div class="seg" role="group" aria-label="Statut"><button type="button" class="on" data-am-statut="a_voir">À voir</button><button type="button" data-am-statut="vu">Déjà vu</button></div>
      </div>
      <div class="ligne am-l">
        <div class="am-c"><label class="lbl" for="am-annee">Année</label>
          <input class="input" id="am-annee" name="annee" type="number" inputmode="numeric" min="1880" max="2100" placeholder="ex. 1998"></div>
        <div class="am-c" data-am-duree><label class="lbl" for="am-duree">Durée (minutes)</label>
          <input class="input" id="am-duree" name="duree" type="number" inputmode="numeric" min="1" max="1000" placeholder="ex. 105"></div>
      </div>
      <div><label class="lbl" for="am-resume">Résumé <span class="muted">(facultatif)</span></label>
        <textarea class="input" id="am-resume" name="resume" rows="3" maxlength="2000"></textarea></div>
      <p class="muted petit">La durée sert au temps total du Profil. Les séries ajoutées à la main n'ont pas d'épisodes.</p>
      <button class="btn pri w" type="submit">${ic("plus", "s18")}Ajouter à ma bibliothèque</button>
    </form>`,
  });
  let type = "film", statut = "a_voir";
  const form = f.el.querySelector("#am-form");
  f.el.addEventListener("click", (e) => {
    const ty = e.target.closest("[data-am-type]");
    if (ty) {
      type = ty.dataset.amType;
      $$("[data-am-type]", f.el).forEach((b) => b.classList.toggle("on", b === ty));
      f.el.querySelector("[data-am-duree]").hidden = type !== "film";
    }
    const st = e.target.closest("[data-am-statut]");
    if (st) {
      statut = st.dataset.amStatut;
      $$("[data-am-statut]", f.el).forEach((b) => b.classList.toggle("on", b === st));
    }
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const titre = form.titre.value.trim();
    if (!titre) { form.titre.focus(); return; }
    await occupe(form.querySelector("[type=submit]"), async () => {
      try {
        const r = await api("/api/library/manual", { method: "POST", body: {
          titre, type, statut, annee: form.annee.value || null,
          duree: type === "film" ? form.duree.value || null : null, resume: form.resume.value.trim() || null } });
        await f.fermer();
        toast(`« ${titre} » ajouté à ta bibliothèque`);
        await MaBiblio.charger({ forcer: true }).catch(() => {});
        rendreBib({ garder: true });
        signaler("titre", { lid: r.id, type });
      } catch (err) { toastErr(err); }
    });
  });
}

/* ----------------------------------------------------------- évènements */
$("#bib-chips")?.addEventListener("click", (e) => {
  const b = e.target.closest("[data-f]");
  if (!b || b.dataset.f === Biblio.f) return;
  Biblio.f = b.dataset.f;
  rendreBib();
});
$("#bib-vue")?.addEventListener("click", (e) => {
  const b = e.target.closest("[data-vue]");
  if (!b || b.dataset.vue === Biblio.vue) return;
  Biblio.vue = b.dataset.vue;
  rendreBib();
  // Le dernier affichage choisi devient celui du démarrage (Paramètres → Apparence).
  enregistrerPrefs({ vue_biblio: Biblio.vue }, { message: "" }).catch(() => {});
});
$("#bib-genre")?.addEventListener("change", (e) => { Biblio.genre = e.target.value; rendreBib(); });
$("#bib-tri")?.addEventListener("change", (e) => { Biblio.tri = e.target.value; rendreBib(); });
$("#bib-q")?.addEventListener("input", (e) => {
  Biblio.q = e.target.value;
  rendreBib();
  chercherExtBib();
});
$("#bib-q")?.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && e.target.value) { e.preventDefault(); e.stopPropagation(); e.target.value = ""; Biblio.q = ""; rendreBib(); chercherExtBib(); }
});
$("#bib-roulette")?.addEventListener("click", () => ouvrirRoulette("library"));
$("#bib-manuel")?.addEventListener("click", () => ajoutManuel());
$("#bib-choisir")?.addEventListener("click", () => {
  if (Biblio.choix && Biblio._sel) Couches.fermer(Biblio._sel.couche);
  else entrerSelection();
});
const _bibContenu = $("#bib-contenu");
// Enregistré avant l'écouteur ci-dessous : le clic qui suit l'appui long est avalé d'abord.
if (_bibContenu) appuiLong(_bibContenu, ".po[data-k], .lt[data-k]", (el) => entrerSelection(el));
$("#bib-contenu")?.addEventListener("click", (e) => {
  if (e.target.closest("[data-bib-effacer]")) {
    Biblio.f = "tout"; Biblio.genre = ""; Biblio.q = "";
    $("#bib-q").value = "";
    rendreBib();
    chercherExtBib();
    return;
  }
  if (!Biblio.choix) return;
  const el = e.target.closest("[data-k]");
  if (!el) return;
  e.preventDefault();
  e.stopPropagation();
  basculerChoix(el);
}, true);

Pages.bibliotheque = {
  afficher(sous, { change }) {
    if (sous) {
      // #bibliotheque/en_cours : ouvre sur ce filtre, puis l'adresse redevient simple.
      if (FILTRES_BIB.includes(sous)) Biblio.f = sous;
      Nav.sous = null;
      history.replaceState(history.state, "", "#bibliotheque");
    }
    if (!MaBiblio.titres || MaBiblio._perimee) chargerBib();
    else if (change || sous) rendreBib({ garder: true });
  },
};
