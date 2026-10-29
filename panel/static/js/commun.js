/* =========================================================================
   cinéthèque — outils communs (JavaScript sans dépendance ni compilation).
   Chargé en premier : sélecteurs, appels d'API, dates, messages avec
   « Annuler », couches (fiche, feuilles, menus) liées au bouton retour du
   téléphone, confirmations, bulles « ? », préférences d'affichage.
   Les fichiers suivants partagent la portée globale des scripts classiques ;
   le démarrage se fait dans demarrage.js, chargé en dernier.
   ========================================================================= */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/* Configuration posée par le serveur : rôle, préférences, droits. */
const CT = (() => {
  try { return JSON.parse(document.getElementById("ct-config")?.textContent || "{}"); }
  catch (_) { return {}; }
})();
const SUPER_ADMIN = !!CT.superAdmin;
const CAPS = CT.caps || {};

const ecranOrdi = () => matchMedia("(min-width: 1000px)").matches;
const ecranLarge = () => matchMedia("(min-width: 760px)").matches;
const pointeurFin = () => matchMedia("(hover: hover) and (pointer: fine)").matches;

/* Icône du jeu dessiné (templates/_icons.html). */
function ic(nom, cls = "") {
  return `<svg class="i${cls ? " " + cls : ""}" aria-hidden="true"><use href="#i-${nom}"/></svg>`;
}

