/* =========================================================================
   cinéthèque — fiche d'un film ou d'une série, et page d'une personne.
   En-tête flouté qui se colle en haut (F1), barre d'actions collée en bas
   (F2), onglets Épisodes / Infos / Casting / Où regarder (F3), mes
   plateformes d'abord (F4), historique du titre (F5), résumé replié et
   casting en ronds (F6). Saisons en accordéon avec anneau (S1), appui long
   « Marquer jusqu'ici » (S2), épisodes à venir à part (S3).
   Chaque fiche est une couche : le bouton retour du téléphone la referme (F7).
   ========================================================================= */
"use strict";

const ONGLETS = [["episodes", "Épisodes"], ["infos", "Infos"], ["casting", "Casting"], ["ou", "Où regarder"]];
const DUREE_EP_DEFAUT = 42;   // minutes, comme les statistiques du serveur (DUREE_EPISODE_DEFAUT)

/* Données de la fiche, qu'elles viennent de ma bibliothèque ou de TMDB. */
function normFiche(d) {
  const t = d.titre;
  const F = {
    lid: t.id, tmdb_id: t.tmdb_id, type: t.type, titre: t.titre, annee: t.annee, date_sortie: t.date_sortie,
    duree: t.duree, resume: t.resume, genres: t.genres || [], note_tmdb: t.note_tmdb, fond: t.fond, affiche: t.affiche,
    bande_annonce: t.bande_annonce, plateformes: t.plateformes || [], casting: t.casting || [], equipe: t.equipe || [],
    pays: t.pays, statut: t.statut, favori: !!t.favori, date_ajout: t.date_ajout, nb_saisons: t.nb_saisons,
    manuel: !!t.ajout_manuel, visionnages: d.visionnages || [], saisons: d.saisons || [],
    prochain: d.prochain_episode || null, temps: d.temps || null, alerte: d.alerte || null,
    journal: d.journal || [], sync: !!d.sync_pending, enBiblio: true,
  };
  F.P = progressionFiche(F);
  return F;
}

/* Série de ma bibliothèque : épisodes diffusés vus / total et prochain à voir
   (un non-vu, sinon le premier moins revu que les autres : revisionnage). */
function progressionFiche(F) {
  if (F.type !== "serie") return null;
  const eps = F.saisons.flatMap((s) => s.episodes || []).filter(estDiffuse);
  if (!eps.length) return { total: 0, vus: 0, next: null, revoit: false };
  const maxi = Math.max(...eps.map((e) => e.nb_vues || 0));
  let next = eps.find((e) => !e.vu) || null, revoit = false;
  if (!next && maxi > 0) { next = eps.find((e) => (e.nb_vues || 0) < maxi) || null; revoit = !!next; }
  return { total: eps.length, vus: eps.filter((e) => e.vu).length, next, revoit };
}
function normApercu(d) {
  const pe = d.prochain_episode;
  return {
    lid: null, tmdb_id: d.tmdb_id, type: d.type, titre: d.titre, annee: d.annee, date_sortie: d.date_sortie,
    duree: d.duree, resume: d.resume, genres: d.genres || [], note_tmdb: d.note_tmdb, fond: d.fond, affiche: d.affiche,
    bande_annonce: d.bande_annonce, plateformes: d.plateformes || [], casting: d.casting || [], equipe: d.equipe || [],
    pays: d.pays, realisateur: d.realisateur, statut: null, favori: false, nb_saisons: d.nb_saisons, P: null,
    nb_episodes: d.nb_episodes, visionnages: [], journal: [], temps: null, alerte: null, sync: false, enBiblio: false,
    saisons: (d.saisons || []).map((s) => ({ numero: s.numero, nom: s.nom, nb: s.nb_episodes || 0, episodes: null })),
    prochain: pe && pe.air_date ? { saison: pe.season_number, numero: pe.episode_number, nom: pe.name, date_diff: pe.air_date } : null,
  };
}

const estDiffuse = (e) => e.diffuse !== undefined ? !!e.diffuse : !!e.date_diff && e.date_diff <= isoLocal();

/* Journal du titre → mini frise (F5) : « 28 octobre : S1 · É1 → É4 ». */
function friseTitre(journal) {
  const jours = new Map();
  for (const ev of journal) {
    const j = isoDeTs(ev.cree);
    if (!jours.has(j)) jours.set(j, []);
    jours.get(j).push(ev);
  }
  const lignes = [];
  for (const [jour, evs] of jours) {
    const parts = [];
    const eps = [];
    for (const ev of evs.slice().reverse()) {
      const m = /^S(\d+)E(\d+)/.exec(ev.label || "");
      if (ev.type === "episode" && m) eps.push([+m[1], +m[2]]);
      else if (ev.type === "saison") parts.push(ev.label || "Saison");
      else if (ev.type === "serie") parts.push("Série entière");
      else if (ev.type === "film") parts.push("Film vu");
    }
    // Épisodes qui se suivent dans une même saison : « S1 · É1 → É4 ».
    const plages = [];
    for (const [s, n] of eps.sort((a, b) => a[0] - b[0] || a[1] - b[1])) {
      const der = plages[plages.length - 1];
      if (der && der.s === s && n <= der.b + 1) der.b = Math.max(der.b, n);
      else plages.push({ s, a: n, b: n });
    }
    for (const p of plages) parts.push(p.a === p.b ? codeEp(p.s, p.a) : `${codeEp(p.s, p.a)} → É${p.b}`);
    if (eps.length > 1) parts.push(pluriel(eps.length, "épisode"));
    lignes.push({ jour, txt: parts.join(" · ") });
  }
  return lignes.slice(0, 8);
}

