/* =========================================================================
   cinéthèque — actions sur un titre et menu rapide.
   Téléphone : toucher une affiche ouvre une feuille du bas (Q1) avec le gros
   bouton « Marquer S1 · É5 vu ». Ordinateur : le clic ouvre la fiche, le clic
   droit ou ⋯ ouvre un petit menu, et V / A / L / Entrée agissent sur
   l'affiche survolée (Q2). Chaque action propose « Annuler » 5 s (Q3).
   ========================================================================= */
"use strict";

const MODES_INCLUS = new Set(["Abonnement", "Gratuit", "Avec pubs", ""]);

/* Plateformes sans doublons (Netflix / Netflix avec pubs…), les miennes en
   premier avec la mention « Inclus » (F4). */
function plateformesTriees(plats) {
  const vues = new Set(), out = [];
  for (const p of plats || []) {
    const nom = canonPlatform(p.nom);
    const k = nom.toLowerCase();
    if (!nom || vues.has(k)) continue;
    vues.add(k);
    out.push({ ...p, nom, inclus: ownsPlatform(nom) && MODES_INCLUS.has(p.mode || "") });
  }
  return out.sort((a, b) => b.inclus - a.inclus);
}

/* Ajoute le titre à la bibliothèque s'il n'y est pas encore ; renvoie son id. */
async function assurerDansBiblio(t, statut = "a_voir") {
  if (t.lid) return t.lid;
  const r = await api("/api/library", { method: "POST", body: { tmdb_id: t.tmdb_id, type: t.type, statut } });
  t.lid = r.id;
  t.statut = statut;
  t.date_ajout = Math.floor(Date.now() / 1000);
  return t.lid;
}

/* Une série vient d'être ajoutée : ses épisodes arrivent en arrière-plan. On
   patiente (au plus ~20 s) avant de marquer un épisode précis. */
