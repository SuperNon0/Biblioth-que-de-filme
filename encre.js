/* =========================================================================
   encre.js — les comportements du design « encre » (sans dépendance).

   Reprise de cinéthèque (v29), rendue indépendante du site :
   - Apparence : couleur d'accent + thème auto / clair / sombre, enregistrés
     sur l'appareil (et sur le compte si le site fournit Encre.apparence.sauver).
   - Navigation : onglet actif de la barre flottante et du menu de gauche,
     feuille « Plus », ombre de la barre du haut quand on défile.
   - Couches : le bouton retour du téléphone referme d'abord la feuille,
     le menu ou la fenêtre ouverte, au lieu de quitter le site.
   - Feuilles du bas (téléphone) / fenêtres centrées (ordinateur), menus,
     confirmations et questions intégrées : jamais d'alert(), confirm(),
     prompt() du navigateur.
   - Recherche rapide (Ctrl K, ⌘ K ou « / ») sur les raccourcis du site.
   - Messages avec « Annuler » pendant 5 s, bouton « occupé » (pas de
     double envoi), bulles « ? », copier, apparition en cascade, appui long.

   Tout passe par l'objet global Encre ; rien d'autre n'est ajouté à window.
   À charger avec <script defer src="encre.js"></script>. Mode d'emploi :
   LISEZMOI.md, section « Le comportement ».
   ========================================================================= */
