// Clique les boutons des aperçus interactifs et vérifie ce qui s'ouvre.
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const http = require("http");
const TEST = path.resolve(process.argv[2]);
const serveur = http.createServer((req, res) => {
  const f = path.join(TEST, decodeURIComponent(req.url.split("?")[0]));
  if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
  const t = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".woff2": "font/woff2" }[path.extname(f)] || "application/octet-stream";
  res.writeHead(200, { "Content-Type": t }); fs.createReadStream(f).pipe(res);
});
let ok = 0, ko = 0;
const verif = (nom, cond, det = "") => { if (cond) ok++; else ko++; console.log((cond ? "  ok  " : "  ÉCHEC ") + nom + (det ? "  " + det : "")); };
(async () => {
  await new Promise((r) => serveur.listen(0, r));
  const base = `http://127.0.0.1:${serveur.address().port}/project/components/`;
  const browser = await chromium.launch();
  async function ouvrir(comp, { w = 760, h = 500, mode = "dark", tel = false, local = null } = {}) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, isMobile: false, hasTouch: tel });  // un cadre (iframe) prend la largeur de la carte : pas de viewport mobile
    if (local) await ctx.addInitScript((v) => { try { localStorage.setItem("encre-apparence", v); } catch (_) {} }, local);
    const page = await ctx.newPage();
    const erreurs = [];
    page.on("pageerror", (e) => erreurs.push(e.message));
    page.on("console", (m) => { if (m.type() === "error") erreurs.push(m.text()); });
    await page.goto(base + comp + `/cadre-${mode}.html`);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(300);
    return { ctx, page, erreurs };
  }
  const html = (page) => page.evaluate(() => ({ th: document.documentElement.dataset.theme, ac: document.documentElement.dataset.accent, len: history.length, url: location.href }));

  // 1. Le choix d'un autre aperçu (localStorage) ne déteint pas.
  console.log("Choix gardé ailleurs");
  for (const mode of ["dark", "light"]) {
    const { ctx, page, erreurs } = await ouvrir("Bouton", { mode, local: JSON.stringify({ accent: "or", theme: mode === "dark" ? "clair" : "sombre" }) });
    const r = await html(page);
    verif(`Bouton ${mode} : reste ${mode} et lavande`, r.th === mode && r.ac === "lavande", JSON.stringify(r));
    verif(`Bouton ${mode} : sans erreur`, erreurs.length === 0, erreurs.join(" | "));
    await ctx.close();
  }

  // 2. Pastilles : choisir Menthe, puis Clair.
  console.log("Pastilles");
  {
    const { ctx, page, erreurs } = await ouvrir("Pastilles");
    const avant = await html(page);
    await page.click('.past[data-v="menthe"]');
    await page.waitForTimeout(300);
    let r = await html(page);
    verif("menthe appliquée", r.ac === "menthe", JSON.stringify(r));
    const acc = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--accent").trim());
    verif("--accent suit (menthe sombre)", /4fd1b5/i.test(acc) || acc.includes("accent-menthe"), acc);
    const accRendu = await page.evaluate(() => { const e = document.createElement("i"); e.style.color = "var(--accent)"; document.body.append(e); const c = getComputedStyle(e).color; e.remove(); return c; });
    verif("couleur rendue = menthe", accRendu === "rgb(79, 209, 181)", accRendu);
    await page.click('[data-encre-theme] [data-v="clair"]');
    await page.waitForTimeout(300);
    r = await html(page);
    verif("clair appliqué", r.th === "light", JSON.stringify(r));
    const fond = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    verif("fond clair", fond === "rgb(245, 243, 238)", fond);
    verif("historique intact", r.len === avant.len && r.url === avant.url, `${avant.len}→${r.len}`);
    verif("sans erreur", erreurs.length === 0, erreurs.join(" | "));
    await ctx.close();
  }

  // 3. Confirmation : les trois boutons.
  console.log("Confirmation");
  for (const [txt, attendu] of [["Confirmer", ".conf"], ["Action sensible", ".conf"], ["Demander un nom", "input"]]) {
    const { ctx, page, erreurs } = await ouvrir("Confirmation", { h: 600 });
    const avant = await html(page);
    await page.getByRole("button", { name: txt, exact: true }).click();
    await page.waitForTimeout(450);
    const n = await page.locator(".feuille:not(.statique) " + attendu).count();
    verif(`« ${txt} » ouvre une vraie feuille`, n > 0);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);
    const reste = await page.locator(".feuille:not(.statique)").count();
    verif(`« ${txt} » se ferme avec Échap`, reste === 0, String(reste));
    const r = await html(page);
    verif(`« ${txt} » sans historique ni erreur`, r.len === avant.len && erreurs.length === 0, erreurs.join(" | "));
    await ctx.close();
  }

  // 4. Message : les trois boutons.
  console.log("Message");
  {
    const { ctx, page, erreurs } = await ouvrir("Message", { h: 400 });
    for (const txt of ["Message", "Avec « Annuler »", "Erreur"]) {
      await page.getByRole("button", { name: txt, exact: true }).click();
      await page.waitForTimeout(250);
    }
    const n = await page.locator("#toasts .toast, .toasts .toast").count();
    verif("trois messages affichés", n >= 3, String(n));
    verif("sans erreur", erreurs.length === 0, erreurs.join(" | "));
    await ctx.close();
  }

  // 5. Menu : à la souris (ordinateur) et au doigt (téléphone).
  console.log("Menu");
  for (const [w, tel, sel] of [[1100, false, ".pop"], [390, true, ".feuille:not(.statique)"]]) {
    const { ctx, page, erreurs } = await ouvrir("Menu", { w, h: 600, tel });
    await page.click("[data-menu]");
    await page.waitForTimeout(450);
    const n = await page.locator(sel).count();
    verif(`menu ${tel ? "au doigt" : "à la souris"} ouvert`, n > 0, String(n));
    verif("sans erreur", erreurs.length === 0, erreurs.join(" | "));
    await ctx.close();
  }

  // 6. Recherche, FeuillePlus, Reglages, Selection, Bulle, Copie, Aide.
  console.log("Autres");
  {
    const { ctx, page, erreurs } = await ouvrir("Recherche", { w: 1100, h: 600 });
    await page.getByRole("button", { name: /Ouvrir la recherche/ }).click();
    await page.waitForTimeout(400);
    await page.keyboard.type("rég");
    await page.waitForTimeout(400);
    const res = await page.locator(".palette:not(.statique) .pal-it").count();
    verif("recherche ouverte avec résultats", res > 0, String(res));
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
    await page.keyboard.press("Control+k");
    await page.waitForTimeout(400);
    verif("Ctrl K ouvre aussi", (await page.locator(".palette:not(.statique)").count()) > 0);
    verif("sans erreur", erreurs.length === 0, erreurs.join(" | "));
    await ctx.close();
  }
  {
    const { ctx, page, erreurs } = await ouvrir("FeuillePlus", { w: 390, h: 700, tel: true });
    await page.getByRole("button", { name: /vraie feuille/ }).click();
    await page.waitForTimeout(500);
    verif("feuille Plus ouverte", (await page.locator(".feuille:not(.statique)").count()) > 0);
    const lien = page.locator(".feuille:not(.statique) a").first();
    await lien.click();
    await page.waitForTimeout(500);
    const r = await html(page);
    verif("un lien referme la feuille sans changer d'adresse", (await page.locator(".feuille:not(.statique)").count()) === 0 && !r.url.includes("#"), r.url);
    verif("sans erreur", erreurs.length === 0, erreurs.join(" | "));
    await ctx.close();
  }
  for (const w of [390, 1100]) {
    const { ctx, page, erreurs } = await ouvrir("Reglages", { w, h: 600, tel: w < 600 });
    await page.locator("[data-reg]").nth(1).click();
    await page.waitForTimeout(300);
    const vis = await page.evaluate(() => [...document.querySelectorAll("[data-panneau]")].filter((s) => !s.hidden).map((s) => s.dataset.panneau));
    verif(`réglages ${w} : rubrique ouverte`, vis.length === 1, vis.join(","));
    if (w < 600) {
      const liste = await page.locator(".reg-liste").isVisible();
      verif("téléphone : la liste laisse place au réglage", !liste);
      await page.locator("[data-retour]").first().click();
      await page.waitForTimeout(200);
      verif("téléphone : retour à la liste", await page.locator(".reg-liste").isVisible());
    } else {
      const gap = await page.evaluate(() => getComputedStyle(document.querySelector(".reg-liste")).display + " " + getComputedStyle(document.querySelector(".reg-liste")).rowGap);
      verif("ordinateur : liste en grille avec son espace", gap === "grid 18px", gap);
    }
    verif("sans erreur", erreurs.length === 0, erreurs.join(" | "));
    await ctx.close();
  }
  {
    const { ctx, page, erreurs } = await ouvrir("Bulle", { h: 400 });
    await page.locator(".q").first().click();
    await page.waitForTimeout(300);
    verif("bulle ouverte", (await page.locator(".bulle:not(.statique)").count()) > 0);
    verif("sans erreur", erreurs.length === 0, erreurs.join(" | "));
    await ctx.close();
  }
  {
    const { ctx, page, erreurs } = await ouvrir("Selection", { w: 390, h: 400, tel: true });
    verif("sélection sans erreur", erreurs.length === 0, erreurs.join(" | "));
    await ctx.close();
  }
  {
    const { ctx, page, erreurs } = await ouvrir("Copie");
    await ctx.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.getByRole("button", { name: /Copier/ }).first().click();
    await page.waitForTimeout(300);
    const t = await page.getByRole("button", { name: /Copi/ }).first().innerText();
    verif("Copier → « Copié »", /Copié/.test(t), t);
    verif("sans erreur", erreurs.length === 0, erreurs.join(" | "));
    await ctx.close();
  }
  {
    const { ctx, page, erreurs } = await ouvrir("Aide");
    const q = page.locator("details summary, .faq-q, [data-faq]").nth(1);
    if (await q.count()) { await q.click(); await page.waitForTimeout(200); }
    verif("aide sans erreur", erreurs.length === 0, erreurs.join(" | "));
    await ctx.close();
  }
  await browser.close(); serveur.close();
  console.log(`\n${ok} vérifications réussies, ${ko} échecs`);
})();