/* ------------------------------------------------------------ la fiche */
function ouvrirFiche(source, { onglet = null } = {}) {
  const t = source && TITRES.get(cleDe(source)) === source ? source : retenir(source || {});
  const el = document.createElement("div");
  el.className = "fiche";
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-modal", "true");
  el.setAttribute("aria-label", t.titre || "Fiche");
  el.tabIndex = -1;
  const V = { F: null, onglet, extras: {}, charges: new Set(), ctrl: new AbortController(), ferme: false };
  const avant = document.activeElement;
  document.body.append(el);
  const retirer = () => {
    if (V.ferme) return;
    V.ferme = true;
    V.ctrl.abort();
    el.classList.add("sort");
    setTimeout(() => el.remove(), 210);
    if (avant && avant.focus && document.contains(avant)) avant.focus({ preventScroll: true });
  };
  const couche = Couches.ouvrir(retirer, { el });
  const fermer = () => Couches.fermer(couche);

  /* Squelette tout de suite, avec ce qu'on sait déjà (affiche, titre). */
  el.innerHTML = `${htmlBarreHaut(t)}
    <div class="fi-hero"><div class="fond"${t.fond || t.affiche ? ` style="background-image:url('${cssUrl(t.fond || t.affiche)}')"` : ""}></div>
      <div class="fi-head"><div class="aff">${t.affiche ? `<img src="${posterSrc(t.affiche)}" alt="">` : ""}</div>
        <div class="tx"><div class="fi-kick">${esc(libType(t))}${t.annee ? " · " + t.annee : ""}</div><h1 class="fi-t">${esc(t.titre || "")}</h1>
          <div class="sk ln" style="width:140px;margin-top:12px"></div></div></div></div>
    <div class="fi-corps">${squeletteLignes(4)}</div>`;
  setTimeout(() => el.focus({ preventScroll: true }), 40);

  const charger = async () => {
    const d = t.lid ? normFiche(await api(`/api/title/${t.lid}`, { signal: V.ctrl.signal }))
      : normApercu(await api(`/api/preview?tmdb_id=${t.tmdb_id}&type=${t.type}`, { signal: V.ctrl.signal }));
    if (!d.enBiblio && t.lid) return charger();   // ajouté entre-temps
    return d;
  };

  /* Données fraîches puis rendu, en gardant onglet, saisons ouvertes et défilement. */
  async function recharger({ garder = true } = {}) {
    try {
      V.F = await charger();
    } catch (e) {
      if (e.name === "AbortError" || V.ferme) return;
      if (t.lid && /introuvable/i.test(e.message)) {     // retiré ailleurs : aperçu TMDB
        Object.assign(t, ETAT_LOCAL);
        if (t.tmdb_id) return recharger({ garder });
      }
      if (!V.F) { $(".fi-corps", el).innerHTML = erreurHtml(e); return; }
      toastErr(e);
      return;
    }
    if (V.ferme) return;
    rendre({ garder });
    if (V.F.sync) suivreSynchro();
  }

  /* Série en cours de remplissage : on rafraîchit les saisons (≤ 1 min). */
  let essais = 0;
  function suivreSynchro() {
    if (essais++ >= 40) return;
    setTimeout(async () => {
      if (V.ferme || !V.F || !V.F.lid) return;
      try {
        const d = normFiche(await api(`/api/title/${V.F.lid}`, { signal: V.ctrl.signal }));
        if (V.ferme) return;
        V.F = d;
        rendre({ garder: true });
        if (d.sync) suivreSynchro();
        else actualiserTitre(t).catch(() => {});
      } catch (_) { /* on réessaiera à la prochaine ouverture */ }
    }, 1500);
  }

  function ongletParDefaut(F) {
    if (V.onglet && (V.onglet !== "episodes" || F.type === "serie")) return V.onglet;
    return F.type === "serie" && F.enBiblio ? "episodes" : "infos";
  }

  function rendre({ garder = false } = {}) {
    const F = V.F;
    const ouvertes = garder ? new Set($$(".saison.ouverte", el).map((s) => s.dataset.s)) : null;
    const fermees = garder ? new Set($$(".saison:not(.ouverte)", el).map((s) => s.dataset.s)) : null;
    const deplies = garder ? new Set($$(".ep.deplie", el).map((e) => `${e.dataset.s}-${e.dataset.n}`)) : null;
    const focus = document.activeElement && el.contains(document.activeElement) ? cleFocus(document.activeElement) : null;
    const y = el.scrollTop;
    V.onglet = ongletParDefaut(F);
    el.setAttribute("aria-label", F.titre);
    synchroniserCarte(F);
    el.innerHTML = htmlBarreHaut(F) + htmlHero(F, t) + htmlOnglets(F, V.onglet)
      + `<div class="fi-corps">${ONGLETS.filter(([k]) => k !== "episodes" || F.type === "serie").map(([k]) =>
        `<section class="fi-panneau${k === V.onglet ? " on" : ""}" data-p="${k}" role="tabpanel" aria-labelledby="fo-${k}">${htmlPanneau(k, F, t, { ouvertes, fermees })}</section>`).join("")}</div>`
      + htmlActions(F, t);
    if (deplies) deplies.forEach((k) => { const [s, n] = k.split("-"); $(`.ep[data-s="${s}"][data-n="${n}"]`, el)?.classList.add("deplie"); });
    for (const [k, html] of Object.entries(V.extras)) { const box = $(`[data-extra="${k}"]`, el); if (box) box.innerHTML = html; }
    el.scrollTop = garder ? y : 0;
    majToutesFleches(el);
    plierResume();
    if (focus) $(focus, el)?.focus({ preventScroll: true });
    if (V.onglet === "infos") chargerExtras();
    majDefile();
  }

  /* Les affiches de ce titre (page dessous) reprennent l'état de la fiche. */
  function synchroniserCarte(F) {
    if (!F.enBiblio) return;
    t.lid = F.lid; t.statut = F.statut; t.favori = F.favori;
    if (F.P) {
      const n = F.P.next;
      Object.assign(t, { total_ep: F.P.total, vus_ep: F.P.vus, revoit: F.P.revoit,
        next_saison: n ? n.saison : null, next_numero: n ? n.numero : null, next_nom: n ? n.nom : null, next_duree: n ? n.duree : null });
    } else if (F.type === "film") t.nb_vues = F.visionnages.length;
    majCartes(t);
  }

  /* Le résumé ne garde « Lire la suite » que s'il dépasse 3 lignes. */
  function plierResume() {
    const r = $(".resume", el);
    const b = $("[data-lire]", el);
    if (!r || !b) return;
    b.hidden = r.scrollHeight <= r.clientHeight + 2;
  }

  /* Similaires et saga : chargés à la première visite de l'onglet Infos. */
  async function chargerExtras() {
    const F = V.F;
    if (!F.tmdb_id || V.charges.has("extras")) return;
    V.charges.add("extras");
    const poser = (cle, html) => {
      V.extras[cle] = html;
      const box = $(`[data-extra="${cle}"]`, el);
      if (box) { box.innerHTML = html; majToutesFleches(box); }
    };
    api(`/api/similar?tmdb_id=${F.tmdb_id}&type=${F.type}`, { signal: V.ctrl.signal }).then(({ results }) => {
      if (results && results.length) poser("similaires", htmlRangee(`Parce que tu as aimé « ${F.titre} »`, results));
    }).catch(() => {});
    if (F.type === "film") {
      api(`/api/collection?tmdb_id=${F.tmdb_id}`, { signal: V.ctrl.signal }).then(({ results, nom }) => {
        if (results && results.length) poser("saga", htmlRangee(nom ? `La saga « ${nom} »` : "Dans la même saga", results));
      }).catch(() => {});
    }
  }

  const majDefile = () => {
    const h = $(".fi-hero", el);
    el.classList.toggle("defile", el.scrollTop > (h ? h.offsetHeight - 120 : 160));
  };
  el.addEventListener("scroll", majDefile, { passive: true });

  /* ---------------------------------------------------------- actions */
  const ctx = () => ({ t, F: V.F });

  async function assurerSerie() {
    if (V.F.lid) return V.F.lid;
    const lid = await assurerDansBiblio(t, "a_voir");
    toast("Série ajoutée à ta bibliothèque");
    const d = normFiche(await attendreEpisodes(lid));
    V.F = d;
    return lid;
  }

  async function apresAction(r, message) {
    toast(message, { annuler: r && r.annuler, apres: () => { recharger(); actualiserTitre(t).catch(() => {}); } });
    await recharger();
    actualiserTitre(t).catch(() => {});
  }

  const MSG_EP = { seen: "vu", revu: "revu", remove: "un visionnage retiré", unmark: "décoché" };
  async function actionEpisode(s, n, action) {
    const lid = await assurerSerie();
    const r = await api(`/api/title/${lid}/episode/${s}/${n}/toggle`, { method: "POST", body: { action } });
    await apresAction(r, `${codeEp(s, n)} ${MSG_EP[action]}`);
  }
  async function actionSaison(s, action) {
    const lid = await assurerSerie();
    const r = await api(`/api/title/${lid}/season/${s}/mark`, { method: "POST", body: { action } });
    if (!r.touches) { toast("Rien à changer dans cette saison"); return; }
    const m = { seen: `Saison ${s} marquée vue · ${pluriel(r.touches, "épisode")}`, revu: `Saison ${s} revue`,
      unmark: `Saison ${s} décochée`, remove: `Un visionnage retiré de la saison ${s}` }[action];
    await apresAction(r, m);
  }
  async function actionSerie(action) {
    const lid = await assurerSerie();
    const r = await api(`/api/title/${lid}/mark`, { method: "POST", body: { action } });
    if (!r.touches) { toast("Rien à changer"); return; }
    const m = { seen: `Toute la série marquée vue · ${pluriel(r.touches, "épisode")}`, revu: "Série revue en entier",
      unmark: "Toute la série décochée", remove: "Un visionnage retiré de la série" }[action];
    await apresAction(r, m);
  }

  /* S2 : « Marquer jusqu'à É8 » annonce le nombre d'épisodes et leur durée. */
  async function jusquIci(s, n) {
    const F = V.F;
    let eps = [];
    if (F.enBiblio) {
      eps = F.saisons.flatMap((x) => x.episodes || [])
        .filter((e) => estDiffuse(e) && !e.vu && (e.saison < s || (e.saison === s && e.numero <= n)));
    } else {
      const sa = F.saisons.find((x) => x.numero === s);
      eps = (sa && sa.episodes ? sa.episodes : []).filter((e) => estDiffuse(e) && e.numero <= n);
    }
    if (F.enBiblio && !eps.length) { toast("Rien à marquer : tout est déjà vu jusqu'ici."); return; }
    const minutes = eps.reduce((a, e) => a + (e.duree || DUREE_EP_DEFAUT), 0);
    const detail = F.enBiblio
      ? `${pluriel(eps.length, "épisode encore non vu", "épisodes encore non vus")} jusqu'à ${codeEp(s, n)}, soit environ ${fmtDuree(minutes) || "0 min"}.`
      : `Tous les épisodes déjà diffusés jusqu'à ${codeEp(s, n)}. La série est d'abord ajoutée à ta bibliothèque.`;
    const ok = await confirmer(detail, { titre: `Marquer jusqu'à ${codeEp(s, n)} ?`, ok: eps.length ? `Marquer ${pluriel(eps.length, "épisode")}` : "Marquer" });
    if (!ok) return;
    const lid = await assurerSerie();
    const r = await api(`/api/title/${lid}/mark-upto`, { method: "POST", body: { saison: s, numero: n } });
    await apresAction(r, `${pluriel(r.touches, "épisode marqué vu", "épisodes marqués vus")}`);
  }

  function menuEpisode(e, btn) {
    const F = V.F;
    const ep = trouverEp(F, +e.dataset.s, +e.dataset.n) || {};
    const s = +e.dataset.s, n = +e.dataset.n;
    const items = [
      ["revu", "rotate", ep.vu ? `Je l'ai revu${ep.nb_vues ? ` (×${ep.nb_vues + 1})` : ""}` : "Marquer vu"],
      ["upto", "checks", `Marquer vu jusqu'à ${codeEp(s, n)}`],
    ];
    if (ep.vu && ep.nb_vues >= 1) items.push(["remove", "minus", ep.nb_vues > 1 ? "Retirer un visionnage" : "Marquer non vu"]);
    if (ep.nb_vues > 1) items.push(["unmark", "x", "Décocher complètement"]);
    const lancer = (a) => occupe(null, async () => {
      try { if (a === "upto") await jusquIci(s, n); else await actionEpisode(s, n, a); }
      catch (err) { toastErr(err); }
    });
    menuAdapte(items, btn, lancer, `${codeEp(s, n)}${ep.nom ? " · " + ep.nom : ""}`);
  }

  async function actionPrincipale(nom, btn) {
    const F = V.F;
    await occupe(btn, async () => {
      try {
        if (nom === "suivant") {
          const n = F.P && F.P.next;
          if (n) await actionEpisode(n.saison, n.numero, F.P.revoit ? "revu" : "seen");
        } else if (nom === "revoirFilm" || nom === "vuFilm") {
          const lid = F.lid || await assurerDansBiblio(t, "a_voir");
          const r = await api(`/api/title/${lid}/watch`, { method: "POST", body: {} });
          await apresAction(r, nom === "revoirFilm" ? `Revisionnage enregistré · ×${F.visionnages.length + 1}` : "Marqué vu");
        } else if (nom === "serieVue") {
          await actionSerie("seen");
        } else if (["aVoir", "vu", "alerte", "favori"].includes(nom)) {
          if (await Actions[nom](t)) await recharger();
        } else if (nom === "liste") {
          await choisirListes(t);
          recharger();
        }
      } catch (e) { toastErr(e); }
    });
  }

  /* ------------------------------------------------------- événements */
  el.addEventListener("click", async (e) => {
    const F = V.F;
    if (e.target.closest("[data-fermer]")) { fermer(); return; }
    if (!F) return;
    const o = e.target.closest(".onglets [data-o], [data-o-cible]");
    if (o) { changerOnglet(o.dataset.o || o.dataset.oCible); return; }
    const act = e.target.closest("[data-act]");
    if (act) { actionPrincipale(act.dataset.act, act); return; }
    if (e.target.closest("[data-lire]")) {
      const r = $(".resume", el);
      r.classList.toggle("plie");
      e.target.closest("[data-lire]").textContent = r.classList.contains("plie") ? "Lire la suite" : "Réduire";
      return;
    }
    if (e.target.closest("[data-fav]")) { actionPrincipale("favori", e.target.closest("[data-fav]")); return; }
    if (e.target.closest("[data-menu-fiche]")) { menuFiche(e.target.closest("[data-menu-fiche]")); return; }
    const delv = e.target.closest("[data-del-vision]");
    if (delv) {
      await occupe(delv, async () => {
        try {
          const r = await api(`/api/watch/${delv.dataset.delVision}`, { method: "DELETE" });
          await apresAction(r, "Visionnage retiré");
        } catch (err) { toastErr(err); }
      });
      return;
    }
    const sh = e.target.closest(".saison-h");
    if (sh) { basculerSaison(sh.closest(".saison")); return; }
    const sa = e.target.closest("[data-saison-act]");
    if (sa) {
      await occupe(sa, async () => {
        try { await actionSaison(Number(sa.closest(".saison").dataset.s), sa.dataset.saisonAct); }
        catch (err) { toastErr(err); }
      });
      return;
    }
    const se = e.target.closest("[data-serie-act]");
    if (se) {
      const a = se.dataset.serieAct;
      if (a === "unmark" && !(await confirmer("Tous les épisodes de la série redeviennent « non vus ».", { titre: "Tout décocher ?", ok: "Tout décocher", danger: true }))) return;
      await occupe(se, async () => { try { await actionSerie(a); } catch (err) { toastErr(err); } });
      return;
    }
    const epEl = e.target.closest(".ep[data-s]");
    if (epEl) {
      const ck = e.target.closest("[data-ck]");
      const plus = e.target.closest("[data-ep-menu]");
      if (ck) {
        const ep = trouverEp(F, +epEl.dataset.s, +epEl.dataset.n) || {};
        await occupe(ck, async () => {
          try { await actionEpisode(+epEl.dataset.s, +epEl.dataset.n, ep.vu ? "remove" : "seen"); }
          catch (err) { toastErr(err); }
        });
      } else if (plus) menuEpisode(epEl, plus);
      else if (e.target.closest(".nm")) epEl.classList.toggle("deplie");
    }
  });
  el.addEventListener("submit", async (e) => {
    const form = e.target.closest("[data-vision-date]");
    if (!form) return;
    e.preventDefault();
    const jour = form.jour.value;
    if (!jour) { form.jour.focus(); return; }
    await occupe(form.querySelector("button"), async () => {
      try {
        const lid = V.F.lid || await assurerDansBiblio(t, "a_voir");
        const r = await api(`/api/title/${lid}/watch`, { method: "POST", body: { date: jour } });
        await apresAction(r, `Visionnage du ${fmtDate(jour, { annee: true })} ajouté`);
      } catch (err) { toastErr(err); }
    });
  });
  // Appui long sur un épisode : « Marquer jusqu'ici » (S2).
  appuiLong(el, ".ep[data-s]:not(.futur)", (ep) => {
    jusquIci(+ep.dataset.s, +ep.dataset.n).catch(toastErr);
  });
  el.addEventListener("keydown", (e) => {
    const o = e.target.closest(".onglets [data-o]");
    if (!o || (e.key !== "ArrowRight" && e.key !== "ArrowLeft")) return;
    const bts = $$(".onglets [data-o]", el);
    const i = bts.indexOf(o) + (e.key === "ArrowRight" ? 1 : -1);
    const b = bts[(i + bts.length) % bts.length];
    changerOnglet(b.dataset.o);
    $(`.onglets [data-o="${b.dataset.o}"]`, el)?.focus();
  });

  function changerOnglet(k) {
    V.onglet = k;
    $$(".onglets [data-o]", el).forEach((b) => {
      const on = b.dataset.o === k;
      b.classList.toggle("on", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
    });
    $$(".fi-panneau", el).forEach((p) => p.classList.toggle("on", p.dataset.p === k));
    const haut = $(".fi-hero", el).offsetHeight - $(".fi-barre", el).offsetHeight;
    if (el.scrollTop > haut) el.scrollTop = haut;
    if (k === "infos") { chargerExtras(); plierResume(); }
    majToutesFleches(el);
  }

  async function basculerSaison(sEl) {
    const ouvrir = !sEl.classList.contains("ouverte");
    sEl.classList.toggle("ouverte", ouvrir);
    $(".saison-h", sEl).setAttribute("aria-expanded", ouvrir ? "true" : "false");
    if (!ouvrir || V.F.enBiblio) return;
    // Aperçu : les épisodes de la saison se chargent au premier dépliage.
    const s = V.F.saisons.find((x) => String(x.numero) === sEl.dataset.s);
    if (!s || s.episodes) return;
    try {
      const { episodes } = await api(`/api/preview/season?tmdb_id=${V.F.tmdb_id}&saison=${s.numero}`, { signal: V.ctrl.signal });
      s.episodes = episodes || [];
      const c = $(".saison-c", sEl);
      if (c) c.innerHTML = htmlContenuSaison(s, V.F, t);
    } catch (e) {
      if (e.name !== "AbortError") $(".saison-c", sEl).innerHTML = `<p class="muted petit" style="padding:12px 14px">Impossible de charger les épisodes.</p>`;
    }
  }

  function menuFiche(btn) {
    const F = V.F;
    const items = [["liste", "listplus", "Ajouter à une liste…"]];
    if (F.bande_annonce) items.push(["ba", "play", "Voir la bande-annonce"]);
    if (F.tmdb_id) items.push(["tmdb", "external", "Ouvrir sur TMDB"]);
    if (F.lid) items.push(["retirer", "trash", "Retirer de ma bibliothèque", true]);
    const lancer = async (a) => {
      if (a === "liste") { await choisirListes(t); recharger(); }
      else if (a === "ba") window.open(`https://www.youtube.com/watch?v=${encodeURIComponent(F.bande_annonce)}`, "_blank", "noopener");
      else if (a === "tmdb") window.open(`https://www.themoviedb.org/${F.type === "serie" ? "tv" : "movie"}/${F.tmdb_id}`, "_blank", "noopener");
      else if (a === "retirer") {
        try { if (await Actions.retirer(t)) fermer(); } catch (e) { toastErr(e); }
      }
    };
    if (pointeurFin() && dernierPointeur !== "touch") menuSimple(items, btn, lancer, F.titre);
    else {
      const f = feuille({ titre: esc(F.titre), html: `<div class="liste-r">${items.map(([a, i, txt, dn]) =>
        `<button type="button" class="li${dn ? " dn" : ""}" data-a="${a}"><span class="li-ic">${ic(i)}</span><span class="tx">${esc(txt)}</span></button>`).join("")}</div>` });
      f.el.addEventListener("click", async (ev) => {
        const b = ev.target.closest("[data-a]");
        if (!b) return;
        await f.fermer();
        lancer(b.dataset.a);
      });
    }
  }

  recharger({ garder: false });
  return { el, fermer };
}

/* Retrouve un épisode (bibliothèque ou aperçu chargé). */
function trouverEp(F, s, n) {
  const sa = (F.saisons || []).find((x) => x.numero === s);
  return sa && sa.episodes ? sa.episodes.find((e) => e.numero === n) : null;
}
/* Sélecteur pour remettre le focus au même bouton après un nouveau rendu. */
function cleFocus(a) {
  const ep = a.closest(".ep[data-s]");
  if (ep) return `.ep[data-s="${ep.dataset.s}"][data-n="${ep.dataset.n}"] ${a.matches("[data-ck]") ? "[data-ck]" : "[data-ep-menu]"}`;
  if (a.dataset.act) return `[data-act="${a.dataset.act}"]`;
  if (a.dataset.o) return `.onglets [data-o="${a.dataset.o}"]`;
  return null;
}

/* Petit menu flottant générique (ordinateur). */
function menuSimple(items, ancre, lancer, titre = "") {
  fermerPop();
  const el = document.createElement("div");
  el.className = "pop";
  el.setAttribute("role", "menu");
  el.innerHTML = (titre ? `<div class="pop-t">${esc(titre)}</div>` : "") + items.map(([a, i, txt, dn]) =>
    `<button type="button" class="mi${dn ? " dn" : ""}" role="menuitem" data-a="${a}">${ic(i)}<span>${esc(txt)}</span></button>`).join("");
  document.body.append(el);
  const r = ancre.getBoundingClientRect();
  el.style.left = `${Math.max(8, Math.min(r.right - el.offsetWidth, innerWidth - el.offsetWidth - 8))}px`;
  const y = r.bottom + 6;
  el.style.top = `${y + el.offsetHeight > innerHeight - 8 ? Math.max(8, r.top - el.offsetHeight - 6) : y}px`;
  let ferme = false;
  const dehors = (e) => { if (!el.contains(e.target)) p.fermer(); };
  const retirer = () => {
    if (ferme) return;
    ferme = true;
    el.remove();
    document.removeEventListener("pointerdown", dehors, true);
    if (popOuverte === p) popOuverte = null;
  };
  const couche = Couches.ouvrir(retirer, { el });
  const p = { el, fermer: () => (ferme ? Promise.resolve() : Couches.fermer(couche)) };
  popOuverte = p;
  setTimeout(() => document.addEventListener("pointerdown", dehors, true), 0);
  el.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-a]");
    if (!b) return;
    await p.fermer();
    lancer(b.dataset.a);
  });
  el.querySelector(".mi")?.focus({ preventScroll: true });
  return p;
}