(() => {
  "use strict";

  const Encre = (window.Encre = window.Encre || {});
  const h = document.documentElement;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const ecranOrdi = () => matchMedia("(min-width: 1000px)").matches;
  const ecranLarge = () => matchMedia("(min-width: 760px)").matches;
  const pointeurFin = () => matchMedia("(hover: hover) and (pointer: fine)").matches;
  const appareilClair = () => matchMedia("(prefers-color-scheme: light)").matches;

  /* Icône du jeu dessiné (icones.svg). Encre.sprite = "" si le fichier est
     collé dans la page, ou son adresse (data-encre-sprite sur <html>). */
  const ic = (nom, cls = "") =>
    `<svg class="i${cls ? " " + cls : ""}" aria-hidden="true"><use href="${Encre.sprite || ""}#i-${nom}"/></svg>`;

  const esc = (str) => String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

  function vibrer(ms = 8) {
    try { if (navigator.vibrate) navigator.vibrate(ms); } catch (_) { /* refusé */ }
  }

  /* ================================================================ apparence */
  const ACCENTS = ["or", "ambre", "corail", "menthe", "lavande"];
  const THEMES = ["auto", "clair", "sombre"];
  const CLE = "encre-apparence";
  const FOND = { sombre: "#0b0f17", clair: "#f5f3ee" };   // = --bg des deux thèmes

  function lireLocal() {
    try { return JSON.parse(localStorage.getItem(CLE) || "{}") || {}; } catch (_) { return {}; }
  }
  function ecrireLocal(p) {
    try { localStorage.setItem(CLE, JSON.stringify(p)); } catch (_) { /* privé, quota */ }
  }

  const Apparence = {
    ACCENTS, THEMES,
    /* Accent par défaut du site : data-accent-defaut sur <html> (lavande sinon). */
    defaut: { accent: ACCENTS.includes(h.dataset.accentDefaut) ? h.dataset.accentDefaut : "lavande", theme: "auto" },
    prefs: null,
    /* Optionnel : async (prefs, changement) => { … } pour enregistrer sur le
       compte (côté serveur). Une erreur annule le changement et l'affiche. */
    sauver: null,

    /* Ce que la page a posé sur <html> (le serveur, ou le petit script de
       <head> qui relit l'appareil), sinon ce que l'appareil a gardé. */
    lire() {
      const local = lireLocal();
      const serveur = "encrePrefs" in h.dataset;   // data-encre-prefs : le serveur décide
      const accent = ACCENTS.includes(h.dataset.accent) ? h.dataset.accent
        : (!serveur && ACCENTS.includes(local.accent) ? local.accent : this.defaut.accent);
      let theme = "encreAuto" in h.dataset ? "auto"
        : h.dataset.theme === "dark" ? "sombre" : h.dataset.theme === "light" ? "clair" : null;
      if (!theme) theme = !serveur && THEMES.includes(local.theme) ? local.theme : this.defaut.theme;
      return { accent, theme };
    },

    appliquer(p = this.prefs) {
      h.dataset.accent = p.accent;
      /* Automatique : data-theme suit quand même l'appareil (avec data-encre-auto),
         pour que des jetons sans requête média (tokens.css compilé) suivent aussi. */
      if (p.theme === "auto") {
        h.dataset.theme = appareilClair() ? "light" : "dark";
        h.dataset.encreAuto = "";
      } else {
        h.dataset.theme = p.theme === "clair" ? "light" : "dark";
        delete h.dataset.encreAuto;
      }
      // Couleur de la barre du téléphone : le fond du thème affiché.
      $$('meta[name="theme-color"]').forEach((m) => m.remove());
      const meta = (content, media) => {
        const m = document.createElement("meta");
        m.name = "theme-color";
        m.content = content;
        if (media) m.media = media;
        document.head.append(m);
      };
      if (p.theme === "auto") {
        meta(FOND.sombre, "(prefers-color-scheme: dark)");
        meta(FOND.clair, "(prefers-color-scheme: light)");
      } else meta(FOND[p.theme]);
      this.marquer();
    },

    /* Change l'accent et/ou le thème : Encre.apparence.choisir({accent: "or"}). */
    async choisir(changement, { message = "Enregistré" } = {}) {
      const avant = { ...this.prefs };
      this.prefs = { ...this.prefs, ...changement };
      this.appliquer();
      ecrireLocal(this.prefs);
      try {
        if (typeof this.sauver === "function") await this.sauver({ ...this.prefs }, changement);
        if (message) toast(message);
        document.dispatchEvent(new CustomEvent("encre:apparence", { detail: { ...this.prefs } }));
      } catch (e) {
        this.prefs = avant;
        this.appliquer();
        ecrireLocal(avant);
        toastErr(e);
      }
    },

    /* Allume la bonne pastille ([data-encre-accent]) et le bon segment ([data-encre-theme]). */
    marquer(racine = document) {
      if (!this.prefs) return;
      $$("[data-encre-accent] [data-v]", racine).forEach((b) => {
        const on = b.dataset.v === this.prefs.accent;
        b.classList.toggle("on", on);
        b.setAttribute("aria-checked", on ? "true" : "false");
        b.tabIndex = on ? 0 : -1;
      });
      $$("[data-encre-theme] [data-v]", racine).forEach((b) => {
        const on = b.dataset.v === this.prefs.theme;
        b.classList.toggle("on", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
    },

    brancher() {
      // Automatique : suit l'appareil s'il change pendant la visite (le soir…).
      try {
        matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
          if (this.prefs && this.prefs.theme === "auto") this.appliquer();
        });
      } catch (_) { /* très vieux navigateur : au prochain chargement */ }
      document.addEventListener("click", (e) => {
        const b = e.target.closest("[data-encre-accent] [data-v], [data-encre-theme] [data-v]");
        if (!b) return;
        const cle = b.closest("[data-encre-accent]") ? "accent" : "theme";
        if (b.dataset.v !== this.prefs[cle]) this.choisir({ [cle]: b.dataset.v });
      });
      // Flèches du clavier dans les pastilles d'accent (groupe radio).
      document.addEventListener("keydown", (e) => {
        const groupe = e.target.closest && e.target.closest("[data-encre-accent]");
        if (!groupe || !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
        e.preventDefault();
        const bts = $$("[data-v]", groupe);
        const i = bts.findIndex((b) => b.dataset.v === this.prefs.accent);
        const j = (i + (e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 1) + bts.length) % bts.length;
        bts[j].focus();
        bts[j].click();
      });
    },
  };

  /* ==================================== couches et bouton retour du téléphone */
  /* Chaque feuille, menu ou fenêtre ouverte ajoute une entrée à l'historique :
     le bouton retour du téléphone la referme au lieu de quitter le site.
     Fermer depuis l'écran (croix, voile, Échap) recule d'autant.
     data-encre-sans-retour sur <html> : pas d'historique (site qui a déjà
     son propre routeur, Next.js par exemple) ; les couches se ferment sur place. */
  const Couches = {
    pile: [],
    actif: false,
    _attente: [],
    _differes: [],
    apresPop: null,

    init() {
      if (this.actif || "encreSansRetour" in h.dataset) return;
      this.actif = true;
      const st = history.state && typeof history.state === "object" ? history.state : {};
      history.replaceState({ ...st, n: 0 }, "", location.href);
      addEventListener("popstate", (e) => this._pop(e));
    },
    get ouvertes() { return this.pile.length; },
    _niveau() { return (history.state && history.state.n) || 0; },

    /* vue : sous-page qui ne bloque pas le défilement et ne cache pas la barre. */
    ouvrir(fermer, { url = null, el = null, vue = false } = {}) {
      const c = { n: null, fermer, url, el, vue, annule: false };
      this.pile.push(c);
      if (this.actif) {
        const pousser = () => {
          if (c.annule) return;
          c.n = this._niveau() + 1;
          history.pushState({ n: c.n }, "", c.url || location.href);
        };
        if (this._attente.length) this._differes.push(pousser); else pousser();
      }
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
      if (pas <= 0) {
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
      const ouvert = this.pile.some((c) => !c.vue);
      document.body.classList.toggle("overlay-ouvert", ouvert);
      document.body.classList.toggle("verrou", ouvert);
    },
  };

  /* ========================================== feuilles du bas, fenêtres */
  /* Sur téléphone, une feuille qui monte du bas ; à partir de 760 px, une
     fenêtre centrée. titre est du HTML : échappe-le (Encre.esc) s'il vient
     d'une saisie. Renvoie {el, corps, fermer()}. */
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
    const couche = Couches.ouvrir(retirer, { el });
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

  /* Confirmation intégrée : jamais de confirm() du navigateur (il grise
     l'écran des apps installées sur iPhone). Se résout à true / false. */
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

  /* Remplace prompt() : un champ dans une feuille. Se résout au texte, ou null. */
  function demander(titre, { label = "", valeur = "", placeholder = "", ok = "Valider" } = {}) {
    return new Promise((resolve) => {
      let rep = null;
      const f = feuille({
        titre: esc(titre),
        html: `<form class="form"><label class="lbl" for="encre-champ"></label>
          <input class="input" id="encre-champ" autocomplete="off" autofocus>
          <div class="conf"><div class="bts"><button type="button" class="btn" data-non>Annuler</button>
          <button type="submit" class="btn pri" data-oui></button></div></div></form>`,
        surFermer: () => resolve(rep),
      });
      const champ = f.el.querySelector("#encre-champ");
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

  /* Menu d'actions : menu flottant à côté du bouton sur ordinateur (souris),
     feuille du bas sur téléphone. elements = [{icone, texte, touche, danger,
     action}] ; null = séparateur. */
  let popOuverte = null;
  function menu(ancre, elements, { titre = "" } = {}) {
    if (popOuverte) popOuverte.fermer();
    const items = elements.filter(Boolean);
    const lancer = async (i, fermer) => {
      await fermer();
      const it = items[i];
      if (it && typeof it.action === "function") it.action();
    };
    if (!(ecranLarge() && pointeurFin())) {
      const f = feuille({
        titre: titre ? esc(titre) : "",
        html: elements.map((it) => it === null ? "" : `<button type="button" class="q-ext${it.danger ? " dn" : ""}" data-i="${items.indexOf(it)}">${ic(it.icone || "dot")}<span>${esc(it.texte)}</span></button>`).join(""),
      });
      f.el.addEventListener("click", (e) => {
        const b = e.target.closest("[data-i]");
        if (b) lancer(Number(b.dataset.i), f.fermer);
      });
      return f;
    }
    const el = document.createElement("div");
    el.className = "pop";
    el.setAttribute("role", "menu");
    if (titre) el.setAttribute("aria-label", titre);
    el.innerHTML = (titre ? `<div class="pop-t">${esc(titre)}</div>` : "") + elements.map((it) => it === null ? '<div class="msep"></div>'
      : `<button type="button" class="mi${it.danger ? " dn" : ""}" role="menuitem" data-i="${items.indexOf(it)}">${ic(it.icone || "dot")}<span>${esc(it.texte)}</span>${it.touche ? `<span class="k">${esc(it.touche)}</span>` : ""}</button>`).join("");
    document.body.append(el);
    const r = ancre.getBoundingClientRect();
    const x = r.right - el.offsetWidth, y = r.bottom + 6;
    el.style.left = `${Math.max(8, Math.min(x, innerWidth - el.offsetWidth - 8))}px`;
    el.style.top = `${Math.max(8, y + el.offsetHeight > innerHeight - 8 ? r.top - el.offsetHeight - 6 : y)}px`;
    const avant = document.activeElement;
    let ferme = false;
    const dehors = (e) => { if (!el.contains(e.target)) p.fermer(); };
    const retirer = () => {
      if (ferme) return;
      ferme = true;
      el.remove();
      document.removeEventListener("pointerdown", dehors, true);
      if (popOuverte === p) popOuverte = null;
      if (avant && avant.focus && document.contains(avant)) avant.focus({ preventScroll: true });
    };
    const couche = Couches.ouvrir(retirer, { el });
    const p = { el, fermer: () => (ferme ? Promise.resolve() : Couches.fermer(couche)) };
    popOuverte = p;
    setTimeout(() => document.addEventListener("pointerdown", dehors, true), 0);
    el.addEventListener("click", (e) => {
      const b = e.target.closest("[data-i]");
      if (b) lancer(Number(b.dataset.i), p.fermer);
    });
    el.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      e.preventDefault();
      const bts = $$(".mi", el);
      const i = bts.indexOf(document.activeElement);
      bts[(i + (e.key === "ArrowDown" ? 1 : -1) + bts.length) % bts.length].focus();
    });
    setTimeout(() => { const b = el.querySelector(".mi"); if (b) b.focus({ preventScroll: true }); }, 0);
    return p;
  }

  /* ========================================= messages avec « Annuler » */
  /* toast(texte, {annuler: async () => {…}, apres, erreur, duree}) :
     « Annuler » reste 5 s avec une petite barre qui se vide ; il appelle
     annuler(), puis apres() pour remettre l'écran à jour. */
  function zoneToasts() {
    let z = $("#toasts");
    if (!z) {
      z = document.createElement("div");
      z.className = "toasts";
      z.id = "toasts";
      z.setAttribute("aria-live", "polite");
      document.body.append(z);
    }
    return z;
  }
  function toast(message, { annuler = null, erreur = false, apres = null, duree = 0 } = {}) {
    const zone = zoneToasts();
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
    if (typeof annuler === "function") {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "a";
      b.textContent = "Annuler";
      b.addEventListener("click", async () => {
        b.disabled = true;
        try {
          await annuler();
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

  /* Un bouton à la fois : grisé + roue qui tourne jusqu'à la réponse ; un
     double appui ne renvoie pas la requête. occupe(bouton, async () => …). */
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

  /* ========================================================= bulles « ? » */
  /* <button type="button" class="q" data-t="Titre" data-d="Explication">?</button>
     ou data-q="cle" avec Encre.bulles.cle = {t, d, pre, k}. */
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
    const w = el.offsetWidth, ht = el.offsetHeight;
    const x = Math.min(Math.max(12, r.left + r.width / 2 - w / 2), innerWidth - w - 12);
    let y = r.bottom + 8;
    if (y + ht > innerHeight - 12) y = Math.max(12, r.top - ht - 8);
    el.style.left = `${x}px`;
    el.style.top = `${y}px`;
    q.setAttribute("aria-expanded", "true");
    bulleOuverte = { el, q };
  }

  /* ================================================================ divers */
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

  /* Rejoue l'apparition en cascade des enfants d'un conteneur. */
  function animerEntree(el) {
    if (!el) return;
    el.classList.remove("anim-in");
    void el.offsetWidth;
    el.classList.add("anim-in");
  }

  /* Appui long (doigt ou stylet) : surAppui(el) après ~0,5 s sans bouger ;
     le clic qui suit est avalé. À la souris : clic droit ou bouton « ⋯ ». */
  let dernierPointeur = "mouse";
  addEventListener("pointerdown", (e) => { dernierPointeur = e.pointerType || "mouse"; }, true);
  function appuiLong(racine, selecteur, surAppui, { delai = 480 } = {}) {
    let t = null, x0 = 0, y0 = 0, declenche = false;
    const annuler = () => { clearTimeout(t); t = null; };
    racine.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || e.pointerType === "mouse") return;
      const el = e.target.closest(selecteur);
      if (!el || !racine.contains(el) || e.target.closest("button, a, input, .ck")) return;
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

  /* ================================================ recherche rapide (Ctrl K) */
  /* Ctrl K (⌘ K), « / » ou un bouton [data-encre-recherche] l'ouvrent.
     Encre.recherche.raccourcis = [{ titre, sous, icone, mots, href | action }] :
       pages et actions du site, filtrées pendant la frappe.
     Encre.recherche.chercher = async (texte, { signal }) =>
       [{ groupe, titre, sous, icone, href | action }] : résultats du site (facultatif). */
  const sansAccents = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const enSaisie = (el) => !!el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));

  const Recherche = {
    raccourcis: [],
    chercher: null,
    placeholder: "Une page, un réglage…",
    ouverte: null,
    get active() { return this.raccourcis.length > 0 || typeof this.chercher === "function"; },

    ouvrir(texte = "") {
      if (this.ouverte) { this.ouverte.champ.focus(); return this.ouverte; }
      const voile = document.createElement("div");
      voile.className = "voile flou";
      const el = document.createElement("div");
      el.className = "palette";
      el.setAttribute("role", "dialog");
      el.setAttribute("aria-modal", "true");
      el.setAttribute("aria-label", "Rechercher");
      el.innerHTML = `<label class="champ">${ic("search", "s18")}
          <input type="search" autocomplete="off" enterkeyhint="search" aria-label="Rechercher"
            aria-controls="encre-res" aria-autocomplete="list">
          <button type="button" class="kbd" data-fermer>${pointeurFin() ? "Échap" : "Annuler"}</button></label>
        <div class="res-p" id="encre-res" role="listbox"></div>
        <div class="pal-pied"><span><span class="kbd">↑</span> <span class="kbd">↓</span> choisir</span>
          <span><span class="kbd">Entrée</span> ouvrir</span><span><span class="kbd">Échap</span> fermer</span></div>`;
      document.body.append(voile, el);
      const champ = el.querySelector("input");
      const res = el.querySelector(".res-p");
      champ.placeholder = this.placeholder;
      const avant = document.activeElement;
      let items = [], sel = 0, seq = 0, ctrl = null, minuteur = null, ferme = false;
      const retirer = () => {
        if (ferme) return;
        ferme = true;
        if (ctrl) ctrl.abort();
        clearTimeout(minuteur);
        voile.remove();
        el.remove();
        this.ouverte = null;
        if (avant && avant.focus && document.contains(avant)) avant.focus({ preventScroll: true });
      };
      const couche = Couches.ouvrir(retirer, { el });
      const fermer = () => (ferme ? Promise.resolve() : Couches.fermer(couche));
      voile.addEventListener("click", fermer);
      el.querySelector("[data-fermer]").addEventListener("click", fermer);

      const rendre = (groupes) => {
        items = [];
        let html = "";
        for (const g of groupes) {
          if (!g.items.length) continue;
          html += `<div class="pal-g">${ic(g.icone || "dot", "s16")}${esc(g.titre)}</div>`;
          for (const it of g.items) {
            const i = items.push(it) - 1;
            html += `<button type="button" class="pal-it${i === sel ? " on" : ""}" role="option" data-i="${i}">
              <span class="ico">${ic(it.icone || "arrow", "s18")}</span>
              <span class="tx"><b>${esc(it.titre)}</b>${it.sous ? `<span>${esc(it.sous)}</span>` : ""}</span></button>`;
          }
        }
        if (sel >= items.length) sel = 0;
        const q = champ.value.trim();
        res.innerHTML = html || (q ? `<p class="muted petit" style="padding: 12px 10px">Rien trouvé pour « ${esc(q)} ».</p>` : "");
      };
      const majSel = () => {
        $$(".pal-it", res).forEach((b) => b.classList.toggle("on", Number(b.dataset.i) === sel));
        const b = res.querySelector(`.pal-it[data-i="${sel}"]`);
        if (b) b.scrollIntoView({ block: "nearest" });
      };
      const chercher = async () => {
        const q = champ.value.trim();
        const nq = sansAccents(q);
        const mien = ++seq;
        if (ctrl) ctrl.abort();
        const rac = this.raccourcis.filter((r) => !nq || sansAccents(`${r.titre} ${r.sous || ""} ${r.mots || ""}`).includes(nq))
          .slice(0, nq ? 6 : 8);
        const groupes = [{ titre: "Raccourcis", icone: "zap", items: rac }];
        sel = 0;
        rendre(groupes);
        if (!q || typeof this.chercher !== "function") return;
        ctrl = new AbortController();
        try {
          const trouves = (await this.chercher(q, { signal: ctrl.signal })) || [];
          if (mien !== seq || ferme) return;
          const parGroupe = new Map();
          for (const t of trouves) {
            const nom = t.groupe || "Résultats";
            if (!parGroupe.has(nom)) parGroupe.set(nom, { titre: nom, icone: t.iconeGroupe || "search", items: [] });
            parGroupe.get(nom).items.push(t);
          }
          rendre([...parGroupe.values(), ...groupes]);
        } catch (e) {
          if (e.name !== "AbortError" && mien === seq) toastErr(e);
        }
      };
      const lancer = async (i) => {
        const it = items[i];
        if (!it) return;
        await fermer();
        if (typeof it.action === "function") it.action();
        else if (it.href && it.href.startsWith("#")) Nav.aller(it.href);
        else if (it.href) location.href = it.href;
      };
      res.addEventListener("click", (e) => {
        const b = e.target.closest(".pal-it");
        if (b) lancer(Number(b.dataset.i));
      });
      res.addEventListener("pointermove", (e) => {
        const b = e.target.closest(".pal-it");
        if (b && Number(b.dataset.i) !== sel) { sel = Number(b.dataset.i); majSel(); }
      });
      champ.addEventListener("input", () => { clearTimeout(minuteur); minuteur = setTimeout(chercher, 180); });
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
      this.ouverte = { el, champ, fermer };
      return this.ouverte;
    },
  };

  /* ============================================================ navigation */
  const Nav = {
    /* Page courante : data-page sur <body> (site à plusieurs pages), sinon
       le début de l'adresse après # (#reglages/compte → « reglages »). */
    page() {
      return document.body.dataset.page || decodeURIComponent(location.hash.slice(1).split("/")[0] || "");
    },
    /* Allume l'onglet et l'entrée du menu de gauche de la page courante.
       « Plus » s'allume pour une page qui n'a pas d'onglet à elle. */
    marquer(page = this.page()) {
      $$(".tab[data-page], .side-it[data-page]").forEach((a) => {
        const on = a.dataset.page === page;
        a.classList.toggle("on", on);
        if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
      });
      const plus = $(".tab[data-encre-plus]");
      if (plus) plus.classList.toggle("on", !!page && !$$(".tab[data-page]").some((a) => a.dataset.page === page));
    },
    /* Va vers #cible après avoir refermé feuilles et menus ouverts. */
    aller(cible) {
      return Couches.fermerTout().then(() => { location.hash = String(cible).replace(/^#/, ""); });
    },
    /* Feuille « Plus » : contenu du <template> nommé par data-encre-plus. */
    plus(btn) {
      const tpl = document.getElementById(btn.dataset.encrePlus || "encre-plus");
      if (!tpl) return null;
      return feuille({ titre: esc(btn.dataset.titre || "Plus"), html: tpl.innerHTML });
    },
  };

  /* ============================================================ démarrage */
  function demarrer() {
    if (Encre._demarre) return;
    Encre._demarre = true;
    Couches.init();
    Apparence.prefs = Apparence.lire();
    Apparence.appliquer();
    Apparence.brancher();
    Nav.marquer();
    addEventListener("hashchange", () => Nav.marquer());

    // Barre du haut : un trait apparaît dès qu'on défile.
    const top = $(".top");
    if (top) {
      const maj = () => top.classList.toggle("ombre", scrollY > 4);
      addEventListener("scroll", maj, { passive: true });
      maj();
    }

    document.addEventListener("click", (e) => {
      // Bulles « ? » (avant tout le reste).
      const q = e.target.closest(".q");
      if (q) { e.preventDefault(); ouvrirBulle(q); return; }
      if (bulleOuverte && !e.target.closest(".bulle")) fermerBulle();
      // Bouton de recherche (menu de gauche, barre du haut…).
      const r = e.target.closest("[data-encre-recherche]");
      if (r && Recherche.active) { e.preventDefault(); Recherche.ouvrir(); return; }
      // Onglet « Plus ».
      const plus = e.target.closest("[data-encre-plus]");
      if (plus) { e.preventDefault(); Nav.plus(plus); return; }
      // Un lien touché dans une feuille ouverte : on referme d'abord, pour que
      // le bouton retour ne rouvre pas la feuille (#page, ou autre page du site).
      const a = e.target.closest("a[href]");
      if (!a || !Couches.ouvertes || e.defaultPrevented || a.target || a.hasAttribute("download")
        || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      const href = a.getAttribute("href");
      if (href.startsWith("#")) {
        if (href.length > 1) { e.preventDefault(); Nav.aller(href); }
      } else if (a.origin === location.origin) {
        e.preventDefault();
        Couches.fermerTout().then(() => { location.href = a.href; });
      }
    });
    addEventListener("scroll", fermerBulle, { passive: true, capture: true });
    addEventListener("resize", fermerBulle);

    // Ctrl K (⌘ K) ouvre ou ferme la recherche ; « / » l'ouvre hors d'un champ.
    addEventListener("keydown", (e) => {
      if (!Recherche.active) return;
      if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (Recherche.ouverte) Recherche.ouverte.fermer(); else Recherche.ouvrir();
      } else if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey && !enSaisie(document.activeElement)
        && !Couches.pile.some((c) => !c.vue)) {
        e.preventDefault();
        Recherche.ouvrir();
      }
    });

    // Échap ferme la bulle, sinon la couche du dessus.
    addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (bulleOuverte) { fermerBulle(); e.preventDefault(); return; }
      if (Couches.ouvertes && !e.defaultPrevented) { e.preventDefault(); Couches.fermer(); }
    });
  }

  Object.assign(Encre, {
    version: "1.0",
    sprite: Encre.sprite ?? (h.dataset.encreSprite || ""),
    $, $$, ic, esc, vibrer, ecranOrdi, ecranLarge, pointeurFin,
    apparence: Apparence, nav: Nav, recherche: Recherche, Couches,
    feuille, confirmer, demander, menu, toast, toastErr, occupe,
    bulles: BULLES, ouvrirBulle, fermerBulle,
    copier, animerEntree, appuiLong, demarrer,
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarrer);
  else demarrer();
})();
