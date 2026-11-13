// Captures du dossier « encre » : node captures.js <demo.html> <dossier de sortie> [échelle]
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const URL = "file://" + path.resolve(process.argv[2]);
const SORTIE = path.resolve(process.argv[3]);
const ECHELLE = Number(process.argv[4] || 2);
fs.mkdirSync(SORTIE, { recursive: true });
const pause = (p, ms) => p.waitForTimeout(ms);

async function ouvrir(browser, { w, h, schema, tel = true, accent = null, hash = "accueil" }) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: ECHELLE, isMobile: tel, hasTouch: tel, colorScheme: schema });
  if (accent) await ctx.addInitScript((a) => { try { localStorage.setItem("encre-apparence", JSON.stringify({ accent: a, theme: "auto" })); } catch (_) {} }, accent);
  const page = await ctx.newPage();
  await page.goto(URL + "#" + hash);
  await page.waitForFunction(() => window.Encre && Encre._demarre && document.fonts.status === "loaded");
  await page.evaluate(() => document.fonts.ready);
  await pause(page, 700);
  return { ctx, page };
}
// Fait défiler pour que la rangée d'images passe sous la barre flottante.
async function sousLaBarre(page, sel = ".demo-mur") {
  await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    const y = el.getBoundingClientRect().top + scrollY - (innerHeight - 150);
    scrollTo({ top: y, behavior: "instant" });
  }, sel);
  await pause(page, 400);
}

(async () => {
  const browser = await chromium.launch();
  const fichier = (nom) => path.join(SORTIE, nom);

  // 1. Téléphone sombre : l'accueil, la barre en verre au-dessus des images.
  let { ctx, page } = await ouvrir(browser, { w: 390, h: 844, schema: "dark" });
  await sousLaBarre(page);
  await page.screenshot({ path: fichier("telephone-sombre.png") });
  await page.screenshot({ path: fichier("barre-flottante-flou.png"), clip: { x: 0, y: 844 - 170, width: 390, height: 170 } });
  // 2. Feuille « Plus ».
  await page.click(".tab[data-encre-plus]");
  await pause(page, 600);
  await page.screenshot({ path: fichier("telephone-plus.png") });
  await ctx.close();

  // 3. Téléphone clair.
  ({ ctx, page } = await ouvrir(browser, { w: 390, h: 844, schema: "light" }));
  await sousLaBarre(page);
  await page.screenshot({ path: fichier("telephone-clair.png") });
  await page.screenshot({ path: fichier("barre-flottante-flou-clair.png"), clip: { x: 0, y: 844 - 170, width: 390, height: 170 } });
  await ctx.close();

  // 4. Les 5 couleurs d'accent (haut de l'accueil, téléphone sombre).
  for (const a of ["lavande", "or", "ambre", "corail", "menthe"]) {
    ({ ctx, page } = await ouvrir(browser, { w: 390, h: 844, schema: "dark", accent: a, hash: "apparence" }));
    await page.screenshot({ path: fichier(`accent-${a}.png`) });
    await ctx.close();
  }

  // 5. Ordinateur sombre (accueil) et clair (réglages).
  ({ ctx, page } = await ouvrir(browser, { w: 1440, h: 900, schema: "dark", tel: false }));
  await page.screenshot({ path: fichier("ordinateur-sombre.png") });
  await page.keyboard.press("Control+k");
  await pause(page, 300);
  await page.keyboard.type("r");
  await pause(page, 500);
  await page.screenshot({ path: fichier("ordinateur-recherche.png") });
  await ctx.close();
  ({ ctx, page } = await ouvrir(browser, { w: 1440, h: 900, schema: "light", tel: false, hash: "reglages" }));
  await page.screenshot({ path: fichier("ordinateur-clair-reglages.png") });
  await ctx.close();

  // 6. Une confirmation (téléphone sombre) et un menu (ordinateur).
  ({ ctx, page } = await ouvrir(browser, { w: 390, h: 844, schema: "dark", hash: "retours" }));
  await page.click(".li[data-demo='danger']");
  await pause(page, 600);
  await page.screenshot({ path: fichier("telephone-confirmation.png") });
  await ctx.close();

  await browser.close();
  console.log(fs.readdirSync(SORTIE).join("\n"));
})();
