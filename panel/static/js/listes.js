/* =========================================================================
   cinéthèque — Listes : cartes en mosaïque (L1), détail d'une liste avec sa
   progression « 12 / 31 vus » (L4), listes « dans l'ordre » numérotées avec
   « Prochain : n° 4 · Thor » et l'ordre qui se change en faisant glisser
   (L3). Aussi : nouvelle liste, listes prêtes (sagas) et import.
   Le détail est une sous-page (#listes/12) : le bouton retour y revient.
   ========================================================================= */
"use strict";

const Listes = { index: null, detail: null, _req: 0 };

/* ------------------------------------------------------------ nouvelle */
async function nouvelleListe() {
  const nom = await demander("Nouvelle liste", { label: "Nom de la liste", placeholder: "ex. Soirées d'hiver", ok: "Créer" });
  if (!nom) return;
  try {
    const r = await api("/api/lists", { method: "POST", body: { nom } });
    toast(`Liste « ${nom} » créée`);
    signaler("listes", { id: r.id });
    Nav.lien("listes", String(r.id));
  } catch (e) { toastErr(e); }
}

/* ------------------------------------------------------------- l'index */
function htmlMosaique(affiches) {
  const a = (affiches || []).slice(0, 4);
  if (a.length === 1) return `<div class="mosa un"><div><img src="${posterSrc(a[0])}" alt="" loading="lazy"></div></div>`;
  const cases = [0, 1, 2, 3].map((i) => a[i] ? `<div><img src="${posterSrc(a[i])}" alt="" loading="lazy"></div>`
    : `<div class="vide-m">${i === 0 && !a.length ? ic("film") : ""}</div>`);
  return `<div class="mosa">${cases.join("")}</div>`;
}
function htmlCarteListe(l) {
  const pct = l.nb ? Math.round(l.vus / l.nb * 100) : 0;
  const etq = l.systeme ? `<span class="etq sys">${l.systeme === "favoris" ? "suit le cœur" : "suit le statut"}</span>`
    : l.ordonnee ? `<span class="etq">${ic("hash", "s16")}dans l'ordre</span>` : "";
  return `<button type="button" class="lc" data-liste="${l.id}" aria-label="${esc(l.nom)}, ${pluriel(l.nb, "titre")}">
    ${htmlMosaique(l.affiches)}
    <div class="b"><b>${esc(l.nom)}</b>
      <div class="m"><span>${pluriel(l.nb, "titre")}</span>${etq}</div>
      ${l.nb ? `<div class="pgl"><div class="pg${pct >= 100 ? " ok" : " acc"}"><i style="width:${pct}%"></i></div><span>${nb(l.vus)} / ${nb(l.nb)} vus</span></div>` : ""}
    </div></button>`;
}

async function chargerListes() {
  const box = $("#lst-grille");
  const my = ++Listes._req;
  if (!Listes.index) box.innerHTML = `<div class="sk" style="aspect-ratio:4/3"></div>`.repeat(4);
  try {
    const { listes = [] } = await api("/api/lists");
    if (my !== Listes._req) return;
    const premier = !Listes.index;
    Listes.index = listes;
    box.innerHTML = listes.map(htmlCarteListe).join("")
      + `<button type="button" class="lc lc-nouvelle" data-nouvelle-liste>${ic("plus", "s24")}<span>Nouvelle liste</span></button>`;
    if (premier) animerEntree(box);
  } catch (e) {
    if (my === Listes._req && !Listes.index) box.innerHTML = erreurHtml(e);
  }
}

$("#lst-grille")?.addEventListener("click", (e) => {
  const c = e.target.closest(".lc[data-liste]");
  if (c) ouvrirListe(Number(c.dataset.liste));
});