async function attendreEpisodes(lid) {
  for (let i = 0; i < 20; i++) {
    const d = await api(`/api/title/${lid}`);
    if (!d.sync_pending && (d.saisons || []).length) return d;
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("Les épisodes de cette série arrivent encore : réessaie dans un instant.");
}

const apresAnnuler = (t) => () => actualiserTitre(t).catch(() => {});

/* ------------------------------------------------- actions sur un titre */
const Actions = {
  async aVoir(t) {
    if (t.lid && t.statut === "a_voir") { toast("Déjà dans « À voir plus tard »"); return false; }
    let r;
    if (t.lid) r = await api(`/api/library/${t.lid}`, { method: "PATCH", body: { statut: "a_voir" } });
    else {
      r = await api("/api/library", { method: "POST", body: { tmdb_id: t.tmdb_id, type: t.type, statut: "a_voir" } });
      t.lid = r.id;
    }
    toast("Ajouté à « À voir plus tard »", { annuler: r.annuler, apres: apresAnnuler(t) });
    await actualiserTitre(t);
    return true;
  },

  async vu(t) {
    let r, msg;
    if (t.type === "serie") {
      if (t.lid && t.statut === "vu") {
        toast("Série déjà vue : « J'ai revu » est dans sa fiche, onglet Épisodes.");
        return false;
      }
      if (t.lid) r = await api(`/api/title/${t.lid}/mark`, { method: "POST", body: { action: "seen" } });
      else { r = await api("/api/library", { method: "POST", body: { tmdb_id: t.tmdb_id, type: t.type, statut: "vu" } }); t.lid = r.id; }
      msg = "Série marquée vue";
    } else if (t.lid) {
      const avant = dejaVu(t);
      r = await api(`/api/title/${t.lid}/watch`, { method: "POST", body: {} });
      msg = avant ? `Revisionnage enregistré · ×${(t.nb_vues || 1) + 1}` : "Marqué vu";
    } else {
      r = await api("/api/library", { method: "POST", body: { tmdb_id: t.tmdb_id, type: t.type, statut: "vu" } });
      t.lid = r.id;
      msg = "Marqué vu";
    }
    toast(msg, { annuler: r.annuler, apres: apresAnnuler(t) });
    await actualiserTitre(t);
    return true;
  },

  /* Épisode suivant d'une série (1er visionnage ou revisionnage). */
  async suivant(t) {
    if (!t.lid || !t.next_saison) return false;
    const code = codeEp(t.next_saison, t.next_numero);
    const r = await api(`/api/title/${t.lid}/episode/${t.next_saison}/${t.next_numero}/toggle`,
      { method: "POST", body: { action: t.revoit ? "revu" : "seen" } });
    Object.assign(t, ETAT_LOCAL, { lid: t.lid, favori: t.favori, date_ajout: t.date_ajout, dispo: t.dispo }, r.serie || {});
    toast(`${code} vu`, { annuler: r.annuler, apres: apresAnnuler(t) });
    majCartes(t);
    signaler("titre", { lid: t.lid, tmdb_id: t.tmdb_id, type: t.type });
    actualiserTitre(t, { signal: false }).catch(() => {});  // date de diffusion à venir, etc.
    return true;
  },

  async favori(t) {
    const lid = await assurerDansBiblio(t);
    const on = !t.favori;
    const r = await api(`/api/library/${lid}`, { method: "PATCH", body: { favori: on } });
    toast(on ? "Ajouté à tes favoris" : "Retiré de tes favoris", { annuler: r.annuler, apres: apresAnnuler(t) });
    await actualiserTitre(t);
    return true;
  },

  async retirer(t) {
    if (!t.lid) return false;
    const lid = t.lid;
    const r = await api(`/api/library/${lid}`, { method: "DELETE" });
    Object.assign(t, ETAT_LOCAL);
    toast("Retiré de ta bibliothèque", { annuler: r.annuler, apres: () => { t.lid = lid; apresAnnuler(t)(); } });
    majCartes(t);
    signaler("titre", { lid, tmdb_id: t.tmdb_id, type: t.type, retire: true });
    return true;
  },

  /* Alerte de sortie au cinéma (A5, D3) : un toucher la pose, un second la retire. */
  async alerte(t) {
    if (t.alerte && t.lid) {
      await api(`/api/alerts/${t.lid}`, { method: "DELETE" });
      t.alerte = false;
      toast("Alerte retirée");
    } else {
      const r = await api("/api/alerts", { method: "POST", body: { tmdb_id: t.tmdb_id, type: "film", canal: "cine" } });
      t.alerte = true;
      t.lid = r.id || t.lid;
      toast("Alerte posée : tu seras prévenu le jour de la sortie");
    }
    await actualiserTitre(t);
    return true;
  },

  liste: (t) => choisirListes(t),
  fiche: (t) => ouvrirFiche(t),
};

/* Lance une action depuis un bouton (Q4 : grisé + roue jusqu'à la réponse). */
async function agir(t, nom, btn) {
  try { return await occupe(btn, () => Actions[nom](t)); }
  catch (e) { toastErr(e); return false; }
}

/* Actions en plus selon l'endroit de l'affiche (ex. « Retirer de cette
   liste » dans le détail d'une liste) : chaque page peut s'inscrire ici avec
   une fonction (titre, élément) → [{ic, txt, f, dn}]. */
const EXTRAS_MENU = [];
const extrasDe = (t, el) => el ? EXTRAS_MENU.flatMap((fn) => { try { return fn(t, el) || []; } catch (_) { return []; } }) : [];

/* ------------------------------------------------- menu rapide (Q1) */
function ligneEtat(t) {
  if (!t.lid) return "Pas encore dans ta bibliothèque";
  if (t.type === "serie" && t.total_ep && t.statut !== "vu") {
    return `En cours · <b class="p">${t.vus_ep} / ${pluriel(t.total_ep, "épisode")}</b>`;
  }
  if (t.statut === "vu") {
    const fois = t.type === "film" && t.nb_vues > 1 ? ` · ×${t.nb_vues}` : "";
    return (t.type === "serie" ? "Série vue" : "Vu") + fois;
  }
  if (t.date_ajout) return `Dans ta bibliothèque depuis le ${fmtDate(isoDeTs(t.date_ajout), { annee: true })}`;
  return "Dans ta bibliothèque";
}

let menuOuvert = null;

function ouvrirMenu(t, { depuis = null } = {}) {
  if (menuOuvert && !menuOuvert.ferme) menuOuvert.fermer();
  const extras = extrasDe(t, depuis);
  const f = feuille({ classe: "menu-q" });
  menuOuvert = f;
  let plats = null;   // null : en cours de chargement
  const ctrl = new AbortController();

  const rendre = () => {
    const sortie = t.type === "film" && aVenir(t.date_sortie) && !dejaVu(t);
    const suivant = t.type === "serie" && t.lid && t.next_saison;
    const vuOn = dejaVu(t);
    const meta = [libType(t), t.annee, t.note_tmdb ? "★ " + noteTxt(t.note_tmdb) : ""].filter(Boolean).join(" · ");
    let grand = "";
    if (suivant) {
      const sous = [t.next_nom ? `« ${t.next_nom} »` : "", fmtDuree(t.next_duree)].filter(Boolean).join(" · ");
      grand = `<button type="button" class="btn pri w deux q-grand" data-q="suivant">
        <span>${ic("check", "s18")} ${t.revoit ? "Revu" : "Marquer"} ${codeEp(t.next_saison, t.next_numero)} ${t.revoit ? "" : "vu"}</span>
        ${sous ? `<span class="sub">${esc(sous)}</span>` : ""}</button>`;
    }
    const tuileVu = sortie
      ? `<button type="button" class="qt${t.alerte ? " on" : ""}" data-q="alerte">${ic(t.alerte ? "bellon" : "bell")}${t.alerte ? "Alerte posée" : "M'alerter"}</button>`
      : `<button type="button" class="qt${vuOn ? " on" : ""}" data-q="vu">${ic(vuOn ? "checks" : "check")}${vuOn ? (t.type === "film" && t.nb_vues > 1 ? `Vu ×${t.nb_vues}` : "Vu") : (t.lid ? "Vu" : "Déjà vu")}</button>`;
    let ou = "";
    if (plats === null) ou = `<div class="q-ou"><span class="lbl-mono">Où regarder</span><span class="sk ln" style="width:120px"></span></div>`;
    else if (plats.length) {
      const vis = plats.slice(0, 5);
      ou = `<div class="q-ou"><span class="lbl-mono">Où regarder</span>${vis.map((p) =>
        `<img src="${posterSrc(p.logo)}" alt="${esc(p.nom)}" title="${esc(p.nom)}${p.inclus ? " · inclus" : ""}" loading="lazy">`).join("")}
        ${plats.some((p) => p.inclus) ? `<span class="inclus">${ic("check", "s16")}Inclus</span>` : ""}
        ${plats.length > vis.length ? `<span class="plus">+${plats.length - vis.length}</span>` : ""}</div>`;
    } else if (t.tmdb_id) ou = `<div class="q-ou"><span class="lbl-mono">Où regarder</span><span class="plus">Pas encore en streaming en France</span></div>`;

    f.corps.innerHTML = `<div class="qh">
        <div class="aff">${t.affiche ? `<img src="${posterSrc(t.affiche)}" alt="">` : ""}</div>
        <div class="tx"><span class="ttl">${esc(t.titre)}</span><span>${esc(meta)}</span><span>${ligneEtat(t)}</span></div>
        <button type="button" class="ib" data-fermer aria-label="Fermer">${ic("x")}</button>
      </div>
      ${grand}
      <div class="q-tuiles">
        <button type="button" class="qt${t.statut === "a_voir" ? " on" : ""}" data-q="aVoir">${ic(t.statut === "a_voir" ? "bookmarkon" : "bookmark")}À voir</button>
        ${tuileVu}
        <button type="button" class="qt" data-q="liste">${ic("listplus")}Liste</button>
        <button type="button" class="qt" data-q="fiche">${ic("info")}Fiche</button>
      </div>
      ${ou}
      ${extras.map((x, i) => `<button type="button" class="q-ext${x.dn ? " dn" : ""}" data-qx="${i}">${ic(x.ic)}${esc(x.txt)}</button>`).join("")}
      ${t.lid ? `<button type="button" class="q-retirer" data-q="retirer">${ic("trash")}Retirer de ma bibliothèque</button>` : ""}`;
    f.el.setAttribute("aria-label", t.titre);
  };
  rendre();

  // Où regarder (et état à jour) : chargé en arrière-plan.
  (async () => {
    try {
      let liste = [];
      if (t.lid) {
        const { titre } = await api(`/api/library/${t.lid}`, { signal: ctrl.signal });
        const n = normTitre(titre);
        for (const k of Object.keys(ETAT_LOCAL)) t[k] = n[k];
        liste = titre.plateformes || [];
      } else if (t.tmdb_id) {
        liste = (await api(`/api/preview?tmdb_id=${t.tmdb_id}&type=${t.type}`, { signal: ctrl.signal })).plateformes || [];
      }
      plats = plateformesTriees(liste);
    } catch (e) {
      if (e.name === "AbortError") return;
      plats = [];
    }
    if (!f.ferme) rendre();
  })();

  f.el.addEventListener("click", async (e) => {
    const x = e.target.closest("[data-qx]");
    if (x) { await f.fermer(); extras[Number(x.dataset.qx)].f(); return; }
    const b = e.target.closest("[data-q]");
    if (!b) return;
    const nom = b.dataset.q;
    if (nom === "fiche" || nom === "liste") {
      await f.fermer();
      Actions[nom](t);
      return;
    }
    const ok = await agir(t, nom, b);
    if (!ok || f.ferme) return;
    if (nom === "suivant") {
      // On reste ouvert sur l'épisode d'après, pour enchaîner.
      if (t.next_saison) { rendre(); vibrer(); return; }
      toast("Tout est vu 🎉");
    }
    f.fermer();
  });
  const fermerAvant = f.fermer;
  f.fermer = () => { ctrl.abort(); return fermerAvant(); };
  return f;
}

/* ---------------------------------------- menu flottant (ordinateur, Q2) */
let popOuverte = null;
function fermerPop() { if (popOuverte) popOuverte.fermer(); }

function ouvrirPop(t, { x, y, ancre = null, depuis = null } = {}) {
  fermerPop();
  const extras = extrasDe(t, depuis || ancre);
  const el = document.createElement("div");
  el.className = "pop";
  el.setAttribute("role", "menu");
  el.setAttribute("aria-label", t.titre);
  const sortie = t.type === "film" && aVenir(t.date_sortie) && !dejaVu(t);
  const items = [];
  if (t.type === "serie" && t.lid && t.next_saison) {
    items.push(["suivant", "check", `${t.revoit ? "Revu" : "Marquer"} ${codeEp(t.next_saison, t.next_numero)}${t.revoit ? "" : " vu"}`, "V"]);
  }
  items.push(["aVoir", t.statut === "a_voir" ? "bookmarkon" : "bookmark", "À voir plus tard", "A", t.statut === "a_voir"]);
  if (sortie) items.push(["alerte", t.alerte ? "bellon" : "bell", t.alerte ? "Retirer l'alerte" : "M'alerter à la sortie", ""]);
  else if (t.type === "film") items.push(["vu", "check", dejaVu(t) ? "J'ai revu ce film" : "Marquer vu", t.type === "film" ? "V" : ""]);
  else if (t.statut !== "vu") items.push(["vu", "checks", "Marquer toute la série vue", t.next_saison && t.lid ? "" : "V"]);
  items.push(["liste", "listplus", "Ajouter à une liste…", "L"]);
  items.push(["fiche", "info", "Ouvrir la fiche", "Entrée"]);
  if (t.lid || extras.length) items.push(null);
  extras.forEach((x, i) => items.push([`x${i}`, x.ic, x.txt, "", false, !!x.dn]));
  if (t.lid) {
    items.push(["favori", t.favori ? "heartfill" : "heart", t.favori ? "Retirer des favoris" : "Ajouter aux favoris", ""]);
    items.push(["retirer", "trash", "Retirer de ma bibliothèque", "", false, true]);
  }
  el.innerHTML = `<div class="pop-t">${esc(t.titre)}</div>` + items.map((it) => it === null ? '<div class="msep"></div>'
    : `<button type="button" class="mi${it[4] ? " on" : ""}${it[5] ? " dn" : ""}" role="menuitem" data-q="${it[0]}">${ic(it[1])}<span>${esc(it[2])}</span>${it[3] ? `<span class="k">${it[3]}</span>` : ""}</button>`).join("");
  document.body.append(el);
  if (ancre) {
    const r = ancre.getBoundingClientRect();
    x = r.right - el.offsetWidth; y = r.bottom + 6;
  }
  el.style.left = `${Math.max(8, Math.min(x, innerWidth - el.offsetWidth - 8))}px`;
  el.style.top = `${Math.max(8, y + el.offsetHeight > innerHeight - 8 ? y - el.offsetHeight : y)}px`;
  const avant = document.activeElement;
  let ferme = false;
  const retirer = () => {
    if (ferme) return;
    ferme = true;
    el.remove();
    document.removeEventListener("pointerdown", dehors, true);
    if (popOuverte && popOuverte.el === el) popOuverte = null;
    if (avant && avant.focus && document.contains(avant)) avant.focus({ preventScroll: true });
  };
  const couche = Couches.ouvrir(retirer, { el });
  const p = { el, fermer: () => (ferme ? Promise.resolve() : Couches.fermer(couche)) };
  popOuverte = p;
  const dehors = (e) => { if (!el.contains(e.target)) p.fermer(); };
  setTimeout(() => document.addEventListener("pointerdown", dehors, true), 0);
  el.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-q]");
    if (!b) return;
    await p.fermer();
    const q = b.dataset.q;
    if (q[0] === "x") { extras[Number(q.slice(1))].f(); return; }
    if (q === "fiche" || q === "liste") { Actions[q](t); return; }
    agir(t, q, null);
  });
  // Flèches haut/bas dans le menu.
  el.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const bts = $$(".mi", el);
    const i = bts.indexOf(document.activeElement);
    bts[(i + (e.key === "ArrowDown" ? 1 : -1) + bts.length) % bts.length].focus();
  });
  el.querySelector(".mi")?.focus({ preventScroll: true });
  return p;
}

