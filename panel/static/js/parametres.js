/* =========================================================================
   cinéthèque — Paramètres : réglages groupés avec leur détail (R1), deux
   colonnes sur ordinateur (R2), enregistrement immédiat avec « Enregistré »
   (R3), réglages avancés selon le rôle (R4, V9), recherche (R5), zone
   sensible protégée (R6) et boutons « Copier » du connecteur Claude (R8).
   Sur téléphone, un réglage s'ouvre en sous-page : le bouton retour revient
   à la liste.
   ========================================================================= */
"use strict";

BULLES.botpanel = { t: "Adresse de botpanel", d: "L'adresse de ton botpanel sur le réseau local, avec le port (ex. http://192.168.1.20:8080). cinéthèque l'appelle pour publier sur Discord." };
BULLES.region = { t: "Pays des plateformes", d: "Le code du pays en 2 lettres (FR, BE, CA…) : les plateformes de streaming et les dates de sortie suivent ce pays." };
BULLES["cf-team"] = { t: "Équipe Cloudflare", d: "Le nom de ton équipe Zero Trust : ce qui précède « .cloudflareaccess.com » dans l'adresse de connexion (ex. super-nono)." };

const Reg = { panneau: null, couche: null, reglages: null, charges: new Set(), _rangees: null };
const PANNEAUX = $$("#reg-det .reg-panneau[data-reg]").map((p) => p.dataset.reg);

function statutReg(id, texte, cls = "") {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = texte;
  el.className = "statut" + (cls ? " " + cls : "");
}
async function chargerReglages(forcer = false) {
  if (!Reg.reglages || forcer) Reg.reglages = await api("/api/settings");
  return Reg.reglages;
}
async function enregistrerReglages(patch, { message = "Enregistré" } = {}) {
  const r = await api("/api/settings", { method: "POST", body: patch });
  Reg.reglages = Object.assign(Reg.reglages || {}, r);
  if (message) toast(message);
  return r;
}

