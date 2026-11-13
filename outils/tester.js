// Tests de la démonstration « encre » : node tester.js <chemin de demo.html>
const { chromium } = require("playwright");
const path = require("path");

const fichier = process.argv[2];
const URL = "file://" + path.resolve(fichier);
const PAGES = ["accueil", "briques", "retours", "apparence", "reglages", "connexion", "aide"];
const pause = (p, ms) => p.waitForTimeout(ms);
const resultats = [];
function ok(nom, cond, detail = "") {
  resultats.push({ nom, ok: !!cond, detail });
  console.log(`${cond ? "OK  " : "ÉCHEC"} ${nom}${detail ? " — " + detail : ""}`);
}

async function ouvrir(browser, opts) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  const erreurs = [];
  page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") erreurs.push(`${m.type()}: ${m.text()}`); });
  page.on("pageerror", (e) => erreurs.push("pageerror: " + e.message));
  page.on("requestfailed", (r) => erreurs.push("requête: " + r.url().slice(-60) + " " + (r.failure() || {}).errorText));
  await page.goto(URL + "#accueil");
  await page.waitForFunction(() => window.Encre && Encre._demarre && document.fonts.status === "loaded");
  await pause(page, 300);
  return { ctx, page, erreurs };
}

async function debordements(page, etiquette) {
  for (const p of PAGES) {
    await page.evaluate((h) => { location.hash = h; }, p);
    await pause(page, 120);
    const r = await page.evaluate(() => {
      const w = document.documentElement.clientWidth;
      const fautifs = [...document.querySelectorAll(".page.on *")].filter((el) => {
        const b = el.getBoundingClientRect();
        if (!b.width || getComputedStyle(el).position === "fixed") return false;
        let x = el.parentElement;
        while (x && x !== document.body) { if (/(auto|scroll|hidden)/.test(getComputedStyle(x).overflowX)) return false; x = x.parentElement; }
        return b.right > w + 0.5 || b.left < -0.5;
      }).slice(0, 3).map((el) => el.tagName.toLowerCase() + "." + [...el.classList].join("."));
      return { sw: document.documentElement.scrollWidth, w, fautifs };
    });
    ok(`${etiquette} · #${p} sans défilement de côté`, r.sw <= r.w && !r.fautifs.length, r.fautifs.join(", ") || `${r.sw}/${r.w}`);
  }
}