/* ------------------------------------------- ajouter à une liste (L2) */
async function choisirListes(t) {
  let lid;
  try {
    const ajoute = !t.lid;
    lid = await assurerDansBiblio(t);
    if (ajoute) { toast("Ajouté à ta bibliothèque (à voir)"); actualiserTitre(t).catch(() => {}); }
  } catch (e) { toastErr(e); return; }
  const f = feuille({ titre: "Ajouter à une liste", html: squeletteLignes(3) });
  const rendre = async () => {
    try {
      const { listes } = await api(`/api/lists?titre_id=${lid}`);
      if (f.ferme) return;
      f.corps.innerHTML = `<p class="muted petit" style="margin-bottom:6px">${esc(t.titre)}</p>
        <div class="cases">${listes.map((l) => `<label class="case">
          <input type="checkbox" data-liste="${l.id}" data-nom="${esc(l.nom)}"${l.contient ? " checked" : ""}>
          <span class="ck sq">${ic("check", "s16")}</span>
          <span class="tx"><b>${esc(l.nom)}</b><span>${pluriel(l.nb, "titre")}${l.systeme === "a_voir" ? " · suit le statut « à voir »" : l.systeme === "favoris" ? " · suit le cœur" : l.ordonnee ? " · dans l'ordre" : ""}</span></span>
        </label>`).join("")}</div>
        <form class="ligne" data-nouvelle>
          <input class="input" name="nom" placeholder="Nouvelle liste" autocomplete="off" aria-label="Nom de la nouvelle liste" maxlength="80">
          <button class="btn pri" type="submit">${ic("plus", "s18")}Créer</button>
        </form>`;
    } catch (e) { f.corps.innerHTML = erreurHtml(e); }
  };
  await rendre();
  f.el.addEventListener("change", async (e) => {
    const c = e.target.closest("input[data-liste]");
    if (!c) return;
    const on = c.checked, id = c.dataset.liste, nom = c.dataset.nom;
    c.disabled = true;
    try {
      if (on) await api(`/api/lists/${id}/items`, { method: "POST", body: { titre_id: lid } });
      else await api(`/api/lists/${id}/items/${lid}`, { method: "DELETE" });
      toast(on ? `Ajouté à « ${nom} »` : `Retiré de « ${nom} »`);
      signaler("listes", { id: Number(id) });
      actualiserTitre(t).catch(() => {});  // « Favoris » suit le cœur
    } catch (err) { c.checked = !on; toastErr(err); }
    finally { c.disabled = false; }
  });
  f.el.addEventListener("submit", async (e) => {
    const form = e.target.closest("[data-nouvelle]");
    if (!form) return;
    e.preventDefault();
    const nom = form.nom.value.trim();
    if (!nom) { form.nom.focus(); return; }
    await occupe(form.querySelector("button"), async () => {
      try {
        const r = await api("/api/lists", { method: "POST", body: { nom } });
        await api(`/api/lists/${r.id}/items`, { method: "POST", body: { titre_id: lid } });
        toast(`Liste « ${nom} » créée avec ce titre`);
        signaler("listes", { id: r.id });
        await rendre();
      } catch (err) { toastErr(err); }
    });
  });
}