/* Le même menu en feuille du bas au doigt, en menu flottant à la souris. */
function menuAdapte(items, ancre, lancer, titre = "") {
  if (pointeurFin() && dernierPointeur !== "touch") return menuSimple(items, ancre, lancer, titre);
  const f = feuille({ titre: esc(titre),
    html: `<div class="liste-r">${items.map(([a, i, txt, dn]) => `<button type="button" class="li${dn ? " dn" : ""}" data-a="${a}"><span class="li-ic">${ic(i)}</span><span class="tx">${esc(txt)}</span></button>`).join("")}</div>` });
  f.el.addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-a]");
    if (!b) return;
    await f.fermer();
    lancer(b.dataset.a);
  });
  return f;
}

/* ------------------------------------------------------- morceaux HTML */
function htmlBarreHaut(F) {
  return `<div class="fi-barre">
    <button type="button" class="ib verre" data-fermer aria-label="Fermer la fiche">${ic("chevl")}</button>
    <span class="tt">${esc(F.titre || "")}</span>
    <div class="d">${F.lid !== undefined && F.enBiblio !== undefined ? `${F.lid ? `<button type="button" class="ib verre${F.favori ? " on" : ""}" data-fav aria-pressed="${F.favori ? "true" : "false"}" aria-label="${F.favori ? "Retirer des favoris" : "Ajouter aux favoris"}">${ic(F.favori ? "heartfill" : "heart")}</button>` : ""}
      <button type="button" class="ib verre" data-menu-fiche aria-label="Plus d'actions">${ic("dots")}</button>` : ""}</div>
  </div>`;
}

