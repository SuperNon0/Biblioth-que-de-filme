#!/usr/bin/env python3
"""Génère les icônes d'app (écran d'accueil) pour chaque couleur d'accent.

Outil de développement (nécessite Pillow : apt install python3-pil) :
    python3 scripts/generer-icones.py
Produit panel/static/icones/<accent>-<taille>.png (180, 192, 512) et
réécrit les icônes historiques (apple-touch-icon.png, icon-*.png) en « or ».
Le serveur n'en a pas besoin : les PNG produits sont committés.

Dessin « plein cadre » : le clap occupe toute l'icône (fond = accent), sans
coins arrondis ni marge sur les PNG, car iOS et Android arrondissent
eux-mêmes. Le SVG (onglet du navigateur) garde des coins arrondis.
"""
import os
import sys

# Mêmes valeurs que :root[data-accent] dans style.css (variante sombre).
ACCENTS = {
    #           accent     haut (plus clair)  encre
    "or":      ("#e8c547", "#f2d76a", "#14110a"),
    "ambre":   ("#f0a64a", "#f6bf74", "#1a1206"),
    "corail":  ("#ff7a59", "#ff9c82", "#2a0d05"),
    "menthe":  ("#4fd1b5", "#7fe0cb", "#05211b"),
    "lavande": ("#a99bff", "#c4baff", "#120d2e"),
}
TAILLES = (180, 192, 512)


def svg(accent, haut, encre):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{haut}"/><stop offset="1" stop-color="{accent}"/>
  </linearGradient><clipPath id="c"><rect width="100" height="100" rx="22"/></clipPath></defs>
  <g clip-path="url(#c)">
  <rect width="100" height="100" fill="url(#g)"/>
  <path d="M0 33 L100 15 L100 37 L0 55 Z" fill="{encre}" opacity=".94"/>
  <g fill="{accent}">
    <path d="M9 32.6 l11 -2 l-6.5 16.5 l-11 2 Z"/>
    <path d="M33 28.3 l11 -2 l-6.5 16.5 l-11 2 Z"/>
    <path d="M57 24 l11 -2 l-6.5 16.5 l-11 2 Z"/>
    <path d="M81 19.7 l11 -2 l-6.5 16.5 l-11 2 Z"/>
  </g>
  <path d="M38 61 L69 77 L38 93 Z" fill="{encre}"/>
  </g>
</svg>"""


def _hex(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def dessiner(accent, haut, encre, taille):
    """Même dessin que svg(), tracé avec Pillow (suréchantillonné 4×)."""
    from PIL import Image, ImageDraw
    n = taille * 4
    k = n / 100
    a, h, e = _hex(accent), _hex(haut), _hex(encre)
    img = Image.new("RGB", (n, n))
    d = ImageDraw.Draw(img)
    for y in range(n):  # dégradé vertical haut → accent
        t = y / (n - 1)
        d.line([(0, y), (n, y)], fill=tuple(round(h[i] + (a[i] - h[i]) * t) for i in range(3)))
    # bande du clap (opacité .94 sur le dégradé : quasi l'encre)
    bande = Image.new("L", (n, n), 0)
    ImageDraw.Draw(bande).polygon([(0, 33 * k), (n, 15 * k), (n, 37 * k), (0, 55 * k)], fill=240)
    img.paste(Image.new("RGB", (n, n), e), (0, 0), bande)
    d = ImageDraw.Draw(img)
    for x0, y0 in ((9, 32.6), (33, 28.3), (57, 24), (81, 19.7)):
        pts = [(x0, y0), (x0 + 11, y0 - 2), (x0 + 4.5, y0 + 14.5), (x0 - 6.5, y0 + 16.5)]
        d.polygon([(x * k, y * k) for x, y in pts], fill=a)
    d.polygon([(38 * k, 61 * k), (69 * k, 77 * k), (38 * k, 93 * k)], fill=e)
    return img.resize((taille, taille), Image.LANCZOS)


def main():
    racine = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "panel", "static")
    dossier = os.path.join(racine, "icones")
    os.makedirs(dossier, exist_ok=True)
    for nom, (acc, haut, encre) in ACCENTS.items():
        with open(os.path.join(dossier, f"{nom}.svg"), "w", encoding="utf-8") as fh:
            fh.write(svg(acc, haut, encre) + "\n")
        for t in TAILLES:
            dessiner(acc, haut, encre, t).save(os.path.join(dossier, f"{nom}-{t}.png"), optimize=True)
    # Icônes historiques (liens externes, Discord…) : version « or ».
    for t, f in ((180, "apple-touch-icon.png"), (192, "icon-192.png"),
                 (512, "icon-512.png"), (512, "icon-maskable-512.png")):
        dessiner(*ACCENTS["or"], t).save(os.path.join(racine, f), optimize=True)
    print("Icônes générées dans", os.path.normpath(dossier))


if __name__ == "__main__":
    sys.exit(main())