/* ---------------------------------------------------------- le détail */
function ouvrirListe(id) {
  if (Listes.detail && Listes.detail.id === id) return;
  if (Listes.detail) {
    const c = Listes.detail.couche;
    fermerDetailListe();
    if (c) Couches.fermer(c);
  }
  const D = { id, liste: null, items: [], couche: null, defil: scrollY };
  Listes.detail = D;
  $("#lst-index").hidden = true;
  const box = $("#lst-detail");
  box.hidden = false;
  box.innerHTML = `<div class="liste-h"><span class="sk ln" style="width:50%;height:26px"></span></div>${squeletteLignes(5)}`;
  scrollTo(0, 0);
  D.couche = Nav.sousVue(String(id), () => fermerDetailListe(D));
  chargerDetail(D);
}
function fermerDetailListe(D = Listes.detail) {
  if (!D || Listes.detail !== D) return;
  Listes.detail = null;
  $("#lst-detail").hidden = true;
  $("#lst-detail").innerHTML = "";
  $("#lst-index").hidden = false;
  if (Nav.page === "listes") requestAnimationFrame(() => scrollTo(0, D.defil || 0));
  chargerListes();
}

async function chargerDetail(D, { calme = false } = {}) {
  try {
    const { liste, titres = [] } = await api(`/api/lists/${D.id}`);
    if (Listes.detail !== D) return;
    D.liste = liste;
    D.items = titres.map(retenir);
    rendreDetail(D);
    if (!calme) animerEntree($("#lst-detail .ordre, #lst-detail .grille"));
  } catch (e) {
    if (Listes.detail !== D) return;
    $("#lst-detail").innerHTML = `<div class="liste-h"><button type="button" class="btn sm gh" data-lst-retour>${ic("chevl", "s18")}Listes</button></div>${erreurHtml(e)}`;
  }
}

function rendreDetail(D) {
  const L = D.liste, items = D.items;
  const perso = !L.systeme;
  const vus = items.filter(dejaVu).length;
  const pct = items.length ? Math.round(vus / items.length * 100) : 0;
  const regle = L.systeme === "a_voir" ? "Cette liste suit le statut « à voir » de tes titres : marque-les vus pour qu'ils en sortent."
    : L.systeme === "favoris" ? "Cette liste suit le cœur de tes titres." : "";
  let corps;
  if (!items.length) {
    corps = videHtml("listplus", "Liste vide",
      "Ajoute des titres depuis le menu d'une affiche ou depuis une fiche, avec le bouton « Liste ».",
      `<button type="button" class="btn sm pri" data-palette>${ic("search", "s18")}Chercher un titre</button>`);
  } else if (L.ordonnee) {
    const iSuivant = items.findIndex((t) => !dejaVu(t));
    const s = items[iSuivant];
    corps = (s ? `<div class="prochain" data-ord-ouvrir data-k="${cleDe(s)}" role="button" tabindex="0">
        <div class="mini">${s.affiche ? `<img src="${posterSrc(s.affiche)}" alt="">` : ""}</div>
        <div class="tx"><span class="k">Prochain : n° ${iSuivant + 1}</span><b>${esc(s.titre)}</b>
          <span class="muted petit">${esc(legendeCarte(s).txt)}</span></div>
        ${ic("chev", "s18 muted")}</div>` : `<div class="prochain fini">${ic("checks", "s22 okc")}<div class="tx"><b>Tout est vu</b><span class="muted petit">Bravo, la liste est terminée.</span></div></div>`)
      + `<div class="ordre">${items.map((t, i) => htmlLigneOrdre(t, i, i === iSuivant, perso)).join("")}</div>`;
  } else {
    corps = `<div class="grille">${items.map((t) => htmlCarte(t)).join("")}</div>`;
  }
  $("#lst-detail").innerHTML = `<div class="liste-h">
      <button type="button" class="btn sm gh" data-lst-retour aria-label="Retour aux listes">${ic("chevl", "s18")}<span class="lib">Listes</span></button>
      <h1 class="ttl">${esc(L.nom)}</h1>
      ${perso ? `<label class="ligne soft petit lst-ordre" title="Numéroter les titres, pour une saga"><input type="checkbox" class="sw" data-lst-ordre${L.ordonnee ? " checked" : ""}> Dans l'ordre</label>
        <button type="button" class="btn sm" data-lst-renommer>${ic("edit", "s18")}Renommer</button>
        <button type="button" class="btn sm dn ico" data-lst-suppr title="Supprimer la liste" aria-label="Supprimer la liste">${ic("trash", "s18")}</button>` : ""}
    </div>
    ${regle ? `<p class="muted petit" style="margin:-4px 0 12px">${esc(regle)}</p>` : ""}
    ${items.length ? `<div class="liste-prog"><div class="pg epais${pct >= 100 ? " ok" : " acc"}"><i style="width:${pct}%"></i></div><span>${nb(vus)} / ${nb(items.length)} vus</span></div>` : ""}
    ${corps}`;
  majToutesFleches($("#lst-detail"));
  majNavActive();
}