function htmlHero(F, t) {
  const kick = [libType(F), F.annee, ...(F.genres || []).slice(0, 2)].filter(Boolean).map(esc).join(" · ");
  const mt = [];
  if (F.note_tmdb) mt.push(`<span class="note">${ic("staron", "s16")}${noteTxt(F.note_tmdb)}</span>`);
  if (F.type === "film" && F.duree) mt.push(`<span>${fmtDuree(F.duree)}</span>`);
  if (F.type === "serie") {
    const n = F.enBiblio ? (F.saisons || []).length : F.nb_saisons;
    if (n) mt.push(`<span>${pluriel(n, "saison")}</span>`);
  }
  if (aVenir(F.date_sortie)) mt.push(`<span class="acc">Sortie le ${esc(fmtDate(F.date_sortie, { annee: true }))}</span>`);
  if (F.bande_annonce) mt.push(`<a class="lien" href="https://www.youtube.com/watch?v=${encodeURIComponent(F.bande_annonce)}" target="_blank" rel="noopener">${ic("play", "s16")}Bande-annonce</a>`);
  let prog = "";
  if (F.P && F.P.total) {
    const pct = Math.round(F.P.vus / F.P.total * 100);
    prog = `<div class="fi-prog"><span class="pg${pct >= 100 ? " ok" : ""}"><i style="width:${pct}%"></i></span><span>${F.P.vus} / ${pluriel(F.P.total, "épisode")}</span></div>`;
  } else if (F.enBiblio && F.statut) {
    const lib = { vu: F.type === "serie" ? "Série vue" : (F.visionnages.length > 1 ? `Vu ×${F.visionnages.length}` : "Vu"),
      a_voir: "À voir plus tard", en_cours: "En cours" }[F.statut];
    prog = `<div class="fi-prog"><span class="etq-s ${F.statut}">${ic(F.statut === "vu" ? "check" : F.statut === "a_voir" ? "bookmarkon" : "play", "s16")}${esc(lib)}</span></div>`;
  }
  return `<div class="fi-hero"><div class="fond"${F.fond || F.affiche ? ` style="background-image:url('${cssUrl(F.fond || F.affiche)}')"` : ""}></div>
    <div class="fi-head"><div class="aff">${F.affiche ? `<img src="${posterSrc(F.affiche)}" alt="">` : ""}</div>
      <div class="tx"><div class="fi-kick">${kick}</div><h1 class="fi-t">${esc(F.titre)}</h1>
        <div class="fi-mt">${mt.join("")}</div>${prog}</div></div></div>`;
}