/* ------------------------------------------------ clics sur les affiches */
/* Affiche ou ligne de liste : souris → la fiche ; doigt → le menu rapide (Q2). */
const SEL_TITRE = ".po[data-k], .lt[data-k]";
function activerTitre(t, depuis = null) {
  if (pointeurFin() && dernierPointeur !== "touch") ouvrirFiche(t);
  else ouvrirMenu(t, { depuis });
}
document.addEventListener("click", (e) => {
  if (e.defaultPrevented) return;
  const po = e.target.closest(SEL_TITRE);
  if (!po || po.closest(".selection")) return;
  const t = TITRES.get(po.dataset.k);
  if (!t) return;
  e.preventDefault();
  const cloche = e.target.closest("[data-cloche]");
  if (cloche) { agir(t, "alerte", cloche); return; }
  const more = e.target.closest("[data-more]");
  if (more) { ouvrirPop(t, { ancre: more, depuis: po }); return; }
  activerTitre(t, po);
});
document.addEventListener("contextmenu", (e) => {
  const po = e.target.closest(SEL_TITRE);
  if (!po || e.defaultPrevented || po.closest(".selection")) return;
  const t = TITRES.get(po.dataset.k);
  if (!t) return;
  e.preventDefault();
  if (dernierPointeur === "touch") ouvrirMenu(t, { depuis: po });
  else ouvrirPop(t, { x: e.clientX, y: e.clientY, depuis: po });
});

