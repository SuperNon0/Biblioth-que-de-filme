// Teste les aperçus du système « Design encre » dans un cadre simulé.
// node tester-ds.js <dossier ds/project> <dossier de test> [Comp,Comp…]
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const http = require("http");

const SRC = path.resolve(process.argv[2]);
const TEST = path.resolve(process.argv[3]);
const SEULES = process.argv[4] ? process.argv[4].split(",") : null;
fs.rmSync(TEST, { recursive: true, force: true });
fs.cpSync(SRC, path.join(TEST, "project"), { recursive: true });
const P = path.join(TEST, "project");
const comps = fs.readdirSync(path.join(P, "components")).filter((c) => fs.existsSync(path.join(P, "components", c, "preview.html")))
  .filter((c) => !SEULES || SEULES.includes(c));

function cadre(comp, mode) {
  const prev = fs.readFileSync(path.join(P, "components", comp, "preview.html"), "utf8");
  const m = prev.match(/^[ \t]*<!--\s*@dsCard\b((?:(?!--)[^\r\n])*)(?:[\r\n]\s*)?-->/);
  const attrs = m ? m[1] : "";
  const h = Number((attrs.match(/height=(\d+)/) || [])[1] || 300);
  const doc = `<!doctype html><html data-theme="${mode}" data-mode="${mode}" style="color-scheme:${mode}" class="${mode}"><head><meta name="referrer" content="no-referrer"><link rel="stylesheet" href="../../tokens.css"><link rel="stylesheet" href="../bundle.css"></head><body><script src="../bundle.js"></script>` + prev + "</body></html>";
  fs.writeFileSync(path.join(P, "components", comp, `cadre-${mode}.html`), doc);
  return { h, marker: attrs.trim() };
}

const types = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".woff2": "font/woff2", ".svg": "image/svg+xml", ".json": "application/json" };
const serveur = http.createServer((req, res) => {
  const f = path.join(TEST, decodeURIComponent(req.url.split("?")[0]));
  if (!f.startsWith(TEST) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { "Content-Type": types[path.extname(f)] || "application/octet-stream" });
  fs.createReadStream(f).pipe(res);
});

(async () => {
  await new Promise((r) => serveur.listen(0, r));
  const base = `http://127.0.0.1:${serveur.address().port}/project/components/`;
  const browser = await chromium.launch();
  const lignes = [];
  let pb = 0;
  for (const comp of comps) {
    for (const mode of ["dark", "light"]) {
      const { h, marker } = cadre(comp, mode);
      for (const w of [360, 760, 1100]) {
        const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
        const page = await ctx.newPage();
        const erreurs = [];
        page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") erreurs.push(m.type() + ": " + m.text()); });
        page.on("pageerror", (e) => erreurs.push("pageerror: " + e.message));
        page.on("requestfailed", (r) => erreurs.push("requête: " + r.url()));
        await page.goto(base + comp + `/cadre-${mode}.html`);
        await page.evaluate(() => document.fonts.ready);
        await page.waitForTimeout(comp === "Cover" ? 300 : 500);
        const r = await page.evaluate(() => {
          const d = document.documentElement;
          const polices = ["16px Archivo", "16px 'DM Serif Display'", "italic 16px 'DM Serif Display'", "500 12px 'DM Mono'"].map((f) => document.fonts.check(f));
          return {
            sw: d.scrollWidth, cw: d.clientWidth, sh: d.scrollHeight,
            theme: d.dataset.theme, accent: d.dataset.accent || "", titre: document.title,
            polices, encre: !!window.Encre, bg: getComputedStyle(document.body).backgroundColor,
            fontsOk: [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family + " " + f.style + " " + f.weight),
          };
        });
        const deborde = r.sw > r.cw;
        const tropHaut = r.sh > h;
        if (erreurs.length || deborde) pb++;
        lignes.push(`${comp.padEnd(15)} ${mode.padEnd(5)} ${String(w).padStart(4)}  h=${h} contenu=${r.sh}${tropHaut ? " (DÉPASSE)" : ""}${deborde ? ` DÉBORDE ${r.sw}>${r.cw}` : ""} theme=${r.theme} accent=${r.accent} encre=${r.encre} polices=${r.polices.map(Number).join("")}${erreurs.length ? "\n    " + erreurs.join("\n    ") : ""}`);
        if (w === 760 || (comp === "Cover" && w === 1100)) {
          fs.mkdirSync(path.join(TEST, "captures"), { recursive: true });
          await page.screenshot({ path: path.join(TEST, "captures", `${comp}-${mode}-${w}.png`), fullPage: true });
        }
        await ctx.close();
      }
    }
  }
  await browser.close();
  serveur.close();
  console.log(lignes.join("\n"));
  console.log(`\n${comps.length} aperçus, ${pb} cas avec erreur ou débordement`);
})();