function esc(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
const IMG_VIDE = "data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27/%3E";
// URL d'image prête pour un attribut HTML (échappée), ou une image vide.
const posterSrc = (u) => u ? esc(u) : IMG_VIDE;
// Valeur sûre pour url('…') dans un attribut style (guillemets, parenthèses…).
const cssUrl = (u) => esc(String(u || "").replace(/[\x00-\x20'"()\\]/g,
  (c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0")));

const plusTard = (fn, ms = 250) => {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
};
function vibrer(ms = 8) {
  try { if (navigator.vibrate) navigator.vibrate(ms); } catch (_) { /* refusé */ }
}
/* Évènements internes : « ct:titre » (un titre a changé), « ct:listes »… */
function signaler(type, detail = {}) {
  document.dispatchEvent(new CustomEvent("ct:" + type, { detail }));
}

/* ------------------------------------------------------------- appels API */
// Recharge la page pour repasser par la connexion, au plus une fois par minute
// (évite une boucle de rechargements si le serveur est simplement injoignable).
function reloadForLogin() {
  let last = 0;
  try { last = Number(sessionStorage.getItem("ct-reload")) || 0; } catch (_) { /* privé */ }
  if (Date.now() - last < 60000) return;
  try { sessionStorage.setItem("ct-reload", String(Date.now())); } catch (_) { /* privé */ }
  location.reload();
}

async function api(path, { method = "GET", body, signal } = {}) {
  // X-Cinetheque : preuve que l'appel vient de notre propre page (anti-CSRF).
  const opts = { method, headers: { "X-Cinetheque": "1" }, signal };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let resp;
  try {
    resp = await fetch(path, opts);
  } catch (err) {
    if (err && err.name === "AbortError") throw err;
    // En ligne mais requête bloquée : en pratique, session Cloudflare expirée
    // (redirection vers sa page de connexion). On recharge pour se reconnecter.
    if (navigator.onLine) reloadForLogin();
    throw new Error(navigator.onLine ? "Le site ne répond pas." : "Pas de connexion internet.");
  }
  // Session de l'app expirée : retour au parcours de connexion.
  if (resp.status === 401) { reloadForLogin(); throw new Error("Session expirée."); }
  let data = {};
  try { data = await resp.json(); } catch (_) { /* réponse vide */ }
  if (!resp.ok) throw new Error(data.error || `Erreur ${resp.status}`);
  return data;
}

/* ------------------------------------------------------------------ dates */
const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
  "août", "septembre", "octobre", "novembre", "décembre"];
const MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
  "sept.", "oct.", "nov.", "déc."];
const JOURS = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];
const deux = (n) => String(n).padStart(2, "0");
const majuscule = (s) => s ? s[0].toUpperCase() + s.slice(1) : s;

function isoLocal(d = new Date()) {
  return `${d.getFullYear()}-${deux(d.getMonth() + 1)}-${deux(d.getDate())}`;
}
function dateDe(iso) {
  const [a, m, j] = String(iso || "").slice(0, 10).split("-").map(Number);
  return new Date(a, (m || 1) - 1, j || 1);
}
/* Jours entre aujourd'hui et une date (négatif : passée). */
function joursJusqua(iso) {
  return Math.round((dateDe(iso) - dateDe(isoLocal())) / 86400000);
}
/* « 4 novembre », « 4 nov. 2027 » (année seulement si ce n'est pas l'année en cours). */
function fmtDate(iso, { court = false, annee = "auto" } = {}) {
  if (!iso) return "";
  const d = dateDe(iso);
  if (isNaN(d)) return String(iso);
  const jour = d.getDate() === 1 ? "1er" : String(d.getDate());
  const avecAnnee = annee === true || (annee === "auto" && d.getFullYear() !== new Date().getFullYear());
  return `${jour} ${(court ? MOIS_COURTS : MOIS)[d.getMonth()]}${avecAnnee ? " " + d.getFullYear() : ""}`;
}
/* « Mercredi 4 novembre ». */
function fmtJour(iso) {
  const d = dateDe(iso);
  return majuscule(`${JOURS[d.getDay()]} ${fmtDate(iso)}`);
}
/* « aujourd'hui », « demain », « dans 6 jours », « dans 3 semaines »… */
function dans(n) {
  if (n === 0) return "aujourd'hui";
  if (n === 1) return "demain";
  if (n === -1) return "hier";
  if (n < 0) return `il y a ${-n} jours`;
  if (n < 14) return `dans ${n} jours`;
  if (n < 60) return `dans ${Math.round(n / 7)} semaines`;
  return `dans ${Math.round(n / 30.4)} mois`;
}
function isoDeTs(ts) { return isoLocal(new Date(ts * 1000)); }
function fmtHeure(ts) {
  const d = new Date(ts * 1000);
  return `${d.getHours()} h ${deux(d.getMinutes())}`;
}
/* Durée en minutes → « 1 h 49 », « 45 min ». */
function fmtDuree(min) {
  min = Math.round(min || 0);
  if (!min) return "";
  const h = Math.floor(min / 60), m = min % 60;
  return h ? (m ? `${h} h ${deux(m)}` : `${h} h`) : `${m} min`;
}
const nb = (n) => Number(n || 0).toLocaleString("fr-FR");
/* « 1 épisode », « 4 épisodes » (0 et 1 au singulier, comme en français). */
function pluriel(n, mot, motPluriel = mot + "s") {
  return `${nb(n)} ${Math.abs(n) > 1 ? motPluriel : mot}`;
}
const codeEp = (s, e) => `S${s} · É${e}`;

/* -------------------------------------------- messages avec « Annuler » (Q3) */
/* toast(texte, {annuler: jeton, apres}) : « Annuler » reste 5 s ; il rejoue
   le jeton côté serveur puis appelle apres() pour remettre l'écran à jour. */
function toast(message, { annuler = null, erreur = false, apres = null, duree = 0 } = {}) {
  const zone = $("#toasts");
  if (!zone) return null;
  const el = document.createElement("div");
  el.className = "toast" + (erreur ? " err" : "");
  el.setAttribute("role", erreur ? "alert" : "status");
  el.innerHTML = `${ic(erreur ? "alert" : "check")}<span class="tx"></span>`;
  el.querySelector(".tx").textContent = message;
  let fini = false;
  const fermer = () => {
    if (fini) return;
    fini = true;
    el.classList.add("sort");
    setTimeout(() => el.remove(), 220);
  };
  if (annuler) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "a";
    b.textContent = "Annuler";
    b.addEventListener("click", async () => {
      b.disabled = true;
      try {
        await api("/api/undo", { method: "POST", body: { jeton: annuler } });
        fermer();
        toast("Annulé");
        if (apres) apres();
      } catch (e) { fermer(); toastErr(e); }
    });
    el.append(b);
    el.insertAdjacentHTML("beforeend", `<span class="tm"><i></i></span>`);
  }
  while (zone.children.length >= 3) zone.firstElementChild.remove();
  zone.append(el);
  setTimeout(fermer, duree || (annuler ? 5000 : erreur ? 4500 : 2600));
  return { fermer };
}
const toastErr = (e) => toast(e && e.message ? e.message : String(e), { erreur: true });

/* Un bouton à la fois (Q4) : grisé + roue qui tourne jusqu'à la réponse ; un
   double appui ne renvoie plus la requête (épisode compté deux fois…). */
async function occupe(btn, fn) {
  if (btn && btn.dataset.occupe) return undefined;
  if (btn) {
    btn.dataset.occupe = "1";
    btn.classList.add("occupe");
    btn.setAttribute("aria-busy", "true");
  }
  try { return await fn(); }
  finally {
    if (btn) {
      delete btn.dataset.occupe;
      btn.classList.remove("occupe");
      btn.removeAttribute("aria-busy");
    }
  }
}

/* ------------------------------- couches et bouton retour du téléphone (F7) */
/* Chaque fiche, feuille, menu ou recherche ouverte ajoute une entrée à
   l'historique : le bouton retour du téléphone la referme au lieu de quitter
   l'app. Fermer depuis l'écran (croix, voile, Échap) recule d'autant. */
const Couches = {
  pile: [],
  _attente: [],     // promesses de fermeture en cours (history.go asynchrone)
  _differes: [],    // ouvertures/fermetures demandées pendant un retour
  apresPop: null,

  init() {
    const st = history.state || {};
    history.replaceState({ ...st, n: 0 }, "", location.href);
    addEventListener("popstate", (e) => this._pop(e));
  },
  get ouvertes() { return this.pile.length; },
  _niveau() { return (history.state && history.state.n) || 0; },

  ouvrir(fermer, { url = null } = {}) {
    const c = { n: null, fermer, url, annule: false };
    this.pile.push(c);
    const pousser = () => {
      if (c.annule) return;
      c.n = this._niveau() + 1;
      history.pushState({ n: c.n }, "", c.url || location.href);
    };
    if (this._attente.length) this._differes.push(pousser); else pousser();
    this._maj();
    return c;
  },

  /* Ferme une couche (et celles au-dessus) ; se résout une fois fermée. */
  fermer(c = this.pile[this.pile.length - 1]) {
    if (!c || !this.pile.includes(c)) return Promise.resolve();
    if (this._attente.length) {
      return new Promise((res) => this._differes.push(() => this.fermer(c).then(res)));
    }
    if (c.n === null) {
      c.annule = true;
      this._retirer(this.pile.indexOf(c));
      return Promise.resolve();
    }
    const pas = this._niveau() - c.n + 1;
    if (pas <= 0) {                     // historique incohérent : on ferme sur place
      this._retirer(this.pile.indexOf(c));
      return Promise.resolve();
    }
    return new Promise((res) => { this._attente.push(res); history.go(-pas); });
  },
  fermerTout() { return this.pile.length ? this.fermer(this.pile[0]) : Promise.resolve(); },

  _retirer(i) {
    const parties = this.pile.splice(i);
    for (let k = parties.length - 1; k >= 0; k--) parties[k].fermer();
    this._maj();
  },
  _pop(e) {
    const n = (e.state && e.state.n) || 0;
    for (let i = this.pile.length - 1; i >= 0; i--) {
      const c = this.pile[i];
      if (c.n !== null && c.n > n) { this.pile.splice(i, 1); c.fermer(); }
    }
    this._maj();
    this._attente.splice(0).forEach((r) => r());
    this._differes.splice(0).forEach((f) => f());
    if (this.apresPop) this.apresPop(e);
  },
  _maj() {
    const ouvert = this.pile.length > 0;
    document.body.classList.toggle("overlay-ouvert", ouvert);
    document.body.classList.toggle("verrou", ouvert);
  },
};

/* ------------------------------------------------ feuilles du bas, fenêtres */
/* Sur téléphone, une feuille qui monte du bas ; sur grand écran, une fenêtre
   centrée. Renvoie {el, corps, fermer()}. */
function feuille({ titre = "", html = "", large = false, classe = "", surFermer = null } = {}) {
  const voile = document.createElement("div");
  voile.className = "voile";
  const el = document.createElement("div");
  el.className = "feuille" + (large ? " large" : "") + (classe ? " " + classe : "");
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-modal", "true");
  el.tabIndex = -1;
  el.innerHTML = `<div class="grab" aria-hidden="true"></div>${titre ? `<div class="feuille-t"><span class="tt">${titre}</span><span class="esp"></span>
      <button type="button" class="ib" data-fermer aria-label="Fermer">${ic("x")}</button></div>` : ""}
    <div class="feuille-c">${html}</div>`;
  if (titre) el.setAttribute("aria-label", el.querySelector(".tt").textContent);
  const avant = document.activeElement;
  document.body.append(voile, el);
  let ferme = false;
  const retirer = () => {
    if (ferme) return;
    ferme = true;
    voile.classList.add("sort");
    el.classList.add("sort");
    setTimeout(() => { voile.remove(); el.remove(); }, 230);
    if (avant && avant.focus && document.contains(avant)) avant.focus({ preventScroll: true });
    if (surFermer) surFermer();
  };
  const couche = Couches.ouvrir(retirer);
  const f = {
    el, corps: el.querySelector(".feuille-c"),
    fermer: () => (ferme ? Promise.resolve() : Couches.fermer(couche)),
    get ferme() { return ferme; },
  };
  voile.addEventListener("click", () => f.fermer());
  el.addEventListener("click", (e) => { if (e.target.closest("[data-fermer]")) f.fermer(); });
  glisserPourFermer(el, () => f.fermer());
  setTimeout(() => {
    const cible = el.querySelector("[autofocus]") || (ecranLarge() ? el.querySelector("input:not([type=checkbox]), textarea") : null);
    (cible || el).focus({ preventScroll: true });
  }, 60);
  return f;
}

/* Tirer la feuille vers le bas (par sa poignée ou son titre) la referme. */
function glisserPourFermer(el, fermer) {
  let y0 = null, dy = 0;
  el.addEventListener("pointerdown", (e) => {
    if (ecranLarge() || !e.target.closest(".grab, .feuille-t")) return;
    if (e.target.closest("button")) return;
    y0 = e.clientY; dy = 0;
    el.style.transition = "none";
  });
  el.addEventListener("pointermove", (e) => {
    if (y0 === null) return;
    dy = Math.max(0, e.clientY - y0);
    el.style.transform = `translateY(${dy}px)`;
  });
  const fin = () => {
    if (y0 === null) return;
    y0 = null;
    el.style.transition = "";
    el.style.transform = "";
    if (dy > 90) fermer();
  };
  el.addEventListener("pointerup", fin);
  el.addEventListener("pointercancel", fin);
}

/* Confirmation intégrée (V6) : jamais de confirm() du navigateur, qui grise
   l'écran des apps installées sur iPhone. Se résout une fois la feuille fermée. */
function confirmer(message, { ok = "Confirmer", danger = false, titre = "", detail = "" } = {}) {
  return new Promise((resolve) => {
    let rep = false;
    const f = feuille({
      titre: titre ? esc(titre) : "",
      html: `<div class="conf"><p class="msg"></p>${detail ? `<p class="muted petit det"></p>` : ""}
        <div class="bts"><button type="button" class="btn" data-non>Annuler</button>
        <button type="button" class="btn ${danger ? "dn plein" : "pri"}" data-oui></button></div></div>`,
      surFermer: () => resolve(rep),
    });
    f.el.querySelector(".msg").textContent = message;
    if (detail) f.el.querySelector(".det").textContent = detail;
    f.el.querySelector("[data-oui]").textContent = ok;
    f.el.addEventListener("click", (e) => {
      if (e.target.closest("[data-oui]")) { rep = true; f.fermer(); }
      else if (e.target.closest("[data-non]")) f.fermer();
    });
  });
}

/* Remplace prompt() (V6) : un champ dans une feuille. Se résout au texte, ou null. */
function demander(titre, { label = "", valeur = "", placeholder = "", ok = "Valider" } = {}) {
  return new Promise((resolve) => {
    let rep = null;
    const f = feuille({
      titre: esc(titre),
      html: `<form class="form"><label class="lbl" for="dm-champ"></label>
        <input class="input" id="dm-champ" autocomplete="off" autofocus>
        <div class="conf"><div class="bts"><button type="button" class="btn" data-non>Annuler</button>
        <button type="submit" class="btn pri" data-oui></button></div></div></form>`,
      surFermer: () => resolve(rep),
    });
    const champ = f.el.querySelector("#dm-champ");
    f.el.querySelector(".lbl").textContent = label;
    if (!label) f.el.querySelector(".lbl").remove();
    champ.value = valeur;
    champ.placeholder = placeholder;
    f.el.querySelector("[data-oui]").textContent = ok;
    f.el.querySelector("form").addEventListener("submit", (e) => {
      e.preventDefault();
      const v = champ.value.trim();
      if (!v) { champ.focus(); return; }
      rep = v;
      f.fermer();
    });
    f.el.querySelector("[data-non]").addEventListener("click", () => f.fermer());
  });
}

/* ----------------------------------------------------------- bulles « ? » */
/* Bulle d'explication (T4). Texte dans BULLES[data-q] = {t, d, pre}, ou dans
   les attributs data-t / data-d du bouton. */
const BULLES = {};
let bulleOuverte = null;
function fermerBulle() {
  if (!bulleOuverte) return;
  bulleOuverte.q.setAttribute("aria-expanded", "false");
  bulleOuverte.el.remove();
  bulleOuverte = null;
}
function ouvrirBulle(q) {
  const deja = bulleOuverte && bulleOuverte.q === q;
  fermerBulle();
  if (deja) return;
  const info = BULLES[q.dataset.q] || { t: q.dataset.t || "", d: q.dataset.d || "" };
  const el = document.createElement("div");
  el.className = "bulle";
  el.setAttribute("role", "tooltip");
  el.innerHTML = (info.t ? `<b>${esc(info.t)}</b>` : "") + (info.d ? `<div>${esc(info.d)}</div>` : "")
    + (info.pre ? `<div class="k">${esc(info.k || "Le calcul")}</div><pre>${esc(info.pre)}</pre>` : "");
  document.body.append(el);
  const r = q.getBoundingClientRect();
  const w = el.offsetWidth, h = el.offsetHeight;
  const x = Math.min(Math.max(12, r.left + r.width / 2 - w / 2), innerWidth - w - 12);
  let y = r.bottom + 8;
  if (y + h > innerHeight - 12) y = Math.max(12, r.top - h - 8);
  el.style.left = `${x}px`;
  el.style.top = `${y}px`;
  q.setAttribute("aria-expanded", "true");
  bulleOuverte = { el, q };
}
document.addEventListener("click", (e) => {
  const q = e.target.closest(".q");
  if (q) {
    e.preventDefault();
    e.stopPropagation();
    ouvrirBulle(q);
    return;
  }
  if (bulleOuverte && !e.target.closest(".bulle")) fermerBulle();
}, true);
addEventListener("scroll", fermerBulle, { passive: true, capture: true });
addEventListener("resize", fermerBulle);

BULLES.accent = { t: "Couleur d'accent", d: "La couleur des boutons principaux, des onglets actifs et des titres mis en avant. Elle s'adapte au thème clair pour rester lisible." };
BULLES.theme = { t: "Thème", d: "« Automatique » suit le réglage de ton appareil : clair en journée, sombre le soir. Tu peux aussi forcer l'un ou l'autre." };

/* ---------------------------------------------------- préférences d'affichage */
const PREFS = Object.assign({ accent: "lavande", theme: "auto", affiche: "m", legendes: true,
  vue_biblio: "grille", reprendre: "carte", rangees: [] }, CT.prefs || {});
const _metasTheme = $$('meta[name="theme-color"]').map((m) => m.cloneNode());

function appliquerPrefs() {
  const h = document.documentElement;
  h.dataset.accent = PREFS.accent;
  h.dataset.affiche = PREFS.affiche;
  h.dataset.legendes = PREFS.legendes ? "1" : "0";
  if (PREFS.theme === "sombre") h.dataset.theme = "dark";
  else if (PREFS.theme === "clair") h.dataset.theme = "light";
  else delete h.dataset.theme;
  // Couleur de la barre du téléphone : le fond du thème choisi.
  $$('meta[name="theme-color"]').forEach((m) => m.remove());
  if (PREFS.theme === "auto") {
    _metasTheme.forEach((m) => document.head.append(m.cloneNode()));
  } else {
    const m = document.createElement("meta");
    m.name = "theme-color";
    m.content = getComputedStyle(h).getPropertyValue("--bg").trim();
    document.head.append(m);
  }
}

async function enregistrerPrefs(patch, { message = "Enregistré" } = {}) {
  const avant = { ...PREFS };
  Object.assign(PREFS, patch);
  appliquerPrefs();
  try {
    const r = await api("/api/prefs", { method: "POST", body: patch });
    Object.assign(PREFS, r.prefs || {});
    appliquerPrefs();
    purgeShell();  // la page en cache porte l'ancien accent : on l'oublie
    if (message) toast(message);
    signaler("prefs", patch);
  } catch (e) {
    Object.assign(PREFS, avant);
    appliquerPrefs();
    toastErr(e);
    throw e;
  }
}

/* Le service worker garde la page « / » pour démarrer vite : elle est retirée
   du cache quand le compte ou les préférences changent. */
async function purgeShell() {
  if (!window.caches) return;
  try {
    await Promise.all((await caches.keys()).map(async (k) => (await caches.open(k)).delete("/")));
  } catch (_) { /* Cache API indisponible */ }
}

/* -------------------------------------------------- petit cache local */
/* Affiche tout de suite le dernier contenu connu, puis rafraîchit. Tolérant
   aux erreurs (navigation privée, quota) : n'empêche jamais l'affichage. */
function cacheGet(key) {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : null; }
  catch (_) { return null; }
}
function cacheSet(key, value) {
  try {
    const s = JSON.stringify(value);
    if (s.length < 600000) localStorage.setItem(key, s);  // garde-fou de quota
  } catch (_) { /* quota plein / mode privé */ }
}

