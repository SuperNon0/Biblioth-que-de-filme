// Hauteur naturelle de chaque aperçu (cadres déjà écrits par tester-ds.js).
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const http = require("http");
const TEST = path.resolve(process.argv[2]);
const P = path.join(TEST, "project");
const comps = fs.readdirSync(path.join(P, "components")).filter((c) => fs.existsSync(path.join(P, "components", c, "cadre-dark.html")));
const serveur = http.createServer((req, res) => {
  const f = path.join(TEST, decodeURIComponent(req.url.split("?")[0]));
  if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
  const t = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".woff2": "font/woff2" }[path.extname(f)] || "application/octet-stream";
  res.writeHead(200, { "Content-Type": t }); fs.createReadStream(f).pipe(res);
});
(async () => {
  await new Promise((r) => serveur.listen(0, r));
  const base = `http://127.0.0.1:${serveur.address().port}/project/components/`;
  const browser = await chromium.launch();
  for (const comp of comps) {
    const prev = fs.readFileSync(path.join(P, "components", comp, "preview.html"), "utf8");
    const h = Number((prev.match(/height=(\d+)/) || [])[1]);
    const out = [];
    for (const w of [360, 600, 760, 1100]) {
      const ctx = await browser.newContext({ viewport: { width: w, height: 100 } });
      const page = await ctx.newPage();
      await page.goto(base + comp + "/cadre-dark.html");
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(250);
      const n = await page.evaluate(() => Math.ceil(document.body.getBoundingClientRect().height));
      out.push(`${w}:${n}`);
      await ctx.close();
    }
    console.log(comp.padEnd(15), "h=" + h, out.join("  "));
  }
  await browser.close(); serveur.close();
})();