function htmlLigneOrdre(t, i, suivant, perso) {
  const vu = dejaVu(t);
  return `<div class="ord${vu ? " vu" : ""}${suivant ? " suivant" : ""}" data-k="${cleDe(t)}" data-id="${t.lid}">
    <span class="num">${i + 1}</span>
    <div class="mini" data-ord-ouvrir>${t.affiche ? `<img src="${posterSrc(t.affiche)}" alt="" loading="lazy">` : ""}</div>
    <div class="tx" data-ord-ouvrir><b>${esc(t.titre)}</b><span>${esc(legendeCarte(t).txt)}</span></div>
    <span class="ck${vu ? " on" : ""}" aria-label="${vu ? "Vu" : "Pas encore vu"}" role="img">${vu ? ic("check", "s16") : ""}</span>
    <button type="button" class="ib" data-ord-menu aria-label="Actions pour ${esc(t.titre)}">${ic("dots", "s18")}</button>
    ${perso ? `<button type="button" class="poignee" data-poignee aria-label="Déplacer ${esc(t.titre)} (flèches haut et bas)">${ic("grip")}</button>` : ""}
  </div>`;
}

/* Retirer un titre d'une liste perso, avec « Annuler » (remis à sa place). */
async function retirerDeListe(D, t) {
  const ordre = D.items.map((x) => x.lid);
  try {
    await api(`/api/lists/${D.id}/items/${t.lid}`, { method: "DELETE" });
  } catch (e) { toastErr(e); return; }
  D.items = D.items.filter((x) => x !== t);
  if (Listes.detail === D) rendreDetail(D);
  signaler("listes", { id: D.id });
  toast(`Retiré de « ${D.liste.nom} »`, {
    annuler: async () => {
      await api(`/api/lists/${D.id}/items`, { method: "POST", body: { titre_id: t.lid } });
      if (D.liste.ordonnee) await api(`/api/lists/${D.id}/ordre`, { method: "PUT", body: { titres: ordre } });
    },
    apres: () => { signaler("listes", { id: D.id }); if (Listes.detail === D) chargerDetail(D, { calme: true }); },
  });
}
EXTRAS_MENU.push((t, el) => {
  const D = Listes.detail;
  if (!D || !D.liste || D.liste.systeme || !t.lid || !el.closest("#lst-detail")) return [];
  return [{ ic: "minus", txt: `Retirer de « ${D.liste.nom} »`, f: () => retirerDeListe(D, t) }];
});

async function enregistrerOrdre(D) {
  const ids = $$("#lst-detail .ord[data-id]").map((r) => Number(r.dataset.id));
  D.items.sort((a, b) => ids.indexOf(a.lid) - ids.indexOf(b.lid));
  // Au clavier, la poignée garde le focus après le nouveau rendu.
  const focus = document.activeElement?.closest?.("#lst-detail .ord[data-id]")?.dataset.id;
  rendreDetail(D);
  if (focus) $(`#lst-detail .ord[data-id="${focus}"] [data-poignee]`)?.focus();
  try {
    await api(`/api/lists/${D.id}/ordre`, { method: "PUT", body: { titres: ids } });
    toast("Ordre enregistré");
    signaler("listes", { id: D.id });
  } catch (e) { toastErr(e); chargerDetail(D, { calme: true }); }
}
const enregistrerOrdreBientot = plusTard((D) => enregistrerOrdre(D), 700);