/* ------------------------------------------------------- mes plateformes */
/* Variantes d'une même plateforme (miroir de canon_platform côté serveur) :
   « Netflix basic with Ads » → « Netflix ». */
const _PLAT_SUFFIXE = /\s*(?:-\s*)?(?:(?:basic|standard|premium|essential)?\s*with ads|avec (?:pub|pubs|publicit[ée]s?)|amazon channel|apple tv channel|with showtime|kids)\s*$/i;
function canonPlatform(nom) {
  let s = String(nom || "").trim(), prev = null;
  while (prev !== s) { prev = s; s = s.replace(_PLAT_SUFFIXE, "").trim(); }
  return s || String(nom || "").trim();
}
let MES_PLATEFORMES = new Set();
const ownsPlatform = (nom) => MES_PLATEFORMES.has(canonPlatform(nom).toLowerCase());
async function chargerMesPlateformes() {
  try {
    const s = await api("/api/settings");
    MES_PLATEFORMES = new Set((s.mes_plateformes || []).map((x) => canonPlatform(x).toLowerCase()));
    return s;
  } catch (_) { return null; }
}
/* Type indicatif d'une plateforme (TMDB ne le donne pas globalement). */
function platformType(nom) {
  const n = String(nom || "").toLowerCase();
  const achat = ["vod", "google play", "play store", "microsoft", "rakuten", "youtube", "amazon video"];
  if (achat.some((k) => n.includes(k))) return "buy";
  const abo = ["netflix", "disney", "prime video", "amazon prime", "paramount", "max", "hbo",
    "mycanal", "canal+", "ciné+", "cine+", "crunchyroll", "adn", "animation digital", "ocs",
    "universal+", "pass warner", "mubi", "shadowz", "filmo", "insomnia", "molotov", "tf1+",
    "m6+", "6play", "france tv", "arte", "britbox", "skyshowtime", "starz", "peacock", "hulu",
    "apple tv+", "apple tv plus", "universcine"];
  if (abo.some((k) => n.includes(k)) || n.includes("+") || /\bplus\b/.test(n)) return "sub";
  if (["apple tv", "orange", "bbox", "sfr", "fnac"].some((k) => n.includes(k))) return "buy";
  return "";
}