function htmlOnglets(F, actif) {
  return `<div class="onglets" role="tablist" aria-label="Sections de la fiche">${ONGLETS.filter(([k]) => k !== "episodes" || F.type === "serie").map(([k, nom]) =>
    `<button type="button" role="tab" id="fo-${k}" data-o="${k}" class="${k === actif ? "on" : ""}" aria-selected="${k === actif}" tabindex="${k === actif ? 0 : -1}">${nom}</button>`).join("")}</div>`;
}

function htmlPanneau(k, F, t, etat) {
  if (k === "episodes") return htmlEpisodes(F, t, etat);
  if (k === "infos") return htmlInfos(F, t);
  if (k === "casting") return htmlCasting(F);
  return htmlOu(F);
}

/* Barre d'actions collée en bas (F2) : l'action la plus utile en grand. */
function htmlActions(F, t) {
  const liste = `<button type="button" class="btn ico" data-act="liste" title="Ajouter à une liste" aria-label="Ajouter à une liste">${ic("listplus")}</button>`;
  const lib = (txt) => `<span class="lib">${txt}</span>`;
  let h = "";
  if (F.type === "serie") {
    const n = F.P && F.P.next;
    if (F.enBiblio && n) {
      h = `<button type="button" class="btn pri croit" data-act="suivant">${ic("check", "s18")}${lib(`${F.P.revoit ? "Revu" : "Marquer"} ${codeEp(n.saison, n.numero)}${F.P.revoit ? "" : " vu"}`)}</button>`;
      if (F.statut !== "a_voir" && !F.P.vus) h += `<button type="button" class="btn ico" data-act="aVoir" aria-label="À voir plus tard">${ic("bookmark")}</button>`;
    } else if (F.enBiblio && F.statut === "vu") {
      h = `<button type="button" class="btn okb croit" data-o-cible="episodes">${ic("checks", "s18")}${lib("Série vue · les épisodes")}</button>`;
    } else if (F.enBiblio) {
      h = `<button type="button" class="btn pri croit" data-act="serieVue">${ic("checks", "s18")}${lib("Marquer toute la série vue")}</button>`;
    } else {
      h = `<button type="button" class="btn pri croit" data-act="aVoir">${ic("bookmark", "s18")}${lib("À voir plus tard")}</button>
        <button type="button" class="btn" data-act="vu">${ic("check", "s18")}Déjà vue</button>`;
    }
  } else {
    const sortie = aVenir(F.date_sortie) && !F.visionnages.length;
    if (sortie) {
      const al = F.alerte || t.alerte;
      h = `<button type="button" class="btn ${al ? "okb" : "pri"} croit" data-act="alerte" aria-pressed="${al ? "true" : "false"}">${ic(al ? "bellon" : "bell", "s18")}${lib(al ? "Alerte posée" : "M'alerter à la sortie")}</button>`;
      if (F.statut !== "a_voir") h += `<button type="button" class="btn ico" data-act="aVoir" aria-label="À voir plus tard">${ic("bookmark")}</button>`;
    } else if (F.enBiblio && F.visionnages.length) {
      h = `<button type="button" class="btn okb croit" data-act="revoirFilm">${ic("rotate", "s18")}${lib(`Vu${F.visionnages.length > 1 ? " ×" + F.visionnages.length : ""} · J'ai revu`)}</button>`;
    } else if (F.enBiblio) {
      h = `<button type="button" class="btn pri croit" data-act="vuFilm">${ic("check", "s18")}${lib("Marquer vu")}</button>`;
      if (F.statut !== "a_voir") h += `<button type="button" class="btn ico" data-act="aVoir" aria-label="À voir plus tard">${ic("bookmark")}</button>`;
    } else {
      h = `<button type="button" class="btn pri croit" data-act="aVoir">${ic("bookmark", "s18")}${lib("À voir plus tard")}</button>
        <button type="button" class="btn" data-act="vu">${ic("check", "s18")}Déjà vu</button>`;
    }
  }
  return `<div class="fi-act">${h}${liste}</div>`;
}