/* Raccourcis sur l'affiche survolée ou sélectionnée au clavier (Q2). */
let poSurvolee = null;
document.addEventListener("pointerover", (e) => {
  if (e.pointerType === "mouse") poSurvolee = e.target.closest(SEL_TITRE);
});
const enSaisie = (el) => el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey || enSaisie(document.activeElement)) return;
  const po = (document.activeElement && document.activeElement.closest && document.activeElement.closest(SEL_TITRE))
    || (poSurvolee && document.contains(poSurvolee) && poSurvolee.matches(":hover") ? poSurvolee : null);
  if (!po || po.closest(".selection")) return;
  // Une affiche sous une feuille ou un menu ouvert n'est pas visée (une
  // sous-page, comme le détail d'une liste, ne compte pas).
  const fiche = po.closest(".fiche");
  const dessus = [...Couches.pile].reverse().find((c) => !c.vue);
  if (dessus && !(fiche && dessus.el === fiche)) return;
  const t = TITRES.get(po.dataset.k);
  if (!t) return;
  const k = e.key.toLowerCase();
  let nom = null;
  if (e.key === "Enter" || e.key === " ") nom = pointeurFin() ? "fiche" : null;
  else if (k === "v") nom = t.type === "serie" && t.lid && t.next_saison ? "suivant" : (t.type === "film" && aVenir(t.date_sortie) ? null : "vu");
  else if (k === "a") nom = "aVoir";
  else if (k === "l") nom = "liste";
  if (!nom) {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ouvrirMenu(t, { depuis: po }); }
    return;
  }
  e.preventDefault();
  if (nom === "fiche" || nom === "liste") Actions[nom](t);
  else agir(t, nom, null);
});