/* Glisser la poignée pour changer l'ordre (L3). */
function glisserOrdre(e) {
  const h = e.target.closest("[data-poignee]");
  const D = Listes.detail;
  if (!h || !D || e.button !== 0) return;
  const row = h.closest(".ord");
  const box = row.parentElement;
  const rows = $$(".ord", box);
  const i0 = rows.indexOf(row);
  if (i0 < 0) return;
  e.preventDefault();
  h.setPointerCapture(e.pointerId);
  const hauts = rows.map((r) => { const b = r.getBoundingClientRect(); return { y: b.top + scrollY, h: b.height }; });
  const y0 = e.clientY + scrollY;
  let cible = i0, dernierY = e.clientY, defile = 0;
  box.classList.add("tri-encours");
  row.classList.add("glisse");
  const placer = () => {
    const dy = dernierY + scrollY - y0;
    row.style.transform = `translateY(${dy}px)`;
    const centre = hauts[i0].y + hauts[i0].h / 2 + dy;
    cible = hauts.filter((r, j) => j !== i0 && r.y + r.h / 2 < centre).length;
    rows.forEach((r, j) => {
      if (j === i0) return;
      let decal = 0;
      if (i0 < cible && j > i0 && j <= cible) decal = -hauts[i0].h;
      if (i0 > cible && j < i0 && j >= cible) decal = hauts[i0].h;
      r.style.transform = decal ? `translateY(${decal}px)` : "";
    });
  };
  // Près du haut ou du bas de l'écran, la page défile toute seule.
  const boucle = () => {
    if (!row.classList.contains("glisse")) return;
    const v = dernierY < 90 ? -10 : dernierY > innerHeight - 110 ? 10 : 0;
    if (v) { scrollBy(0, v); placer(); }
    defile = requestAnimationFrame(boucle);
  };
  defile = requestAnimationFrame(boucle);
  const bouge = (ev) => { dernierY = ev.clientY; placer(); };
  const fin = () => {
    cancelAnimationFrame(defile);
    h.removeEventListener("pointermove", bouge);
    h.removeEventListener("pointerup", fin);
    h.removeEventListener("pointercancel", fin);
    rows.forEach((r) => { r.style.transform = ""; });
    row.classList.remove("glisse");
    box.classList.remove("tri-encours");
    if (cible === i0) return;
    const autres = rows.filter((r) => r !== row);
    if (cible >= autres.length) box.append(row); else box.insertBefore(row, autres[cible]);
    vibrer(10);
    enregistrerOrdre(D);
  };
  h.addEventListener("pointermove", bouge);
  h.addEventListener("pointerup", fin);
  h.addEventListener("pointercancel", fin);
}

function deplacerLigne(D, row, sens) {
  const box = row.parentElement;
  const voisin = sens < 0 ? row.previousElementSibling : row.nextElementSibling;
  if (!voisin) return;
  if (sens < 0) box.insertBefore(row, voisin); else box.insertBefore(voisin, row);
  $$(".ord", box).forEach((r, i) => { r.querySelector(".num").textContent = String(i + 1); });
  row.querySelector("[data-poignee]")?.focus();
  enregistrerOrdreBientot(D);
}