/* --- Infos (F5, F6) */
function htmlInfos(F, t) {
  let h = "";
  if (F.resume) {
    h += `<p class="resume plie">${esc(F.resume)}</p><button type="button" class="lire" data-lire>Lire la suite</button>`;
  } else h += `<p class="muted">Pas de résumé pour l'instant.</p>`;
  const tags = (F.genres || []).map((g) => `<span class="tag">${esc(g)}</span>`);
  if (F.pays) tags.push(`<span class="tag">${esc(F.pays)}</span>`);
  if (tags.length) h += `<div class="tags">${tags.join("")}</div>`;

  const infos = [];
  if (F.date_sortie) infos.push(["Sortie", fmtDate(F.date_sortie, { annee: true })]);
  if (F.type === "film" && F.duree) infos.push(["Durée", fmtDuree(F.duree)]);
  if (F.type === "serie") {
    const nbEp = F.enBiblio ? F.saisons.reduce((a, s) => a + (s.total || 0), 0) : F.nb_episodes;
    if (nbEp) infos.push(["Épisodes", `${nb(nbEp)} · ${pluriel(F.enBiblio ? F.saisons.length : F.nb_saisons || 0, "saison")}`]);
    if (F.type === "serie" && F.duree) infos.push(["Par épisode", fmtDuree(F.duree)]);
  }
  if (F.note_tmdb) infos.push(["Note TMDB", `★ ${noteTxt(F.note_tmdb)} / 10`]);
  const real = F.realisateur || ((F.equipe || []).find((p) => p.poste === "Réalisateur") || {}).nom;
  if (real) infos.push(["Réalisation", real]);
  const crea = ((F.equipe || []).find((p) => p.poste === "Créateur") || {}).nom;
  if (crea) infos.push(["Création", crea]);
  if (F.enBiblio && F.date_ajout) infos.push(["Ajouté le", fmtDate(isoDeTs(F.date_ajout), { annee: true })]);
  if (F.manuel) infos.push(["Origine", "Ajout manuel"]);
  if (infos.length) h += `<div class="infos-g">${infos.map(([k, v]) => `<div class="info-b"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`).join("")}</div>`;

  if (F.enBiblio) h += htmlHistorique(F, t);
  h += `<div data-extra="similaires"></div><div data-extra="saga"></div>`;
  return h;
}

/* F5 : épisodes vus, temps passé, revisionnages, mini frise. */
function htmlHistorique(F, t) {
  const tuiles = [];
  if (F.type === "serie") {
    const tp = F.temps || {};
    tuiles.push(["Épisodes vus", nb(tp.episodes || 0)]);
    tuiles.push(["Temps passé", tp.minutes ? tp.texte : "—"]);
    tuiles.push(["Série vue", tp.fois ? `×${tp.fois}` : "—"]);
  } else {
    const n = F.visionnages.length;
    tuiles.push(["Visionnages", nb(n)]);
    tuiles.push(["Temps passé", n && F.duree ? fmtDuree(n * F.duree) : "—"]);
    const der = F.visionnages.find((v) => v.date);
    tuiles.push(["Dernier", der ? fmtDate(der.date, { court: true }) : (n ? "date inconnue" : "—")]);
  }
  let h = `<h3 class="fi-h3">${ic("clock", "s18 acc")}Ton historique</h3>
    <div class="hist">${tuiles.map(([k, v]) => `<div class="info-b"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`).join("")}</div>`;
  if (F.type === "film") {
    if (F.visionnages.length) {
      h += `<div class="vision">${F.visionnages.map((v) => `<span class="tag">${ic("check", "s16 okc")}${v.date ? esc(fmtDate(v.date, { annee: true })) : "déjà vu"}
        <button type="button" data-del-vision="${v.id}" aria-label="Retirer ce visionnage" title="Retirer ce visionnage">${ic("x", "s16")}</button></span>`).join("")}</div>`;
    }
    h += `<form class="ligne vision-date" data-vision-date><label class="lbl" for="vd-${F.lid}">Vu un autre jour ?</label>
      <input class="input" id="vd-${F.lid}" type="date" name="jour" max="${isoLocal()}">
      <button class="btn sm" type="submit">${ic("plus", "s16")}Ajouter</button></form>`;
  }
  const frise = friseTitre(F.journal || []);
  if (frise.length) {
    h += `<div class="frise">${frise.map((l) => `<div class="e"><b>${esc(fmtDate(l.jour))}</b> : ${esc(l.txt)}</div>`).join("")}</div>`;
  }
  return h;
}