/* ------------------------------------------------- navigation interne */
function montrerPanneau(nom) {
  Reg.panneau = nom;
  $$("#reg-det .reg-panneau").forEach((p) => { p.hidden = p.dataset.reg !== nom; });
  $$("#reglages .li[data-reg]").forEach((a) => {
    const on = a.dataset.reg === nom;
    a.classList.toggle("on", on);
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  if (nom && !Reg.charges.has(nom)) { Reg.charges.add(nom); initPanneau(nom); }
  else if (nom) majPanneau(nom);
}
function fermerDetailReg() {
  Reg.couche = null;
  $("#reglages").classList.remove("detail");
  if (!ecranOrdi()) { Reg.panneau = null; $$("#reglages .li.on").forEach((a) => a.classList.remove("on")); }
}

let _resumesFaits = false;
Pages.parametres = {
  afficher(sous) {
    if (!_resumesFaits) { _resumesFaits = true; resumesReglages(); }
    const nom = PANNEAUX.includes(sous) ? sous : null;
    if (ecranOrdi()) {
      // Deux colonnes : la liste reste à gauche, le réglage s'affiche à droite.
      montrerPanneau(nom || Reg.panneau || "apparence");
      if (!nom) history.replaceState(history.state, "", `#parametres/${Reg.panneau}`);
      return;
    }
    if (!nom) {
      if (Reg.couche) Couches.fermer(Reg.couche);
      fermerDetailReg();
      return;
    }
    montrerPanneau(nom);
    $("#reglages").classList.add("detail");
    scrollTo(0, 0);
    if (!Reg.couche) Reg.couche = Nav.sousVue(nom, () => fermerDetailReg());
  },
};
matchMedia("(min-width: 1000px)").addEventListener?.("change", () => {
  if (Nav.page === "parametres") Pages.parametres.afficher(Reg.panneau);
});

/* ----------------------------------------------------- recherche (R5) */
$("#reg-q")?.addEventListener("input", (e) => {
  const q = sansAccents(e.target.value.trim());
  let total = 0;
  $$("#reglages .reg-bloc").forEach((bloc) => {
    let n = 0;
    $$(".li", bloc).forEach((li) => {
      const ok = !q || sansAccents(`${li.textContent} ${li.dataset.mots || ""}`).includes(q);
      li.hidden = !ok;
      if (ok) n++;
    });
    bloc.hidden = !n;
    total += n;
  });
  $("#reg-rien").hidden = !!total;
});

/* ---------------------------------------------- chaque panneau, à la demande */
function initPanneau(nom) {
  const init = INIT_REG[nom];
  if (init) init();
}
function majPanneau(nom) {
  const maj = MAJ_REG[nom];
  if (maj) maj();
}
const MAJ_REG = {};
const INIT_REG = {
  apparence() {
    MAJ_REG.apparence();
    $("#reg-accents")?.addEventListener("click", (e) => {
      const b = e.target.closest("[data-v]");
      if (b && b.dataset.v !== PREFS.accent) enregistrerPrefs({ accent: b.dataset.v }).then(MAJ_REG.apparence, MAJ_REG.apparence);
    });
    $("#reg-accents")?.addEventListener("keydown", (e) => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
      e.preventDefault();
      const bts = $$("#reg-accents [data-v]");
      const i = bts.findIndex((b) => b.dataset.v === PREFS.accent);
      const j = (i + (e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 1) + bts.length) % bts.length;
      bts[j].focus();
      bts[j].click();
    });
    for (const [id, cle] of [["#reg-theme", "theme"], ["#reg-affiche", "affiche"]]) {
      $(id)?.addEventListener("click", (e) => {
        const b = e.target.closest("[data-v]");
        if (b && b.dataset.v !== PREFS[cle]) enregistrerPrefs({ [cle]: b.dataset.v }).then(MAJ_REG.apparence, MAJ_REG.apparence);
      });
    }
    $("#reg-legendes")?.addEventListener("change", (e) => enregistrerPrefs({ legendes: e.target.checked }).catch(MAJ_REG.apparence));
    $("#reg-vue")?.addEventListener("change", (e) => {
      Biblio.vue = e.target.value;
      enregistrerPrefs({ vue_biblio: e.target.value }).catch(MAJ_REG.apparence);
    });
  },

  async accueil() {
    $("#reg-reprendre")?.addEventListener("change", (e) =>
      enregistrerPrefs({ reprendre: e.target.checked ? "carte" : "rangee" }).catch(MAJ_REG.accueil));
    const box = $("#reg-rangees");
    box.innerHTML = squeletteLignes(4);
    try {
      const { rangees } = await api("/api/prefs");
      Reg._rangees = Object.fromEntries(rangees.map((r) => [r.id, r.nom]));
    } catch (e) { box.innerHTML = erreurHtml(e); return; }
    MAJ_REG.accueil();
    const sauver = plusTard(() => enregistrerPrefs({ rangees: PREFS.rangees }).catch(MAJ_REG.accueil), 450);
    box.addEventListener("click", (e) => {
      const fl = e.target.closest("[data-rg-dep]");
      if (!fl) return;
      const i = Number(fl.closest(".rg").dataset.i), j = i + Number(fl.dataset.rgDep);
      const r = PREFS.rangees.slice();
      if (j < 0 || j >= r.length) return;
      [r[i], r[j]] = [r[j], r[i]];
      PREFS.rangees = r;
      MAJ_REG.accueil();
      box.querySelector(`.rg[data-i="${j}"] [data-rg-dep="${fl.dataset.rgDep}"]`)?.focus();
      sauver();
    });
    box.addEventListener("change", (e) => {
      const sw = e.target.closest("[data-rg-on]");
      if (!sw) return;
      const i = Number(sw.closest(".rg").dataset.i);
      PREFS.rangees = PREFS.rangees.map((x, k) => (k === i ? { ...x, on: sw.checked } : x));
      sw.closest(".rg").classList.toggle("off", !sw.checked);
      sauver();
    });
  },

  motdepasse() {
    $("#reg-mdp-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = e.target;
      const actuel = $("#reg-mdp-actuel").value, nouveau = $("#reg-mdp-nouveau").value;
      if (nouveau.length < 8) { statutReg("reg-mdp-statut", "8 caractères minimum.", "err"); return; }
      await occupe(f.querySelector("[type=submit]"), async () => {
        try {
          await api("/api/admin/password", { method: "POST", body: { actuel, nouveau } });
          f.reset();
          statutReg("reg-mdp-statut", "Mot de passe changé ✓", "ok");
          toast("Mot de passe changé");
        } catch (err) { statutReg("reg-mdp-statut", err.message, "err"); }
      });
    });
  },

  async plateformes() {
    const box = $("#reg-plats");
    if (!box) return;
    box.innerHTML = squeletteLignes(5);
    let toutes = [];
    try {
      const [{ providers = [] }] = await Promise.all([api("/api/providers/all"), chargerReglages()]);
      toutes = providers;
    } catch (e) { box.innerHTML = erreurHtml(e); return; }
    const mes = () => new Set((Reg.reglages.mes_plateformes || []).map((x) => canonPlatform(x).toLowerCase()));
    const rendre = () => {
      const q = sansAccents($("#reg-plats-q").value.trim());
      const m = mes();
      const liste = toutes.filter((p) => !q || sansAccents(p.nom).includes(q))
        .sort((a, b) => (m.has(b.nom.toLowerCase()) - m.has(a.nom.toLowerCase())));
      box.innerHTML = liste.length ? liste.map((p) => {
        const ty = platformType(p.nom);
        return `<label class="plat"><img src="${posterSrc(p.logo)}" alt="" loading="lazy">
          <span class="tx"><b>${esc(p.nom)}</b><span>${ty === "sub" ? "Abonnement" : ty === "buy" ? "Achat ou location" : "Streaming"}</span></span>
          <input type="checkbox" class="sw" data-plat="${esc(p.nom)}"${m.has(p.nom.toLowerCase()) ? " checked" : ""} aria-label="${esc(p.nom)}"></label>`;
      }).join("") : `<p class="muted petit" style="padding:12px">Aucune plateforme ne correspond.</p>`;
    };
    rendre();
    $("#reg-plats-q").addEventListener("input", plusTard(rendre, 120));
    box.addEventListener("change", async (e) => {
      const c = e.target.closest("[data-plat]");
      if (!c) return;
      const nom = c.dataset.plat;
      const avant = Reg.reglages.mes_plateformes || [];
      const apres = c.checked ? avant.concat([nom]) : avant.filter((x) => canonPlatform(x).toLowerCase() !== nom.toLowerCase());
      c.disabled = true;
      try {
        await enregistrerReglages({ mes_plateformes: apres }, { message: c.checked ? `${nom} ajouté à tes plateformes` : `${nom} retiré` });
        MES_PLATEFORMES = new Set(apres.map((x) => canonPlatform(x).toLowerCase()));
        resumePlateformes();
      } catch (err) { c.checked = !c.checked; toastErr(err); }
      finally { c.disabled = false; }
    });
  },

  reparer() {
    $("#reg-verifier")?.addEventListener("click", (e) => occupe(e.currentTarget, async () => {
      try {
        const { fixes = {} } = await api("/api/repair", { method: "POST", body: { simulation: true } });
        const f = fixes.films_vu_sans_visionnage || 0, ep = fixes.episodes_incoherents || 0;
        if (!f && !ep) { statutReg("reg-reparer-statut", "Tout est en ordre ✓ Rien à corriger.", "ok"); $("#reg-reparer").hidden = true; return; }
        statutReg("reg-reparer-statut", `À corriger : ${pluriel(f, "film « vu » sans visionnage", "films « vus » sans visionnage")}, ${pluriel(ep, "épisode au compteur incohérent", "épisodes au compteur incohérent")}.`);
        $("#reg-reparer").hidden = false;
      } catch (err) { statutReg("reg-reparer-statut", err.message, "err"); }
    }));
    $("#reg-reparer")?.addEventListener("click", (e) => occupe(e.currentTarget, async () => {
      try {
        const { fixes = {} } = await api("/api/repair", { method: "POST", body: {} });
        statutReg("reg-reparer-statut", `Corrigé : ${pluriel(fixes.films_vu_sans_visionnage || 0, "film « vu » réintégré", "films « vus » réintégrés")}, ${pluriel(fixes.episodes_incoherents || 0, "épisode remis d'aplomb", "épisodes remis d'aplomb")}.`, "ok");
        $("#reg-reparer").hidden = true;
        signaler("titre", { lot: true });
      } catch (err) { statutReg("reg-reparer-statut", err.message, "err"); }
    }));
  },

  async notifications() {
    try { await chargerReglages(); } catch (e) { toastErr(e); return; }
    MAJ_REG.notifications();
    $("#reg-discord")?.addEventListener("change", async (e) => {
      const on = e.target.checked;
      try { await enregistrerReglages({ notif_discord_enabled: on }, { message: on ? "Notifications activées" : "Notifications coupées" }); resumeNotifs(); }
      catch (err) { e.target.checked = !on; toastErr(err); }
    });
    $$("#reg-det [data-reg='notifications'] [data-cle]").forEach((inp) => {
      const sauver = async () => {
        const cle = inp.dataset.cle, v = inp.value.trim();
        if ((Reg.reglages[cle] || "") === v) return;
        try { await enregistrerReglages({ [cle]: v }); }
        catch (err) { toastErr(err); }
      };
      inp.addEventListener("change", sauver);
      inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); inp.blur(); } });
    });
    $("#reg-notif-test")?.addEventListener("click", (e) => occupe(e.currentTarget, async () => {
      try {
        const r = await api("/api/settings/notif-test", { method: "POST" });
        statutReg("reg-notif-statut", `Test envoyé ✓ (${(r.canaux || []).join(", ") || "Discord"})`, "ok");
      } catch (err) { statutReg("reg-notif-statut", err.message, "err"); }
    }));
  },

  sauvegarde() {
    const fichier = $("#reg-import-fichier");
    $("#reg-import")?.addEventListener("click", () => fichier.click());
    fichier?.addEventListener("change", async () => {
      const fi = fichier.files && fichier.files[0];
      fichier.value = "";
      if (!fi) return;
      let dump;
      try { dump = JSON.parse(await fi.text()); if (!Array.isArray(dump.titres)) throw new Error(); }
      catch (_) { statutReg("reg-import-statut", "Ce fichier n'est pas une sauvegarde cinéthèque.", "err"); return; }
      const ok = await confirmer(`Remplacer ta bibliothèque par « ${fi.name} » ?`, {
        ok: "Remplacer", danger: true,
        detail: `${pluriel(dump.titres.length, "titre")} dans le fichier. Tes titres, épisodes vus, listes et journal actuels sont remplacés ; une sauvegarde de l'état actuel est d'abord téléchargée.` });
      if (!ok) return;
      statutReg("reg-import-statut", "Sauvegarde de l'état actuel…");
      try {
        await telechargerSauvegarde();
        statutReg("reg-import-statut", "Restauration…");
        const r = await api("/api/import", { method: "POST", body: dump });
        statutReg("reg-import-statut", `Restauré ✓ ${r.titres !== undefined ? pluriel(r.titres, "titre") : ""}`.trim(), "ok");
        apresGrandChangement();
      } catch (err) { statutReg("reg-import-statut", err.message, "err"); }
    });
  },

  async site() {
    MAJ_REG.site();
    $("#reg-maj")?.addEventListener("click", async (e) => {
      const b = e.currentTarget;
      const ok = await confirmer("Mettre à jour le site maintenant ?", { ok: "Mettre à jour",
        detail: "La dernière version est récupérée sur GitHub et le site redémarre quelques secondes. Si elle ne répond pas, l'ancienne revient toute seule." });
      if (!ok) return;
      await occupe(b, async () => {
        try {
          const r = await api("/api/update", { method: "POST" });
          statutReg("reg-maj-statut", r.message || "Mise à jour lancée…", "ok");
          await attendreRedemarrage();
        } catch (err) { statutReg("reg-maj-statut", err.message, "err"); }
      });
    });
  },

  async tmdb() {
    try { await chargerReglages(); } catch (e) { toastErr(e); return; }
    MAJ_REG.tmdb();
    $("#reg-tmdb-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const cle = $("#reg-tmdb-cle").value.trim(), region = $("#reg-region").value.trim().toUpperCase();
      if (region && !/^[A-Z]{2}$/.test(region)) { statutReg("reg-tmdb-statut", "Le pays s'écrit en 2 lettres (ex. FR).", "err"); return; }
      await occupe(e.target.querySelector("[type=submit]"), async () => {
        try {
          const patch = { tmdb_region: region || "FR" };
          if (cle) patch.tmdb_api_key = cle;
          await enregistrerReglages(patch, { message: "" });
          $("#reg-tmdb-cle").value = "";
          MAJ_REG.tmdb();
          statutReg("reg-tmdb-statut", "Enregistré ✓", "ok");
          if (cle) { CT.tmdb = true; $("#tmdb-bandeau")?.remove(); }
        } catch (err) { statutReg("reg-tmdb-statut", err.message, "err"); }
      });
    });
    $("#reg-tmdb-test")?.addEventListener("click", (e) => occupe(e.currentTarget, async () => {
      try {
        await api("/api/settings/tmdb-test", { method: "POST" });
        statutReg("reg-tmdb-statut", "La clé fonctionne ✓", "ok");
      } catch (err) { statutReg("reg-tmdb-statut", err.message, "err"); }
    }));
  },

  async cloudflare() {
    try {
      const [c] = await Promise.all([api("/api/cloudflare"), chargerReglages()]);
      $("#reg-cf-team").value = c.team || "";
      $("#reg-cf-aud").value = c.aud || "";
      $("#reg-cf-verify").checked = !!c.verify;
      $("#reg-cf-sso").checked = !!Reg.reglages.cf_sso_enabled;
    } catch (e) { toastErr(e); }
    $("#reg-cf-sso")?.addEventListener("change", async (e) => {
      const on = e.target.checked;
      try { await enregistrerReglages({ cf_sso_enabled: on }, { message: on ? "Connexion automatique activée" : "Connexion automatique coupée" }); }
      catch (err) { e.target.checked = !on; toastErr(err); }
    });
    $("#reg-cf-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      await occupe(e.target.querySelector("[type=submit]"), async () => {
        try {
          const c = await api("/api/cloudflare", { method: "POST", body: {
            team: $("#reg-cf-team").value, aud: $("#reg-cf-aud").value, verify: $("#reg-cf-verify").checked } });
          $("#reg-cf-team").value = c.team || "";
          toast("Cloudflare enregistré");
        } catch (err) { toastErr(err); }
      });
    });
    $("#reg-cf-diag")?.addEventListener("click", (e) => occupe(e.currentTarget, async () => {
      const out = $("#reg-cf-sortie");
      out.hidden = false;
      out.textContent = "Diagnostic…";
      try {
        const d = await api("/api/diagnostic");
        out.textContent = `Équipe : ${d.team || "—"}\nAUD : ${d.aud || "—"}\nVérification du jeton : ${d.verify ? "activée" : "désactivée"}\n`
          + `E-mail reçu de Cloudflare : ${d.header_email || "—"}\nJeton reçu : ${d.has_token ? "oui" : "non"}\n`
          + `Jeton : ${d.jwt_status}${d.jwt_email ? ` (${d.jwt_email})` : ""}${d.jwt_error ? `\nDétail : ${d.jwt_error}` : ""}`;
      } catch (err) { out.textContent = err.message; }
    }));
  },

  async mcp() {
    await MAJ_REG.mcp();
    $("#reg-mcp-gen")?.addEventListener("click", async (e) => {
      const b = e.currentTarget;
      const ok = await confirmer("Générer une nouvelle clé pour Claude ?", { ok: "Générer",
        detail: "Si une clé existe déjà, elle cesse aussitôt de fonctionner : il faudra mettre la nouvelle dans le connecteur." });
      if (!ok) return;
      await occupe(b, async () => {
        try {
          const { cle } = await api("/api/mcp/cle", { method: "POST" });
          afficherCleMcp(cle);
          await MAJ_REG.mcp();
        } catch (err) { toastErr(err); }
      });
    });
    $("#reg-mcp-revoquer")?.addEventListener("click", async (e) => {
      const b = e.currentTarget;
      const ok = await confirmer("Révoquer la clé ?", { ok: "Révoquer", danger: true, detail: "Claude n'aura plus accès au site tant qu'une nouvelle clé n'est pas générée." });
      if (!ok) return;
      await occupe(b, async () => {
        try {
          await api("/api/mcp/cle", { method: "DELETE" });
          $("#reg-mcp-cle").hidden = true;
          $("#reg-mcp-cle").innerHTML = "";
          toast("Clé révoquée");
          await MAJ_REG.mcp();
        } catch (err) { toastErr(err); }
      });
    });
    $("#reg-mcp-cle")?.addEventListener("click", (e) => {
      const b = e.target.closest("[data-copier]");
      if (b) copier(b.closest(".copie").querySelector("code").textContent, b);
    });
  },

  reinitialiser() {
    const mot = $("#reg-reset-mot"), b = $("#reg-reset");
    const attendu = (v) => sansAccents(v.trim()) === "reinitialiser";
    mot?.addEventListener("input", () => { b.disabled = !attendu(mot.value); });
    b?.addEventListener("click", () => occupe(b, async () => {
      if (!attendu(mot.value)) return;
      try {
        if (SUPER_ADMIN) {
          statutReg("reg-reset-statut", "Sauvegarde téléchargée d'abord…");
          await telechargerSauvegarde();
        }
        statutReg("reg-reset-statut", "Effacement…");
        await api("/api/reset", { method: "POST" });
        mot.value = "";
        b.disabled = true;
        statutReg("reg-reset-statut", "Bibliothèque réinitialisée.", "ok");
        toast("Bibliothèque réinitialisée");
        apresGrandChangement();
      } catch (err) { statutReg("reg-reset-statut", err.message, "err"); }
    }));
  },
};