const _lstDetail = $("#lst-detail");
_lstDetail?.addEventListener("pointerdown", glisserOrdre);
_lstDetail?.addEventListener("keydown", (e) => {
  const D = Listes.detail;
  const h = e.target.closest("[data-poignee]");
  if (h && D && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
    e.preventDefault();
    deplacerLigne(D, h.closest(".ord"), e.key === "ArrowUp" ? -1 : 1);
    return;
  }
  const o = e.target.closest(".prochain[data-ord-ouvrir]");
  if (o && D && (e.key === "Enter" || e.key === " ")) {
    e.preventDefault();
    const t = TITRES.get(o.dataset.k);
    if (t) activerTitre(t, o);
  }
});
_lstDetail?.addEventListener("click", async (e) => {
  const D = Listes.detail;
  if (!D) return;
  if (e.target.closest("[data-lst-retour]")) { Couches.fermer(D.couche); return; }
  if (e.target.closest("[data-poignee]")) return;
  const menu = e.target.closest("[data-ord-menu]");
  if (menu) {
    const row = menu.closest(".ord");
    const t = TITRES.get(row.dataset.k);
    if (!t) return;
    const perso = !D.liste.systeme;
    const items = [["fiche", "info", "Ouvrir la fiche"], ["menu", "zap", "Actions rapides (vu, à voir…)"]];
    if (perso && row.previousElementSibling) items.push(["haut", "chevu", "Monter"]);
    if (perso && row.nextElementSibling) items.push(["bas", "chevd", "Descendre"]);
    if (perso) items.push(["retirer", "minus", `Retirer de « ${D.liste.nom} »`, true]);
    menuAdapte(items, menu, (a) => {
      if (a === "fiche") ouvrirFiche(t);
      else if (a === "menu") ouvrirMenu(t, { depuis: row });
      else if (a === "haut" || a === "bas") deplacerLigne(D, row, a === "haut" ? -1 : 1);
      else if (a === "retirer") retirerDeListe(D, t);
    }, t.titre);
    return;
  }
  const ouvrir = e.target.closest("[data-ord-ouvrir]");
  if (ouvrir) {
    const el = ouvrir.closest("[data-k]");
    const t = el && TITRES.get(el.dataset.k);
    if (t) activerTitre(t, el);
    return;
  }
  const ordre = e.target.closest("[data-lst-ordre]");
  if (ordre) {
    const on = ordre.checked;
    ordre.disabled = true;
    try {
      await api(`/api/lists/${D.id}`, { method: "PATCH", body: { ordonnee: on } });
      D.liste.ordonnee = on;
      toast(on ? "Liste numérotée : dans l'ordre" : "Liste sans ordre");
      rendreDetail(D);
      signaler("listes", { id: D.id });
    } catch (err) { ordre.checked = !on; toastErr(err); }
    finally { ordre.disabled = false; }
    return;
  }
  if (e.target.closest("[data-lst-renommer]")) {
    const nom = await demander("Renommer la liste", { label: "Nouveau nom", valeur: D.liste.nom, ok: "Renommer" });
    if (!nom || nom === D.liste.nom) return;
    try {
      await api(`/api/lists/${D.id}`, { method: "PATCH", body: { nom } });
      D.liste.nom = nom;
      rendreDetail(D);
      toast("Liste renommée");
      signaler("listes", { id: D.id });
    } catch (err) { toastErr(err); }
    return;
  }
  if (e.target.closest("[data-lst-suppr]")) {
    const ok = await confirmer(`Supprimer la liste « ${D.liste.nom} » ?`, {
      ok: "Supprimer", danger: true, detail: "Les titres restent dans ta bibliothèque : seule la liste disparaît." });
    if (!ok) return;
    try {
      await api(`/api/lists/${D.id}`, { method: "DELETE" });
      toast(`Liste « ${D.liste.nom} » supprimée`);
      signaler("listes", { id: D.id, supprimee: true });
      Couches.fermer(D.couche);
    } catch (err) { toastErr(err); }
  }
});

/* Un titre marqué ailleurs : la liste ouverte se remet à jour (ordre, « Prochain »). */
const majDetailListe = plusTard(() => { if (Listes.detail && Listes.detail.liste) chargerDetail(Listes.detail, { calme: true }); }, 600);
const majIndexListes = plusTard(() => { if (Nav.page === "listes" && !Listes.detail) chargerListes(); }, 600);
document.addEventListener("ct:titre", () => { if (Listes.detail) majDetailListe(); else majIndexListes(); });
document.addEventListener("ct:listes", majIndexListes);