/* --- Casting (F6) */
function htmlCasting(F) {
  const pers = htmlPersonne;
  let h = "";
  if ((F.casting || []).length) h += `<h3 class="fi-h3">Distribution</h3><div class="cast">${F.casting.map((p) => pers(p, p.personnage)).join("")}</div>`;
  if ((F.equipe || []).length) h += `<h3 class="fi-h3">Équipe</h3><div class="cast">${F.equipe.map((p) => pers(p, p.poste)).join("")}</div>`;
  return h || videHtml("users", "Casting inconnu", "TMDB ne donne pas encore la distribution de ce titre.");
}

/* --- Où regarder (F4) */
function htmlOu(F) {
  const plats = plateformesTriees(F.plateformes);
  if (!plats.length) return videHtml("tv", "Pas encore en streaming", "Aucune plateforme ne le propose en France pour l'instant.");
  const ligne = (p) => `<div class="prov"><img src="${posterSrc(p.logo)}" alt="" loading="lazy">
    <div class="tx"><b>${esc(p.nom)}</b><span>${esc(p.mode || "Disponible")}</span></div>
    ${p.inclus ? `<span class="inclus">${ic("check", "s16")}Inclus</span>` : ""}</div>`;
  const miens = plats.filter((p) => p.inclus), autres = plats.filter((p) => !p.inclus);
  let h = "";
  if (miens.length) h += `<div class="prov-g">Sur tes plateformes</div><div class="prov-l">${miens.map(ligne).join("")}</div>`;
  if (autres.length) h += `${miens.length ? '<div class="prov-g">Ailleurs</div>' : ""}<div class="prov-l">${autres.map(ligne).join("")}</div>`;
  if (!MES_PLATEFORMES.size && SUPER_ADMIN) h += `<p class="muted petit" style="margin-top:12px">Indique tes abonnements dans <a href="#parametres/plateformes">Paramètres → Mes plateformes</a> : ils passeront en premier, avec la mention « Inclus ».</p>`;
  h += `<p class="muted petit" style="margin-top:12px">Données JustWatch, via TMDB.</p>`;
  return h;
}

/* --- Épisodes (S1 à S3) */
function saisonCible(F) {
  if (F.P && F.P.next) return F.P.next.saison;
  const s = (F.saisons || []).find((x) => (x.episodes || []).some((e) => estDiffuse(e) && !e.vu));
  if (s) return s.numero;
  return F.enBiblio ? null : (F.saisons[0] || {}).numero;
}

function htmlEpisodes(F, t, { ouvertes = null, fermees = null } = {}) {
  let h = "";
  if (F.enBiblio && F.temps && F.temps.minutes > 0) {
    h += `<div class="temps-serie">${ic("clock")}<span><b>${esc(F.temps.texte)}</b> passés sur cette série · ${pluriel(F.temps.episodes, "épisode vu", "épisodes vus")}${F.temps.fois > 1 ? ` · revue ×${F.temps.fois}` : ""}${F.temps.converti ? ` · ≈ ${esc(F.temps.converti)}` : ""}</span></div>`;
  }
  if (F.prochain && F.prochain.date_diff && aVenir(F.prochain.date_diff)) {
    const p = F.prochain;
    h += `<div class="annonce">${ic("cal")}<span>Prochain épisode : <b>${codeEp(p.saison, p.numero)}</b>${p.nom ? ` « ${esc(p.nom)} »` : ""} le ${esc(fmtJour(p.date_diff).toLowerCase())} · <span class="decompte">${dans(joursJusqua(p.date_diff))}</span></span></div>`;
  }
  if (!F.enBiblio) h += `<div class="annonce">${ic("info")}<span>Coche un épisode : la série s'ajoute à ta bibliothèque et ta progression est suivie.</span></div>`;
  if (F.sync) h += `<div class="annonce">${ic("spin", "tourne")}<span>Chargement des épisodes…</span></div>`;
  if (!(F.saisons || []).length) return h + (F.sync ? "" : videHtml("tv", "Épisodes indisponibles", "TMDB ne liste pas encore d'épisode pour cette série."));
  const cible = saisonCible(F);
  for (const s of F.saisons) {
    const k = String(s.numero);
    const ouverte = ouvertes && (ouvertes.has(k) || fermees.has(k)) ? ouvertes.has(k) : s.numero === cible;
    h += htmlSaison(s, F, t, ouverte);
  }
  if (F.enBiblio) {
    const diff = F.saisons.reduce((a, s) => a + (s.diffuses || 0), 0);
    const vus = F.saisons.reduce((a, s) => a + (s.episodes || []).filter((e) => estDiffuse(e) && e.vu).length, 0);
    const btns = [];
    if (diff && vus < diff) btns.push(`<button type="button" class="btn sm" data-serie-act="seen">${ic("checks", "s16")}Marquer toute la série vue</button>`);
    if (diff && vus >= diff) btns.push(`<button type="button" class="btn sm" data-serie-act="revu">${ic("rotate", "s16")}J'ai revu toute la série</button>`);
    if (vus) btns.push(`<button type="button" class="btn sm gh" data-serie-act="unmark">${ic("x", "s16")}Tout décocher</button>`);
    if (btns.length) h += `<div class="serie-act">${btns.join("")}</div>`;
  }
  return h;
}

function htmlSaison(s, F, t, ouverte) {
  let diff, vus, total, futurs = 0, premiere = null, fois = 0;
  if (F.enBiblio) {
    const eps = s.episodes || [];
    const aired = eps.filter(estDiffuse);
    diff = aired.length;
    vus = aired.filter((e) => e.vu).length;
    total = eps.length;
    futurs = total - diff;
    const f = eps.find((e) => !estDiffuse(e) && e.date_diff);
    premiere = f ? f.date_diff : null;
    fois = diff && vus >= diff ? Math.min(...aired.map((e) => e.nb_vues || 0)) : 0;
  } else {
    total = s.episodes ? s.episodes.length : s.nb;
    diff = s.episodes ? s.episodes.filter(estDiffuse).length : total;
    vus = 0;
  }
  const pct = diff ? Math.round(vus / diff * 100) : 0;
  const aVenirTout = F.enBiblio && total > 0 && diff === 0;
  let sous;
  if (aVenirTout) sous = premiere ? `À venir · dès le ${fmtDate(premiere)}` : "À venir";
  else if (F.enBiblio && diff && vus >= diff) sous = `Vue${fois > 1 ? " ×" + fois : ""} · ${pluriel(diff, "épisode")}${futurs ? ` · ${futurs} à venir` : ""}`;
  else if (F.enBiblio) sous = `${vus} / ${diff} vus${futurs ? ` · ${futurs} à venir` : ""}`;
  else sous = pluriel(total || 0, "épisode");
  const nom = s.nom && !/^saison \d+$/i.test(s.nom) ? ` · ${s.nom}` : "";
  return `<div class="saison${ouverte ? " ouverte" : ""}${aVenirTout ? " futur" : ""}" data-s="${s.numero}">
    <button type="button" class="saison-h" aria-expanded="${ouverte ? "true" : "false"}">
      <span class="anneau${pct > 0 && pct < 100 ? " cours" : ""}" style="--p:${pct}"><b>${vus}/${diff || total || 0}</b></span>
      <span class="tx"><b>Saison ${s.numero}${esc(nom)}</b><span>${esc(sous)}</span></span>
      ${ic("chev", "s18 chev")}</button>
    <div class="saison-c">${F.enBiblio || s.episodes ? htmlContenuSaison(s, F, t) : `<div style="padding:10px 14px">${squeletteLignes(3)}</div>`}</div>
  </div>`;
}

