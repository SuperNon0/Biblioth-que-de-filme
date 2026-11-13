"""Assemble la démonstration du design « encre ».

- dossier-encre/demo.html : charge polices.css, encre.css et encre.js à côté d'elle.
- outils/demo-artifact.html : tout en un (polices en data URI, CSS et JS en ligne),
  sans <html>/<head>/<body>, pour la publier en page Artifact.

Usage : python3 -I construire.py <racine du scratchpad>
"""
import base64
import re
import sys
from pathlib import Path

racine = Path(sys.argv[1])
dossier = racine / "dossier-encre"
modele = (racine / "outils" / "demo.tpl.html").read_text(encoding="utf-8")
sprite = (dossier / "icones.svg").read_text(encoding="utf-8").strip()


def icones(html):
    def svg(m):
        nom, *classes = m.group(1).split()
        cls = " ".join(["i", *classes])
        return f'<svg class="{cls}" aria-hidden="true"><use href="#i-{nom}"/></svg>'
    return re.sub(r"\{\{i:([^}]+)\}\}", svg, html)


def remplacer(html, marque, contenu):
    assert html.count(marque) == 1, marque
    return html.replace(marque, contenu)


base = icones(modele)
assert "{{" not in base, "icône non remplacée"
base = remplacer(base, "<!-- SPRITE -->", sprite)

# ------------------------------------------------------------ version fichiers
demo = remplacer(base, "<!-- STYLES -->",
                 '<link rel="stylesheet" href="polices.css">\n  <link rel="stylesheet" href="encre.css">')
demo = remplacer(demo, "<!-- SCRIPTS -->", '<script defer src="encre.js"></script>')
(dossier / "demo.html").write_text(demo, encoding="utf-8")

# Squelette minimal (même assemblage).
modele = icones((racine / "outils" / "modele.tpl.html").read_text(encoding="utf-8"))
assert "{{" not in modele, "icône non remplacée (modèle)"
modele = remplacer(modele, "<!-- SPRITE -->", sprite)
modele = remplacer(modele, "<!-- STYLES -->",
                   '<link rel="stylesheet" href="polices.css">\n  <link rel="stylesheet" href="encre.css">')
modele = remplacer(modele, "<!-- SCRIPTS -->", '<script defer src="encre.js"></script>')
(dossier / "modele.html").write_text(modele, encoding="utf-8")

# ------------------------------------------------------- version tout-en-un
polices = (dossier / "polices.css").read_text(encoding="utf-8")


def data_uri(m):
    donnees = (dossier / m.group(1)).read_bytes()
    return "url(data:font/woff2;base64," + base64.b64encode(donnees).decode("ascii") + ")"


polices = re.sub(r"url\((polices/[^)]+\.woff2)\)", data_uri, polices)
assert "polices/" not in polices.split("*/", 1)[1], "police non intégrée"
css = (dossier / "encre.css").read_text(encoding="utf-8")
js = (dossier / "encre.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
assert "</script" not in js and "</style" not in css + polices

tete, corps = base.split("<body>", 1)
corps = corps.rsplit("</body>", 1)[0]
style_demo = re.search(r"<style>.*?</style>", tete, re.S).group(0)
avant = re.search(r"<script>.*?</script>", tete, re.S).group(0)   # accent/thème avant l'affichage
page = "\n".join([
    "<title>Design encre</title>",
    '<meta name="claude:viewport-fit-sides" content="cover">',
    '<script>document.documentElement.lang = "fr";</script>',
    avant.replace("<script>", "<script>", 1),
    "<style>\n" + polices + "\n</style>",
    "<style>\n" + css + "\n</style>",
    style_demo,
    corps.strip(),
])
# encre.js juste avant le script de la démo (il démarre au DOMContentLoaded, avant elle).
dernier = page.rfind("<script>\n/* ---- Démonstration")
assert dernier > 0
page = page[:dernier] + "<script>\n" + js + "\n</script>\n" + page[dernier:]
(racine / "outils" / "demo-artifact.html").write_text(page, encoding="utf-8")

print("demo.html", len(demo.encode()), "octets ; demo-artifact.html", len(page.encode()), "octets")