/* ----------------------------------------------- listes prêtes et import */
async function ouvrirPresets() {
  const f = feuille({ titre: "Listes prêtes", html: squeletteLignes(4) });
  try {
    const { presets = [] } = await api("/api/lists/presets");
    if (f.ferme) return;
    f.corps.innerHTML = `<p class="soft petit" style="margin-bottom:8px">Choisis une saga : ses titres sont ajoutés à ta bibliothèque (« À voir plus tard ») et rangés dans une nouvelle liste, dans l'ordre.</p>
      <div>${presets.map((p) => `<div class="preset"><div class="tx"><b>${esc(p.nom)}</b><span>${pluriel(p.nb, "titre")}</span></div>
        <button type="button" class="btn sm pri" data-preset="${esc(p.cle)}">${ic("download", "s18")}Importer</button></div>`).join("")}</div>`;
  } catch (e) { f.corps.innerHTML = erreurHtml(e); return; }
  f.el.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-preset]");
    if (!b) return;
    await occupe(b, async () => {
      try {
        const r = await api("/api/lists/import-preset", { method: "POST", body: { cle: b.dataset.preset } });
        toast(`Liste créée : ${pluriel(r.ajoutes, "titre ajouté", "titres ajoutés")}`);
        MaBiblio.perimer();
        signaler("listes", { id: r.id });
        await f.fermer();
        Nav.lien("listes", String(r.id));
      } catch (err) { toastErr(err); }
    });
  });
}

function ouvrirImport() {
  const f = feuille({
    titre: "Importer une liste",
    html: `<form class="form" id="imp-form">
      <div><label class="lbl" for="imp-nom">Nom de la liste</label>
        <input class="input" id="imp-nom" name="nom" placeholder="Liste importée" maxlength="80" autocomplete="off"></div>
      <div><label class="lbl" for="imp-json">Titres (JSON), dans l'ordre</label>
        <textarea class="input mono" id="imp-json" name="json" rows="6" spellcheck="false" placeholder='[{"tmdb_id":1726,"type":"film"}, {"tmdb_id":1399,"type":"serie"}]'></textarea>
        <p class="muted petit">Chaque titre est cherché sur TMDB puis ajouté à ta bibliothèque. 200 titres au plus.</p></div>
      <div class="ligne"><button type="button" class="btn sm" data-imp-fichier>${ic("upload", "s18")}Depuis un fichier</button>
        <input type="file" accept="application/json,.json,.txt" hidden data-imp-input></div>
      <button class="btn pri w" type="submit">${ic("download", "s18")}Importer</button>
    </form>`,
  });
  const form = f.el.querySelector("#imp-form");
  const fichier = f.el.querySelector("[data-imp-input]");
  f.el.querySelector("[data-imp-fichier]").addEventListener("click", () => fichier.click());
  fichier.addEventListener("change", async () => {
    const fi = fichier.files && fichier.files[0];
    if (!fi) return;
    form.json.value = await fi.text();
    if (!form.nom.value) form.nom.value = fi.name.replace(/\.[^.]+$/, "");
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    let items;
    try {
      items = JSON.parse(form.json.value);
      if (items && !Array.isArray(items) && Array.isArray(items.items)) items = items.items;
      if (!Array.isArray(items) || !items.length) throw new Error();
    } catch (_) {
      toast("Le texte n'est pas une liste JSON valide (voir l'exemple).", { erreur: true });
      form.json.focus();
      return;
    }
    await occupe(form.querySelector("[type=submit]"), async () => {
      try {
        const r = await api("/api/lists/import", { method: "POST", body: { nom: form.nom.value.trim() || "Liste importée", items } });
        toast(`Liste importée : ${pluriel(r.ajoutes, "titre ajouté", "titres ajoutés")}`);
        MaBiblio.perimer();
        signaler("listes", { id: r.id });
        await f.fermer();
        Nav.lien("listes", String(r.id));
      } catch (err) { toastErr(err); }
    });
  });
}
$("#lst-presets")?.addEventListener("click", () => ouvrirPresets());
$("#lst-import")?.addEventListener("click", () => ouvrirImport());

Pages.listes = {
  afficher(sous) {
    const id = Number(sous);
    if (sous && id) { ouvrirListe(id); return; }
    if (Listes.detail) fermerDetailListe();
    chargerListes();
  },
};
