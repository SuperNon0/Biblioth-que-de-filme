/* =========================================================================
   cinéthèque — navigation : pages, menu de gauche (N2), barre d'onglets en
   verre (N1), feuille « Plus » (N4) et recherche partout « Ctrl K » (N3).
   Une page = une ancre (#accueil, #bibliotheque…) ; les sous-pages (une
   liste, un réglage sur téléphone) s'empilent dans l'historique : le bouton
   retour du téléphone y revient.
   ========================================================================= */
"use strict";

const PAGES = ["accueil", "bibliotheque", "decouvrir", "futur", "listes", "profil", "parametres", "aide"];
const NOMS_PAGES = { accueil: "Accueil", bibliotheque: "Bibliothèque", decouvrir: "Découvrir", futur: "Futur",
  listes: "Listes", profil: "Profil", parametres: "Paramètres", aide: "Aide" };
const PAGES_PLUS = new Set(["listes", "profil", "parametres", "aide"]);
/* Chaque page s'inscrit ici : Pages.x = { afficher(sous, {change}) }. */
const Pages = {};

function lireHash(h = location.hash) {
  const [page, ...reste] = decodeURIComponent(String(h || "").replace(/^#/, "")).split("/");
  return { page: PAGES.includes(page) ? page : null, sous: reste.join("/") || null };
}

const Nav = {
  page: null,
  sous: null,
  _defil: {},

  aller(page, { sous = null, url = true } = {}) {
    if (!PAGES.includes(page)) page = "accueil";
    const change = page !== this.page;
    if (change && this.page) this._defil[this.page] = scrollY;
    if (change) {
      $$(".page").forEach((p) => p.classList.toggle("on", p.dataset.page === page));
      this.page = page;
      majNavActive();
      document.title = page === "accueil" ? "cinéthèque" : `${NOMS_PAGES[page]} · cinéthèque`;
    }
    this.sous = sous;
    if (url) history.replaceState(history.state, "", `#${page}${sous ? "/" + sous : ""}`);
    const mod = Pages[page];
    if (mod && mod.afficher) {
      try { mod.afficher(sous, { change }); } catch (e) { console.error(e); }
    }
    if (change) scrollTo(0, this._defil[page] || 0);
    majNavActive();
  },

  /* Lien interne : referme d'abord fiche, feuilles et sous-pages ouvertes. */
  async lien(page, sous = null) {
    if (Couches.ouvertes) await Couches.fermerTout();
    this.aller(page, { sous });
  },

  /* Sous-page dans l'historique (#listes/12) : retour = page parente. */
  sousVue(sous, fermer) {
    const page = this.page;
    history.replaceState(history.state, "", `#${page}`);
    this.sous = sous;
    majNavActive();
    return Couches.ouvrir(() => {
      if (this.page === page && this.sous === sous) this.sous = null;
      fermer();
      majNavActive();
    }, { url: `#${page}/${sous}`, vue: true });
  },
};

function majNavActive() {
  const p = Nav.page;
  $$(".side-it[data-page]").forEach((a) => a.classList.toggle("on", a.dataset.page === p && !(p === "listes" && Nav.sous)));
  $$(".side-it[data-liste]").forEach((a) => a.classList.toggle("on", p === "listes" && Nav.sous === a.dataset.liste));
  $$(".tab[data-page]").forEach((a) => {
    const on = a.dataset.page === p;
    a.classList.toggle("on", on);
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  $(".tab[data-plus]")?.classList.toggle("on", PAGES_PLUS.has(p));
}

/* Liens #page et #page/sous : sans rechargement. */
document.addEventListener("click", (e) => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const a = e.target.closest('a[href^="#"]');
  if (!a) return;
  const { page, sous } = lireHash(a.getAttribute("href"));
  if (!page) return;
  e.preventDefault();
  Nav.lien(page, sous);
});
/* Adresse modifiée à la main. */
addEventListener("hashchange", () => {
  const { page, sous } = lireHash();
  if (!page || (page === Nav.page && sous === Nav.sous)) return;
  Nav.lien(page, sous);
});

/* Ombre sous la barre du haut dès qu'on défile. */
addEventListener("scroll", () => {
  $("#top")?.classList.toggle("ombre", scrollY > 4);
}, { passive: true });

/* ----------------------------------------------------- menu de gauche (N2) */
const majSideListes = plusTard(async () => {
  const box = $("#side-listes");
  if (!box || !ecranOrdi()) return;
  try {
    const { listes } = await api("/api/lists");
    box.innerHTML = listes.length ? listes.map((l) => `<a class="side-it" href="#listes/${l.id}" data-liste="${l.id}">
        <span class="dot${l.systeme_flag ? " sys" : l.ordonnee ? " ordo" : ""}" aria-hidden="true"></span>
        <span class="nom">${esc(l.nom)}</span><span class="n">${l.nb ? nb(l.nb) : ""}</span></a>`).join("")
      : `<p class="vide-l">Aucune liste pour l'instant.</p>`;
    majNavActive();
  } catch (_) { /* le menu garde l'ancienne version */ }
}, 400);
document.addEventListener("ct:listes", majSideListes);
document.addEventListener("ct:titre", majSideListes);
matchMedia("(min-width: 1000px)").addEventListener?.("change", (m) => { if (m.matches) majSideListes(); });

/* Version du site (menu de gauche, Paramètres → Version). */
let _version = null;
function chargerVersion(forcer = false) {
  if (!_version || forcer) {
    _version = api("/api/version").catch((e) => { _version = null; throw e; });
  }
  return _version;
}
async function afficherVersion() {
  try {
    const v = await chargerVersion();
    const el = $("#side-ver");
    if (el && v.version) el.textContent = "v" + v.version;
  } catch (_) { /* hors ligne : pas de numéro */ }
}

/* ----------------------------------------------------- feuille « Plus » (N4) */
async function deconnecter() {
  await purgeShell();
  const f = document.createElement("form");
  f.method = "post";
  f.action = CT.logout || "/logout";
  document.body.append(f);
  f.submit();
}
document.addEventListener("submit", (e) => {
  if (!e.target.matches(".form-deco")) return;
  e.preventDefault();
  deconnecter();
});

function ouvrirPlus() {
  feuille({
    titre: "Plus",
    html: `<div class="q-tuiles plus-t">
        <a class="qt" href="#listes">${ic("list", "s22")}Listes</a>
        <a class="qt" href="#profil">${ic("chart", "s22")}Profil</a>
        <a class="qt" href="#parametres">${ic("gear", "s22")}Paramètres</a>
        <a class="qt" href="#aide">${ic("help", "s22")}Aide</a>
      </div>
      <div class="liste-r">
        ${CAPS.comptes ? `<a class="li" href="${esc(CT.comptes)}"><span class="li-ic">${ic("users")}</span><span class="tx">Comptes et profils<small>Accès, « voir en tant que »</small></span>${ic("chev", "s18 muted")}</a>` : ""}
        ${CAPS.maj ? `<a class="li" href="#parametres/site"><span class="li-ic">${ic("refresh")}</span><span class="tx">Mettre à jour le site<small data-plus-ver>Version…</small></span>${ic("chev", "s18 muted")}</a>` : ""}
        <button type="button" class="li" data-deco><span class="li-ic">${ic("logout")}</span><span class="tx">Se déconnecter${CT.moi ? `<small>${esc(CT.moi)}</small>` : ""}</span></button>
      </div>`,
  }).el.addEventListener("click", (e) => {
    if (e.target.closest("[data-deco]")) deconnecter();
  });
  chargerVersion().then((v) => {
    const el = $("[data-plus-ver]");
    if (el) el.textContent = `Version installée : ${v.version}`;
  }).catch(() => {});
}

/* ------------------------------------------------ recherche partout (N3) */
const sansAccents = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

const COMMANDES = [
  { t: "Nouvelle liste", s: "Créer une liste", i: "listplus", f: () => nouvelleListe() },
  { t: "Paramètres", s: "Tous les réglages", i: "gear", f: () => Nav.lien("parametres") },
  { t: "Apparence", s: "Couleur d'accent, thème clair ou sombre", i: "palette", mots: "couleur theme sombre clair", f: () => Nav.lien("parametres", "apparence") },
  { t: "Mes plateformes", s: "Tes abonnements de streaming", i: "tv", si: () => SUPER_ADMIN, f: () => Nav.lien("parametres", "plateformes") },
  { t: "Que regarder ?", s: "Au hasard dans « À voir plus tard »", i: "dice", mots: "hasard roulette", f: () => ouvrirRoulette("library") },
  { t: "Ajouter un titre absent de TMDB", s: "Ajout manuel", i: "edit", mots: "manuel", f: () => ajoutManuel() },
  { t: "Bibliothèque", i: "lib", f: () => Nav.lien("bibliotheque") },
  { t: "Découvrir", s: "Le catalogue, par genre", i: "compass", f: () => Nav.lien("decouvrir") },
  { t: "Futur", s: "Les sorties au cinéma", i: "bell", mots: "sorties cinema alertes", f: () => Nav.lien("futur") },
  { t: "Listes", i: "list", f: () => Nav.lien("listes") },
  { t: "Profil", s: "Statistiques et journal", i: "chart", mots: "stats statistiques journal historique", f: () => Nav.lien("profil") },
  { t: "Aide", s: "Questions fréquentes", i: "help", mots: "faq raccourcis", f: () => Nav.lien("aide") },
];

let palette = null;

function ouvrirPalette(texte = "") {
  if (palette) { palette.champ.focus(); return; }
  const voile = document.createElement("div");
  voile.className = "voile flou";
  const el = document.createElement("div");
  el.className = "palette";
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-modal", "true");
  el.setAttribute("aria-label", "Rechercher");
  el.innerHTML = `<label class="champ">${ic("search", "s18")}
      <input type="search" placeholder="Un titre, une personne, un réglage…" autocomplete="off" enterkeyhint="search"
        aria-label="Rechercher" aria-controls="pal-res" aria-autocomplete="list">
      <button type="button" class="kbd" data-fermer>${pointeurFin() ? "Échap" : "Annuler"}</button></label>
    <div class="res-p" id="pal-res" role="listbox"></div>
    <div class="pal-pied"><span><span class="kbd">↑</span> <span class="kbd">↓</span> choisir</span><span><span class="kbd">Entrée</span> ouvrir</span><span><span class="kbd">Échap</span> fermer</span></div>`;
  document.body.append(voile, el);
  const champ = el.querySelector("input");
  const res = el.querySelector(".res-p");
  const avant = document.activeElement;
  let items = [], sel = 0, seq = 0, ctrl = null;
  let ferme = false;
  const retirer = () => {
    if (ferme) return;
    ferme = true;
    if (ctrl) ctrl.abort();
    voile.remove(); el.remove();
    palette = null;
    if (avant && avant.focus && document.contains(avant)) avant.focus({ preventScroll: true });
  };
  const couche = Couches.ouvrir(retirer, { el });
  const fermer = () => (ferme ? Promise.resolve() : Couches.fermer(couche));
  palette = { el, champ, fermer };
  voile.addEventListener("click", fermer);
  el.querySelector("[data-fermer]").addEventListener("click", fermer);

  const ligne = (it, i) => {
    const on = i === sel ? " on" : "";
    if (it.k === "cmd") {
      return `<button type="button" class="pal-it${on}" role="option" data-i="${i}"><span class="ico">${ic(it.c.i, "s18")}</span>
        <span class="tx"><b>${esc(it.c.t)}</b>${it.c.s ? `<span>${esc(it.c.s)}</span>` : ""}</span></button>`;
    }
    if (it.k === "pers") {
      const p = it.p;
      return `<button type="button" class="pal-it${on}" role="option" data-i="${i}"><span class="mini rond">${p.photo ? `<img src="${posterSrc(p.photo)}" alt="" loading="lazy">` : ""}</span>
        <span class="tx"><b>${esc(p.nom)}</b><span>${esc([p.metier, (p.connu_pour || []).join(", ")].filter(Boolean).join(" · "))}</span></span></button>`;
    }
    const t = it.t;
    const etq = t.statut ? `<span class="etq ${t.statut}">${esc(etiquetteStatut(t))}</span>`
      : `<span class="etq" data-ajout="${i}" role="button" title="Ajouter à « À voir plus tard »">${ic("plus", "s16")}À voir</span>`;
    const lg = legendeCarte(t);
    return `<button type="button" class="pal-it${on}" role="option" data-i="${i}"><span class="mini">${t.affiche ? `<img src="${posterSrc(t.affiche)}" alt="" loading="lazy">` : ""}</span>
      <span class="tx"><b>${esc(t.titre)}</b><span>${esc(lg.txt)}</span></span>${etq}</button>`;
  };
  const rendre = (groupes) => {
    items = [];
    let html = "";
    for (const g of groupes) {
      if (!g.items.length) continue;
      html += `<div class="pal-g">${ic(g.i, "s16")}${esc(g.t)}</div>`;
      for (const it of g.items) { html += ligne(it, items.length); items.push(it); }
    }
    if (sel >= items.length) sel = 0;
    res.innerHTML = html || (champ.value.trim().length > 1 ? `<p class="muted petit" style="padding:12px 10px">Rien trouvé pour « ${esc(champ.value.trim())} ».</p>` : "");
  };
  const majSel = () => {
    $$(".pal-it", res).forEach((b) => b.classList.toggle("on", Number(b.dataset.i) === sel));
    const b = res.querySelector(`.pal-it[data-i="${sel}"]`);
    if (b) b.scrollIntoView({ block: "nearest" });
  };

  const chercher = async () => {
    const q = champ.value.trim();
    const nq = sansAccents(q);
    const my = ++seq;
    if (ctrl) ctrl.abort();
    const cmds = COMMANDES.filter((c) => (!c.si || c.si()) && (!nq || sansAccents(`${c.t} ${c.s || ""} ${c.mots || ""}`).includes(nq)))
      .slice(0, nq ? 4 : 6).map((c) => ({ k: "cmd", c }));
    const biblio = MaBiblio.titres || [];
    const locaux = nq ? biblio.filter((t) => sansAccents(t.titre).includes(nq)).slice(0, 6)
      : biblio.filter((t) => t.statut === "en_cours").slice(0, 4);
    const groupes = [
      { t: nq ? "Ta bibliothèque" : "En cours", i: "lib", items: locaux.map((t) => ({ k: "t", t })) },
      { t: "Raccourcis", i: "zap", items: cmds },
    ];
    sel = 0;
    rendre(groupes);
    if (q.length < 2 || !CT.tmdb) return;
    ctrl = new AbortController();
    try {
      const [tm, pe] = await Promise.all([
        api(`/api/search?q=${encodeURIComponent(q)}`, { signal: ctrl.signal }),
        q.length >= 3 ? api(`/api/search/person?q=${encodeURIComponent(q)}`, { signal: ctrl.signal }).catch(() => ({ results: [] }))
          : Promise.resolve({ results: [] }),
      ]);
      if (my !== seq || ferme) return;
      const dejaLa = new Set(locaux.map(cleDe));
      const ext = (tm.results || []).map(retenir).filter((t) => !dejaLa.has(cleDe(t))).slice(0, 8);
      groupes.push({ t: "Sur TMDB", i: "sparkle", items: ext.map((t) => ({ k: "t", t })) });
      groupes.push({ t: "Personnes", i: "users", items: (pe.results || []).slice(0, 3).map((p) => ({ k: "pers", p })) });
      rendre(groupes);
    } catch (e) {
      if (e.name !== "AbortError" && my === seq) toastErr(e);
    }
  };
  const chercherBientot = plusTard(chercher, 220);
  if (!MaBiblio.titres) MaBiblio.charger().then(() => { if (!ferme) chercher(); }).catch(() => {});

  const lancer = async (i, ajout = false) => {
    const it = items[i];
    if (!it) return;
    if (ajout && it.k === "t") {
      const b = res.querySelector(`[data-ajout="${i}"]`);
      if (await agir(it.t, "aVoir", b)) chercher();
      return;
    }
    await fermer();
    if (it.k === "cmd") it.c.f();
    else if (it.k === "pers") ouvrirPersonne(it.p.id);
    else ouvrirFiche(it.t);
  };
  res.addEventListener("click", (e) => {
    const plus = e.target.closest("[data-ajout]");
    const b = e.target.closest(".pal-it");
    if (b) lancer(Number(b.dataset.i), !!plus);
  });
  res.addEventListener("pointermove", (e) => {
    const b = e.target.closest(".pal-it");
    if (b && Number(b.dataset.i) !== sel) { sel = Number(b.dataset.i); majSel(); }
  });
  champ.addEventListener("input", chercherBientot);
  champ.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!items.length) return;
      sel = (sel + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      majSel();
    } else if (e.key === "Enter") {
      e.preventDefault();
      lancer(sel);
    }
  });
  champ.value = texte;
  chercher();
  setTimeout(() => champ.focus(), 30);
}

/* Ctrl K (ou ⌘ K) et « / » : recherche partout. */
addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    if (palette) palette.fermer(); else ouvrirPalette();
  } else if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey && !enSaisie(document.activeElement) && !Couches.pile.some((c) => !c.vue)) {
    e.preventDefault();
    ouvrirPalette();
  }
});
document.addEventListener("click", (e) => {
  if (e.target.closest("[data-palette]")) { e.preventDefault(); ouvrirPalette(); }
  else if (e.target.closest("[data-plus]")) { e.preventDefault(); ouvrirPlus(); }
  else if (e.target.closest("[data-nouvelle-liste]")) { e.preventDefault(); nouvelleListe(); }
});