/* --------------------------------------------- mises à jour des panneaux */
MAJ_REG.apparence = () => {
  const ap = $("#reg-icone-apercu");
  if (ap) ap.src = `/static/icones/${PREFS.accent}-180.png`;
  const deja = $("#reg-icone-deja");
  if (deja) deja.hidden = !(navigator.standalone || matchMedia("(display-mode: standalone)").matches);
  $$("#reg-accents [data-v]").forEach((b) => {
    const on = b.dataset.v === PREFS.accent;
    b.classList.toggle("on", on);
    b.setAttribute("aria-checked", on ? "true" : "false");
    b.tabIndex = on ? 0 : -1;
  });
  for (const [id, cle] of [["#reg-theme", "theme"], ["#reg-affiche", "affiche"]]) {
    $$(`${id} [data-v]`).forEach((b) => {
      const on = b.dataset.v === PREFS[cle];
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }
  const lg = $("#reg-legendes");
  if (lg) lg.checked = !!PREFS.legendes;
  const vue = $("#reg-vue");
  if (vue) vue.value = PREFS.vue_biblio || "grille";
};
MAJ_REG.accueil = () => {
  const rep = $("#reg-reprendre");
  if (rep) rep.checked = PREFS.reprendre !== "rangee";
  const box = $("#reg-rangees");
  if (!box || !Reg._rangees) return;
  const r = PREFS.rangees || [];
  // Le focus reste sur la même commande après un nouveau rendu.
  const f = document.activeElement && box.contains(document.activeElement) ? document.activeElement : null;
  const cible = f && f.closest(".rg") ? `.rg[data-i="${f.closest(".rg").dataset.i}"] ${f.hasAttribute("data-rg-on") ? "[data-rg-on]" : `[data-rg-dep="${f.dataset.rgDep}"]`}` : null;
  box.innerHTML = r.map((x, i) => `<div class="rg${x.on ? "" : " off"}" data-i="${i}">
      <input type="checkbox" class="sw" data-rg-on${x.on ? " checked" : ""} aria-label="Afficher « ${esc(Reg._rangees[x.id] || x.id)} »">
      <span class="tx">${esc(Reg._rangees[x.id] || x.id)}</span>
      <button type="button" class="fl" data-rg-dep="-1" aria-label="Monter"${i === 0 ? " disabled" : ""}>${ic("chevu", "s18")}</button>
      <button type="button" class="fl" data-rg-dep="1" aria-label="Descendre"${i === r.length - 1 ? " disabled" : ""}>${ic("chevd", "s18")}</button>
    </div>`).join("");
  if (cible) box.querySelector(cible)?.focus();
};
MAJ_REG.notifications = () => {
  const s = Reg.reglages || {};
  const sw = $("#reg-discord");
  if (sw) sw.checked = !!s.notif_discord_enabled;
  $$("#reg-det [data-reg='notifications'] [data-cle]").forEach((inp) => {
    if (document.activeElement !== inp) inp.value = s[inp.dataset.cle] || "";
  });
};
MAJ_REG.site = async () => {
  try {
    const v = await chargerVersion();
    $("#reg-version-n").textContent = v.version ? "v" + v.version : "inconnue";
    $("#reg-version-msg").textContent = v.message ? `Dernier changement : ${v.message}` : "";
  } catch (e) { $("#reg-version-n").textContent = "inconnue"; }
};
MAJ_REG.tmdb = () => {
  const s = Reg.reglages || {};
  const cle = $("#reg-tmdb-cle");
  if (cle) cle.placeholder = s.tmdb_configuree ? "Clé enregistrée · laisse vide pour la garder" : "Colle ta clé API (v3)";
  const reg = $("#reg-region");
  if (reg && document.activeElement !== reg) reg.value = s.tmdb_region || "FR";
};
MAJ_REG.mcp = async () => {
  try {
    const m = await api("/api/mcp");
    $("#reg-mcp-statut").textContent = m.active ? `active · clé créée le ${m.cree}` : "désactivé (aucune clé)";
    $("#reg-mcp-revoquer").hidden = !m.active;
    $("#reg-mcp-gen").innerHTML = `${ic("key", "s18")}${m.active ? "Générer une nouvelle clé" : "Générer une clé"}`;
    const etat = $("#reg-mcp-etat");
    if (etat) etat.textContent = m.active ? "Actif · Claude peut piloter le site" : "Avancé · piloter le site avec Claude";
  } catch (_) { $("#reg-mcp-statut").textContent = "inconnu"; }
};

/* Connecteur Claude (R8) : chaque valeur avec son bouton « Copier ». */
function afficherCleMcp(cle) {
  const box = $("#reg-mcp-cle");
  const ligne = (lbl, val) => `<div class="lbl-mono" style="margin-top:12px">${esc(lbl)}</div>
    <div class="copie"><code>${esc(val)}</code><button type="button" class="btn xs" data-copier>${ic("copy", "s16")}Copier</button></div>`;
  box.innerHTML = `<div class="bandeau-c">${ic("alert", "s18")}<span>Copie ces valeurs maintenant : la clé ne sera plus affichée.</span></div>
    ${ligne("Adresse du serveur", `${location.origin}/mcp`)}
    ${ligne("En-tête", "Authorization")}
    ${ligne("Valeur de l'en-tête", `Bearer ${cle}`)}
    <p class="muted petit" style="margin-top:10px">Variante : l'en-tête <code>X-API-Key</code> avec la clé seule. En dernier recours, la clé dans l'adresse :</p>
    ${ligne("Adresse avec la clé", `${location.origin}/mcp/${cle}`)}`;
  box.hidden = false;
}

/* --------------------------------------------- résumés dans la liste */
function resumePlateformes() {
  const el = $("#reg-plats-n");
  if (!el || !Reg.reglages) return;
  const m = Reg.reglages.mes_plateformes || [];
  el.textContent = m.length ? `${pluriel(m.length, "plateforme")} : ${m.slice(0, 3).join(", ")}${m.length > 3 ? "…" : ""}` : "Tes abonnements de streaming";
}
function resumeNotifs() {
  const el = $("#reg-notif-etat");
  if (el && Reg.reglages) el.textContent = Reg.reglages.notif_discord_enabled ? "Activées · nouveaux épisodes et sorties" : "Désactivées";
}
async function resumesReglages() {
  chargerVersion().then((v) => { const el = $("#reg-version"); if (el && v.version) el.textContent = `Version installée : v${v.version}`; }).catch(() => {});
  if (!SUPER_ADMIN) return;
  try { await chargerReglages(); resumePlateformes(); resumeNotifs(); } catch (_) { /* hors ligne */ }
  MAJ_REG.mcp();
}

/* ------------------------------------------------------------- outils */
/* Télécharge la sauvegarde (R6) avant une restauration ou un effacement ;
   échoue (et arrête tout) si elle n'a pas pu être récupérée. */
async function telechargerSauvegarde() {
  const r = await fetch("/api/export", { headers: { "X-Cinetheque": "1" } });
  if (!r.ok) throw new Error("La sauvegarde n'a pas pu être téléchargée : rien n'a été effacé.");
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `cinetheque-sauvegarde-${isoLocal()}.json`;
  document.body.append(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
}
function apresGrandChangement() {
  MaBiblio.perimer();
  Accueil._perime = true;
  Profil._perime = true;
  signaler("titre", { lot: true });
  signaler("listes", {});
}
/* Après « Mettre à jour » : on attend que le site réponde, puis on recharge. */
async function attendreRedemarrage() {
  await new Promise((r) => setTimeout(r, 9000));
  for (let i = 0; i < 20; i++) {
    try {
      const v = await api("/api/version");
      statutReg("reg-maj-statut", `Site redémarré · v${v.version}. Rechargement…`, "ok");
      await purgeShell();
      setTimeout(() => location.reload(), 900);
      return;
    } catch (_) { await new Promise((r) => setTimeout(r, 3000)); }
  }
  statutReg("reg-maj-statut", "Le site met du temps à revenir : recharge la page dans un instant.", "err");
}

document.addEventListener("ct:prefs", () => { MAJ_REG.apparence(); if (Reg._rangees) MAJ_REG.accueil(); });