/* ------------------------------------------------------------- divers */
async function copier(texte, btn) {
  try {
    await navigator.clipboard.writeText(texte);
  } catch (_) {
    const ta = document.createElement("textarea");
    ta.value = texte;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;opacity:0;top:0;left:0";
    document.body.append(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (__) { /* rien de plus à faire */ }
    ta.remove();
  }
  if (btn) {
    const avant = btn.innerHTML;
    btn.innerHTML = `${ic("check", "s16")}Copié`;
    setTimeout(() => { btn.innerHTML = avant; }, 1800);
  }
}

/* Rejoue l'apparition en cascade des enfants d'un conteneur (T7). */
function animerEntree(el) {
  if (!el) return;
  el.classList.remove("anim-in");
  void el.offsetWidth;
  el.classList.add("anim-in");
}

/* Appui long (B4, S2) : déclenche surAppui(el) après ~0,5 s sans bouger, et
   avale le clic qui suit pour ne pas ouvrir la fiche en plus. */
let dernierPointeur = "mouse";
addEventListener("pointerdown", (e) => { dernierPointeur = e.pointerType || "mouse"; }, true);
function appuiLong(racine, selecteur, surAppui, { delai = 480 } = {}) {
  let t = null, x0 = 0, y0 = 0, declenche = false;
  const annuler = () => { clearTimeout(t); t = null; };
  racine.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    const el = e.target.closest(selecteur);
    if (!el || !racine.contains(el) || e.target.closest(".po-more, .po-cloche, .ck, .plus, button.ib")) return;
    x0 = e.clientX; y0 = e.clientY; declenche = false;
    annuler();
    t = setTimeout(() => { t = null; declenche = true; vibrer(12); surAppui(el, e); }, delai);
  });
  racine.addEventListener("pointermove", (e) => {
    if (t && (Math.abs(e.clientX - x0) > 9 || Math.abs(e.clientY - y0) > 9)) annuler();
  }, { passive: true });
  racine.addEventListener("pointerup", annuler);
  racine.addEventListener("pointercancel", annuler);
  racine.addEventListener("scroll", annuler, { passive: true, capture: true });
  racine.addEventListener("click", (e) => {
    if (declenche) { e.preventDefault(); e.stopPropagation(); declenche = false; }
  }, true);
  racine.addEventListener("contextmenu", (e) => {
    if (dernierPointeur === "touch" && e.target.closest(selecteur)) e.preventDefault();
  });
}

/* Échap ferme la bulle, sinon la couche du dessus (fiche, feuille, menu…). */
addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (bulleOuverte) { fermerBulle(); e.preventDefault(); return; }
  if (Couches.ouvertes && !e.defaultPrevented) { e.preventDefault(); Couches.fermer(); }
});
