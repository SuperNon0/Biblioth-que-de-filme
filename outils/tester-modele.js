const { chromium } = require("playwright");
const path = require("path");
(async () => {
  const b = await chromium.launch();
  const out = [];
  for (const [w, h, tel, schema] of [[390, 844, true, "dark"], [1280, 800, false, "light"]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, isMobile: tel, hasTouch: tel, colorScheme: schema });
    const p = await ctx.newPage();
    const err = [];
    p.on("console", (m) => { if (["error", "warning"].includes(m.type())) err.push(m.text()); });
    p.on("pageerror", (e) => err.push(e.message));
    await p.goto("file://" + path.resolve(process.argv[2]));
    await p.waitForFunction(() => window.Encre && Encre._demarre);
    await p.waitForTimeout(300);
    const r = await p.evaluate(() => ({ page: document.querySelector(".page.on").dataset.page, tab: (document.querySelector(".tab.on, .side-it.on") || {}).textContent,
      sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
    out.push(`${w}px accueil=${r.page} actif=${(r.tab || "").trim()} débord=${r.sw > r.cw}`);
    if (tel) {
      await p.click(".tab[data-encre-plus]"); await p.waitForTimeout(350);
      out.push("Plus ouvert=" + !!(await p.$(".feuille")));
      await p.click(".feuille .qt[href='#liste']"); await p.waitForTimeout(500);
      out.push("Plus→Liste " + (await p.evaluate(() => location.hash + " feuille=" + !!document.querySelector(".feuille") + " page=" + document.querySelector(".page.on").dataset.page)));
    }
    await p.evaluate(() => { location.hash = "reglages"; }); await p.waitForTimeout(200);
    await p.click(".page.on [data-v='corail']"); await p.waitForTimeout(200);
    await p.click(".page.on [data-encre-theme] [data-v='clair']"); await p.waitForTimeout(200);
    out.push("accent=" + (await p.evaluate(() => document.documentElement.dataset.accent + " thème=" + document.documentElement.dataset.theme)));
    await p.evaluate(() => { location.hash = "accueil"; }); await p.waitForTimeout(200);
    await p.click("#essai"); await p.waitForTimeout(350);
    await p.click(".feuille [data-oui]"); await p.waitForTimeout(450);
    out.push("toast=" + (await p.evaluate(() => [...document.querySelectorAll(".toast .tx")].map((t) => t.textContent).join("|"))));
    out.push("erreurs=" + (err.join(" | ") || "aucune"));
    await ctx.close();
  }
  await b.close();
  console.log(out.join("\n"));
})();