function htmlContenuSaison(s, F, t) {
  const eps = s.episodes || [];
  const aired = eps.filter(estDiffuse), futurs = eps.filter((e) => !estDiffuse(e));
  const vus = aired.filter((e) => e.vu).length;
  const btns = [];
  if (aired.length && vus < aired.length) btns.push(`<button type="button" class="btn xs" data-saison-act="seen">${ic("checks", "s16")}Marquer la saison vue</button>`);
  if (F.enBiblio && aired.length && vus >= aired.length) btns.push(`<button type="button" class="btn xs" data-saison-act="revu">${ic("rotate", "s16")}J'ai revu la saison</button>`);
  if (F.enBiblio && vus) btns.push(`<button type="button" class="btn xs gh" data-saison-act="unmark">${ic("x", "s16")}Décocher</button>`);
  let h = btns.length ? `<div class="saison-act">${btns.join("")}</div>` : "";
  h += aired.map((e) => htmlEp(e, F, t)).join("");
  if (!eps.length) h += `<p class="muted petit" style="padding:12px 14px">Aucun épisode pour l'instant.</p>`;
  if (futurs.length) {
    h += `<div class="eps-futurs"><div class="lbl-mono">${ic("hourglass", "s16")}À venir</div>${futurs.map((e) => htmlEp(e, F, t)).join("")}</div>`;
  }
  return h;
}

function htmlEp(e, F, t) {
  const diffuse = estDiffuse(e);
  const nx = F.P && F.P.next;
  const hl = !!nx && nx.saison === e.saison && nx.numero === e.numero;
  const meta = [];
  if (e.duree) meta.push(fmtDuree(e.duree));
  if (e.date_diff) meta.push(diffuse ? fmtDate(e.date_diff, { court: true, annee: true }) : `le ${fmtDate(e.date_diff, { court: true })}`);
  if (e.vu && e.nb_vues > 1) meta.push(`vu ×${e.nb_vues}`);
  else if (e.vu && e.derniere_vue) meta.push(`vu le ${fmtDate(e.derniere_vue, { court: true })}`);
  const etat = e.vu ? (e.nb_vues > 1 ? `vu ${e.nb_vues} fois` : "vu") : "pas vu";
  const ck = diffuse
    ? `<button type="button" class="ck${e.vu ? " on" : ""}" data-ck aria-pressed="${e.vu ? "true" : "false"}" aria-label="${codeEp(e.saison, e.numero)}, ${etat}. ${e.vu ? "Retirer un visionnage" : "Marquer vu"}">${e.vu && e.nb_vues > 1 ? `<span class="nb">×${e.nb_vues}</span>` : ic("check", "s16")}</button>`
    : `<span class="decompte">${dans(joursJusqua(e.date_diff || isoLocal()))}</span>`;
  return `<div class="ep${hl ? " hl" : ""}${diffuse ? "" : " futur"}" data-s="${e.saison}" data-n="${e.numero}">
    <span class="nb">É${e.numero}</span>
    <div class="nm"><b>${esc(e.nom || "Épisode " + e.numero)}</b>${meta.length ? `<span>${esc(meta.join(" · "))}</span>` : ""}${e.resume ? `<p>${esc(e.resume)}</p>` : ""}</div>
    ${diffuse ? `<button type="button" class="plus" data-ep-menu aria-label="Plus d'actions pour ${codeEp(e.saison, e.numero)}">${ic("dots", "s18")}</button>` : ""}
    ${ck}</div>`;
}

/* -------------------------------------------------------- une personne */
function ouvrirPersonne(id) {
  const el = document.createElement("div");
  el.className = "fiche perso";
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-modal", "true");
  el.tabIndex = -1;
  const ctrl = new AbortController();
  const avant = document.activeElement;
  let ferme = false;
  el.innerHTML = `${htmlBarreHaut({ titre: "" })}<div class="fi-corps perso-c">${squeletteLignes(2)}<div class="grille">${squeletteGrille(8)}</div></div>`;
  document.body.append(el);
  const couche = Couches.ouvrir(() => {
    if (ferme) return;
    ferme = true;
    ctrl.abort();
    el.classList.add("sort");
    setTimeout(() => el.remove(), 210);
    if (avant && avant.focus && document.contains(avant)) avant.focus({ preventScroll: true });
  }, { el });
  el.addEventListener("click", (e) => {
    if (e.target.closest("[data-fermer]")) Couches.fermer(couche);
    else if (e.target.closest("[data-lire]")) {
      const r = $(".resume", el);
      r.classList.toggle("plie");
      e.target.closest("[data-lire]").textContent = r.classList.contains("plie") ? "Lire la suite" : "Réduire";
    }
  });
  el.addEventListener("scroll", () => el.classList.toggle("defile", el.scrollTop > 60), { passive: true });
  setTimeout(() => el.focus({ preventScroll: true }), 40);
  (async () => {
    try {
      const p = await api(`/api/person/${id}`, { signal: ctrl.signal });
      if (ferme) return;
      el.setAttribute("aria-label", p.nom);
      const infos = [p.metier, p.naissance ? `Né(e) le ${fmtDate(p.naissance, { annee: true })}` : "", p.lieu].filter(Boolean);
      el.innerHTML = `${htmlBarreHaut({ titre: p.nom })}
        <div class="fi-corps perso-c">
          <div class="perso-h"><div class="ph">${p.photo ? `<img src="${posterSrc(p.photo)}" alt="">` : ""}</div>
            <div class="tx"><div class="fi-kick">${esc(p.metier || "Personne")}</div><h1 class="fi-t">${esc(p.nom)}</h1></div></div>
          ${infos.length ? `<div class="tags">${infos.map((x) => `<span class="tag">${esc(x)}</span>`).join("")}</div>` : ""}
          ${p.bio ? `<p class="resume plie" style="margin-top:14px">${esc(p.bio)}</p><button type="button" class="lire" data-lire>Lire la suite</button>` : ""}
          <h3 class="fi-h3">Filmographie<span class="muted petit">${pluriel((p.films || []).length, "titre")}</span></h3>
          <div class="grille">${htmlCartes(p.films || [])}</div>
        </div>`;
      const r = $(".resume", el), b = $("[data-lire]", el);
      if (r && b) b.hidden = r.scrollHeight <= r.clientHeight + 2;
    } catch (e) {
      if (e.name !== "AbortError" && !ferme) $(".fi-corps", el).innerHTML = erreurHtml(e);
    }
  })();
}