async function contrastes(page, etiquette) {
  return page.evaluate((etiquette) => {
    const sonde = document.createElement("i");
    document.body.append(sonde);
    const rgb = (v) => {
      sonde.style.color = `var(${v})`;
      const m = getComputedStyle(sonde).color.match(/[\d.]+/g).map(Number);
      return m.slice(0, 3);
    };
    const lum = ([r, g, b]) => [r, g, b].map((c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; })
      .reduce((s, c, i) => s + c * [0.2126, 0.7152, 0.0722][i], 0);
    const ratio = (a, b) => { const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
    const paires = [["--text", "--bg"], ["--soft", "--bg"], ["--muted", "--bg"], ["--muted", "--card"], ["--accent", "--bg"],
      ["--accent", "--card"], ["--ink", "--accent"], ["--ok", "--bg"], ["--ok-ink", "--ok"], ["--prog", "--bg"], ["--prog-ink", "--prog"],
      ["--danger", "--bg"], ["--warn", "--bg"]];
    const res = paires.map(([a, b]) => ({ paire: `${a} / ${b}`, r: Math.round(ratio(a, b) * 100) / 100 }));
    sonde.remove();
    return { etiquette, min: Math.min(...res.map((x) => x.r)), faibles: res.filter((x) => x.r < 4.5) };
  }, etiquette);
}

(async () => {
  const browser = await chromium.launch();

  // ------------------------------------------------------------ téléphone sombre
  {
    const { ctx, page, erreurs } = await ouvrir(browser, { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, colorScheme: "dark" });
    const etat = await page.evaluate(() => {
      const tb = document.querySelector(".tabbar"), cs = getComputedStyle(tb);
      const usesManquants = [...document.querySelectorAll("use")].map((u) => u.getAttribute("href")).filter((h) => !document.getElementById(h.slice(1)));
      return {
        tabVisible: cs.display !== "none" && tb.getBoundingClientRect().bottom <= innerHeight,
        flou: cs.backdropFilter || cs.webkitBackdropFilter,
        side: getComputedStyle(document.querySelector(".side")).display,
        top: getComputedStyle(document.querySelector(".top")).display,
        accent: document.documentElement.dataset.accent,
        onglet: document.querySelector(".tab.on") && document.querySelector(".tab.on").dataset.page,
        polices: ["16px Archivo", "16px 'DM Serif Display'", "500 12px 'DM Mono'"].map((f) => document.fonts.check(f)),
        police: getComputedStyle(document.querySelector(".page-t")).fontFamily,
        usesManquants,
      };
    });
    ok("téléphone · barre d'onglets visible en bas", etat.tabVisible);
    ok("téléphone · barre en verre flouté", /blur\(16px\)/.test(etat.flou), etat.flou);
    ok("téléphone · menu de gauche caché, barre du haut visible", etat.side === "none" && etat.top !== "none", `${etat.side}/${etat.top}`);
    ok("téléphone · accent lavande par défaut", etat.accent === "lavande", etat.accent);
    ok("téléphone · onglet Accueil allumé", etat.onglet === "accueil", etat.onglet);
    ok("téléphone · polices chargées", etat.polices.every(Boolean), etat.polices.join(","));
    ok("téléphone · toutes les icônes existent", !etat.usesManquants.length, etat.usesManquants.slice(0, 5).join(","));
    await debordements(page, "téléphone");

    // Plus → feuille, puis retour du téléphone.
    await page.evaluate(() => { location.hash = "accueil"; });
    await pause(page, 150);
    await page.click(".tab[data-encre-plus]");
    await pause(page, 350);
    let s = await page.evaluate(() => ({
      feuille: !!document.querySelector(".feuille:not(.sort)"), tuiles: document.querySelectorAll(".feuille .qt").length,
      overlay: document.body.classList.contains("overlay-ouvert"),
      tab: getComputedStyle(document.querySelector(".tabbar")).opacity, hash: location.hash,
    }));
    ok("Plus · feuille ouverte avec 4 grandes tuiles", s.feuille && s.tuiles === 4, `${s.tuiles} tuiles`);
    ok("Plus · la barre d'onglets se cache", s.overlay);
    await page.goBack();
    await pause(page, 400);
    s = await page.evaluate(() => ({ feuille: !!document.querySelector(".feuille"), hash: location.hash, overlay: document.body.classList.contains("overlay-ouvert") }));
    ok("retour du téléphone · referme la feuille sans quitter la page", !s.feuille && !s.overlay && s.hash === "#accueil", s.hash);

    // Plus → lien Réglages : ferme puis navigue.
    await page.click(".tab[data-encre-plus]");
    await pause(page, 350);
    await page.click(".feuille .qt[href='#reglages']");
    await pause(page, 500);
    s = await page.evaluate(() => ({ hash: location.hash, feuille: !!document.querySelector(".feuille"), plusOn: document.querySelector(".tab[data-encre-plus]").classList.contains("on"),
      liste: getComputedStyle(document.querySelector(".reg-liste")).display, det: getComputedStyle(document.querySelector(".reg-det")).display }));
    ok("Plus → Réglages · ouvre la page, feuille fermée", s.hash === "#reglages" && !s.feuille, s.hash);
    ok("Plus allumé sur une page sans onglet", s.plusOn);
    ok("Réglages (téléphone) · la liste d'abord", s.liste !== "none" && s.det === "none", `${s.liste}/${s.det}`);
    await page.click("[data-reg='notifications']");
    await pause(page, 300);
    s = await page.evaluate(() => ({ hash: location.hash, liste: getComputedStyle(document.querySelector(".reg-liste")).display,
      vis: [...document.querySelectorAll(".reg-panneau")].filter((x) => !x.hidden).map((x) => x.dataset.panneau) }));
    ok("Réglages (téléphone) · un réglage s'ouvre en plein écran", s.hash === "#reglages/notifications" && s.liste === "none" && s.vis.join() === "notifications", JSON.stringify(s));
    await page.goBack();
    await pause(page, 300);
    s = await page.evaluate(() => ({ hash: location.hash, liste: getComputedStyle(document.querySelector(".reg-liste")).display }));
    ok("Réglages (téléphone) · retour revient à la liste", s.hash === "#reglages" && s.liste !== "none", s.hash);

    // Retours : toast + Annuler.
    await page.evaluate(() => { location.hash = "retours"; });
    await pause(page, 200);
    await page.click("[data-demo='annuler']");
    await pause(page, 200);
    s = await page.evaluate(() => ({ n: document.querySelector("#d-compteur").textContent, bouton: !!document.querySelector(".toast .a") }));
    ok("Annuler · message avec bouton « Annuler »", s.bouton && s.n === "1", JSON.stringify(s));
    await page.click(".toast .a");
    await pause(page, 600);
    s = await page.evaluate(() => ({ n: document.querySelector("#d-compteur").textContent, txt: [...document.querySelectorAll(".toast .tx")].map((x) => x.textContent) }));
    ok("Annuler · revient en arrière et le dit", s.n === "0" && s.txt.includes("Annulé"), JSON.stringify(s));

    // Confirmer (OK) puis confirmer danger (Annuler).
    await page.click("[data-demo='confirmer']");
    await pause(page, 350);
    s = await page.evaluate(() => ({ titre: (document.querySelector(".feuille .tt") || {}).textContent, ok: (document.querySelector(".feuille [data-oui]") || {}).textContent }));
    ok("Confirmer · feuille intégrée (pas de confirm())", s.titre === "Retirer ce titre ?" && s.ok === "Retirer", JSON.stringify(s));
    await page.click(".feuille [data-oui]");
    await pause(page, 450);
    s = await page.evaluate(() => [...document.querySelectorAll(".toast .tx")].map((x) => x.textContent));
    ok("Confirmer · la réponse arrive", s.includes("Retiré"), s.join(" | "));
    await page.click(".li[data-demo='danger']");
    await pause(page, 350);
    s = await page.evaluate(() => ({ plein: !!document.querySelector(".feuille [data-oui].dn.plein") }));
    ok("Confirmer (sensible) · bouton rouge", s.plein);
    await page.click(".feuille [data-non]");
    await pause(page, 450);
    ok("Confirmer (sensible) · Annuler ferme", !(await page.$(".feuille")));

    // Demander.
    await page.click(".li[data-demo='demander']");
    await pause(page, 350);
    await page.fill("#encre-champ", "Films d'été");
    await page.click(".feuille [data-oui]");
    await pause(page, 450);
    s = await page.evaluate(() => [...document.querySelectorAll(".toast .tx")].map((x) => x.textContent));
    ok("Demander · le nom revient", s.includes("Liste « Films d'été » créée"), s.join(" | "));

    // Menu → feuille au doigt.
    await page.click("[data-demo='menu']");
    await pause(page, 350);
    s = await page.evaluate(() => ({ lignes: document.querySelectorAll(".feuille .q-ext").length, pop: !!document.querySelector(".pop") }));
    ok("Menu (téléphone) · s'ouvre en feuille", s.lignes === 4 && !s.pop, JSON.stringify(s));
    await page.goBack();
    await pause(page, 400);

    // Sélection : barre d'actions à la place des onglets.
    await page.click("[data-demo='selection']");
    await pause(page, 350);
    s = await page.evaluate(() => ({ sel: document.body.classList.contains("mode-sel"), barre: !document.querySelector("#d-selection").hidden,
      tab: getComputedStyle(document.querySelector(".tabbar")).opacity, flou: getComputedStyle(document.querySelector("#d-selection")).backdropFilter }));
    ok("Sélection · la barre d'actions remplace les onglets", s.sel && s.barre && Number(s.tab) < 0.1, JSON.stringify(s));
    await page.screenshot({ path: path.join(path.dirname(fichier), "..", "outils", "verif-selection.png") });
    await page.click("[data-sel='vu']");
    await pause(page, 400);
    s = await page.evaluate(() => ({ sel: document.body.classList.contains("mode-sel"), a: !!document.querySelector(".toast .a") }));
    ok("Sélection · action + « Annuler »", !s.sel && s.a);

    // Occupé : pas de double envoi.
    await page.click(".btn.w[data-demo='occupe']");
    s = await page.evaluate(() => { const b = document.querySelector(".btn.w[data-demo='occupe']"); return { occ: b.classList.contains("occupe"), busy: b.getAttribute("aria-busy") }; });
    ok("Bouton occupé · grisé pendant l'envoi", s.occ && s.busy === "true");
    await pause(page, 1600);

    // Thème : auto → clair → sombre → auto.
    const themes = [];
    for (let i = 0; i < 3; i++) { await page.click(".top [data-demo='theme']"); await pause(page, 120); themes.push(await page.evaluate(() => { const d = document.documentElement.dataset; return (d.theme || "?") + ("encreAuto" in d ? "+auto" : ""); })); }
    ok("Thème · bouton lune : clair, sombre, auto (qui suit l'appareil)", themes.join() === "light,dark,dark+auto", themes.join());
    // Automatique : l'appareil passe en clair pendant la visite, puis revient en sombre.
    await page.emulateMedia({ colorScheme: "light" }); await pause(page, 150);
    const suitClair = await page.evaluate(() => document.documentElement.dataset.theme);
    await page.emulateMedia({ colorScheme: "dark" }); await pause(page, 150);
    const suitSombre = await page.evaluate(() => document.documentElement.dataset.theme);
    ok("Thème automatique · suit l'appareil quand il change", suitClair === "light" && suitSombre === "dark", suitClair + "," + suitSombre);

    // Accent : pastille menthe.
    await page.evaluate(() => { location.hash = "apparence"; });
    await pause(page, 200);
    const avant = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--accent").trim());
    await page.click(".page.on [data-encre-accent] [data-v='menthe']");
    await pause(page, 200);
    s = await page.evaluate(() => ({ a: document.documentElement.dataset.accent, v: getComputedStyle(document.documentElement).getPropertyValue("--accent").trim(),
      on: document.querySelectorAll("[data-encre-accent] [data-v='menthe'].on").length, garde: localStorage.getItem("encre-apparence") }));
    ok("Accent · menthe appliqué partout et gardé", s.a === "menthe" && s.v !== avant && s.on === 2 && /menthe/.test(s.garde), JSON.stringify(s));
    await page.reload();
    await page.waitForFunction(() => window.Encre && Encre._demarre);
    s = await page.evaluate(() => document.documentElement.dataset.accent);
    ok("Accent · toujours là après rechargement", s === "menthe", s);
    await page.click(".page.on [data-encre-accent] [data-v='lavande']");

    // Loupe de la barre du haut → recherche, retour la ferme.
    await page.click(".top [data-encre-recherche]");
    await pause(page, 300);
    ok("Recherche (téléphone) · la loupe ouvre la recherche", !!(await page.$(".palette .pal-it")));
    await page.goBack();
    await pause(page, 350);
    ok("Recherche (téléphone) · retour la ferme", !(await page.$(".palette")));

    // Bulle « ? ».
    await page.evaluate(() => { location.hash = "accueil"; });
    await pause(page, 200);
    await page.click(".page.on .sec-t .q");
    await pause(page, 150);
    ok("Bulle « ? » · s'ouvre", !!(await page.$(".bulle")));

    ok("téléphone · aucune erreur dans la console", !erreurs.length, erreurs.join(" | "));
    await ctx.close();
  }

  // ------------------------------------------------------------ ordinateur
  for (const schema of ["dark", "light"]) {
    const { ctx, page, erreurs } = await ouvrir(browser, { viewport: { width: 1440, height: 900 }, colorScheme: schema });
    const e = await page.evaluate(() => ({
      side: getComputedStyle(document.querySelector(".side")).display, tab: getComputedStyle(document.querySelector(".tabbar")).display,
      top: getComputedStyle(document.querySelector(".top")).display, on: (document.querySelector(".side-it.on") || {}).dataset,
    }));
    ok(`ordinateur ${schema} · menu de gauche, sans barre d'onglets`, e.side !== "none" && e.tab === "none" && e.top === "none", JSON.stringify(e));
    await debordements(page, `ordinateur ${schema}`);
    await page.evaluate(() => { location.hash = "retours"; });
    await pause(page, 200);
    await page.click("[data-demo='menu']");
    await pause(page, 200);
    ok(`ordinateur ${schema} · menu flottant à la souris`, !!(await page.$(".pop .mi")));
    await page.mouse.click(700, 120);
    await pause(page, 300);
    ok(`ordinateur ${schema} · clic à côté ferme le menu`, !(await page.$(".pop")));
    await page.keyboard.press("Control+k");
    await pause(page, 300);
    await page.keyboard.type("rég");
    await pause(page, 350);
    const res = await page.evaluate(() => [...document.querySelectorAll(".palette .pal-it b")].map((b) => b.textContent));
    ok(`ordinateur ${schema} · Ctrl K cherche`, res.join() === "Réglages", res.join());
    await page.keyboard.press("Escape");
    await pause(page, 400);
    ok(`ordinateur ${schema} · Échap ferme`, !(await page.$(".palette")));
    await page.keyboard.press("/");
    await pause(page, 300);
    await page.keyboard.type("zone");
    await pause(page, 350);
    const res2 = await page.evaluate(() => [...document.querySelectorAll(".palette .pal-g")].map((g) => g.textContent.trim()).join("+") + ":" + [...document.querySelectorAll(".palette .pal-it b")].map((b) => b.textContent).join(","));
    ok(`ordinateur ${schema} · « / » ouvre la recherche, résultats du site groupés`, res2 === "Briques:Zone sensible", res2);
    await page.keyboard.press("Enter");
    await pause(page, 500);
    ok(`ordinateur ${schema} · Entrée ouvre le résultat`, !(await page.$(".palette")) && (await page.evaluate(() => location.hash)) === "#briques");
    await page.evaluate(() => { location.hash = "reglages"; });
    await pause(page, 200);
    const r = await page.evaluate(() => ({ liste: getComputedStyle(document.querySelector(".reg-liste")).display, det: getComputedStyle(document.querySelector(".reg-det")).display }));
    ok(`ordinateur ${schema} · réglages en deux colonnes`, r.liste !== "none" && r.det !== "none", JSON.stringify(r));
    console.log("contrastes", JSON.stringify(await contrastes(page, schema)));
    for (const a of ["or", "ambre", "corail", "menthe"]) {
      await page.evaluate((a) => { document.documentElement.dataset.accent = a; }, a);
      console.log("contrastes", JSON.stringify(await contrastes(page, `${schema} ${a}`)));
    }
    ok(`ordinateur ${schema} · aucune erreur dans la console`, !erreurs.length, erreurs.join(" | "));
    await ctx.close();
  }

  // ------------------------------------------------------------ tablette, petit téléphone
  for (const [w, hgt] of [[360, 740], [768, 1024]]) {
    const { ctx, page, erreurs } = await ouvrir(browser, { viewport: { width: w, height: hgt }, isMobile: true, hasTouch: true, colorScheme: "light" });
    await debordements(page, `${w}px clair`);
    const t = await page.evaluate(() => { const b = document.querySelector(".tabbar").getBoundingClientRect(); return { l: Math.round(b.left), w: Math.round(b.width) }; });
    console.log(`${w}px barre d'onglets`, JSON.stringify(t));
    ok(`${w}px · aucune erreur`, !erreurs.length, erreurs.join(" | "));
    await ctx.close();
  }

  await browser.close();
  const echecs = resultats.filter((r) => !r.ok);
  console.log(`\n${resultats.length - echecs.length}/${resultats.length} vérifications réussies`);
  process.exit(echecs.length ? 1 : 0);
})();
