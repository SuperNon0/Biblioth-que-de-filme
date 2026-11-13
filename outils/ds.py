"""Construit le système de design « Design encre » (Artifact de type Design System).

Sortie : <racine>/ds/project/…  (tokens.json, tokens.css, README.md,
components/bundle.css|js, index.d.ts, une fiche par brique, la couverture,
fonts/, puis design-system.json en dernier).

Usage : python3 -I ds.py <racine du scratchpad>
"""
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(sys.argv[1])
DOSSIER = RACINE / "dossier-encre"
SORTIE = RACINE / "ds" / "project"
TITRE = "Design encre"

if SORTIE.parent.exists():
    shutil.rmtree(SORTIE.parent)
(SORTIE / "components").mkdir(parents=True)
(SORTIE / "fonts").mkdir()


def ecrire(chemin, texte):
    p = SORTIE / chemin
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(texte, encoding="utf-8")


# =================================================================== jetons
SOMBRE, CLAIR = "dark", "light"


def deux(sombre, clair):
    return {SOMBRE: sombre, CLAIR: clair}


ACCENTS = [  # nom, sombre (accent, ink), clair (accent, ink), libellé
    ("or", ("#e8c547", "#1b1504"), ("#8a6400", "#ffffff"), "Or"),
    ("ambre", ("#f0a64a", "#1a1206"), ("#995400", "#ffffff"), "Ambre"),
    ("corail", ("#ff7a59", "#2a0d05"), ("#b23c1d", "#ffffff"), "Corail"),
    ("menthe", ("#4fd1b5", "#05211b"), ("#0b7562", "#ffffff"), "Menthe"),
    ("lavande", ("#a99bff", "#120d2e"), ("#5a48d0", "#ffffff"), "Lavande"),
]

COULEURS = [
    ("bg", deux("#0b0f17", "#f5f3ee"),
     "Fond de la page, le plus profond. Sous la barre du haut (mêlé à 86 %) et derrière la carte de connexion."),
    ("surface", deux("#0f1520", "#ffffff"),
     "Un cran au-dessus de `bg` : menu de gauche, boutons-icônes, puces, code, champ de copie."),
    ("card", deux("#141b28", "#ffffff"),
     "Cartes, tuiles, listes, champs de saisie et boutons normaux."),
    ("pop", deux("#182131", "#ffffff"),
     "Ce qui flotte au-dessus de tout : feuilles, menus, messages, bulles, recherche."),
    ("line", deux("#1e2737", "#e7e2d7"),
     "Traits discrets : bord des cartes et des listes, séparation entre deux lignes. Décoratif (1,2 à 1,4:1)."),
    ("line2", deux("#2b3549", "#d5cfc1"),
     "Bordures de ce qui se touche : boutons, puces, segments, barre flottante, poignée des feuilles, interrupteur éteint. Décoratif (1,4 à 1,6:1) : le sens passe aussi par le texte ou l'icône."),
    ("creux", deux("#0f1520", "#ebe7de"),
     "Rail du segment (`.seg`), dans lequel le choix actif ressort en `pop`."),
    ("text", deux("#e7ebf3", "#1b1d22"),
     "Texte principal, qu'on pose sur `bg`, `surface`, `card`, `pop` : au moins 13,5:1 en sombre, 15,2:1 en clair."),
    ("soft", deux("#aab3c5", "#454a55"),
     "Texte secondaire (explications, valeurs de liste, libellés de champ) sur les quatre fonds : au moins 7,6:1 en sombre, 8:1 en clair."),
    ("muted", deux("#8a94aa", "#666b77"),
     "Texte discret (sous-lignes, compteurs, libellés en capitales, onglets inactifs) sur les quatre fonds : au moins 5,3:1 en sombre, 4,8:1 en clair."),
    ("ok", deux("#4fc0ad", "#17725f"),
     "Réussi, terminé, vu : coche pleine, barre de progression finie, message « Enregistré ». Comme texte, sur les quatre fonds : au moins 7,2:1 en sombre, 5,2:1 en clair."),
    ("ok-ink", deux("#04130f", "#ffffff"),
     "Texte ou icône posé sur un fond plein `ok` (coche cochée) : 8,6:1 en sombre, 5,8:1 en clair."),
    ("prog", deux("#8f9cf0", "#5159c9"),
     "En cours : barres d'avancement, bouton « En cours », seconde couleur des répartitions. Comme texte, au moins 6,3:1 en sombre, 5,2:1 en clair."),
    ("prog-ink", deux("#0b0d24", "#ffffff"),
     "Texte posé sur un fond plein `prog` : 7,5:1 en sombre, 5,8:1 en clair."),
    ("danger", deux("#ef7d6b", "#bf3f2c"),
     "Supprimer, erreur, zone sensible. Comme texte, sur les quatre fonds : au moins 6:1 en sombre, 4,8:1 en clair."),
    ("warn", deux("#efb36b", "#94560a"),
     "Attention : demande en attente, avertissement « à lire avant de continuer ». Comme texte, au moins 8,7:1 en sombre, 5,3:1 en clair."),
    ("scrim", deux("rgba(3, 5, 9, 0.62)", "rgba(20, 18, 12, 0.42)"),
     "Voile derrière une feuille ou la recherche (flou de 3 px pour la recherche)."),
    ("glass", deux("rgba(24, 28, 40, 0.74)", "rgba(255, 255, 255, 0.8)"),
     "Le verre des barres flottantes (`.tabbar`, `.barre-act`), toujours avec un flou d'arrière-plan."),
    ("on-img", "#ffffff",
     "Texte et icônes posés sur une image (mêmes valeurs dans les deux thèmes : l'image reste sombre)."),
    ("verre-img", "rgba(10, 12, 16, 0.5)",
     "Fond d'un bouton en verre posé sur une image (`.ib.verre`) et dégradé de lisibilité au bas d'une image."),
    ("img-trait2", "rgba(255, 255, 255, 0.14)",
     "Bord d'un bouton en verre posé sur une image."),
    ("img-bg", deux("#1a2130", "#e4dfd3"),
     "Fond d'une image qui charge (vignettes de la recherche)."),
    ("blanc", "#ffffff",
     "Rond de l'interrupteur et texte du bouton plein `danger` (`.btn.dn.plein`). Sur `danger` : 5,3:1 en clair mais 2,7:1 seulement en sombre (valeur d'origine, gardée telle quelle) : réserve ce bouton aux confirmations, avec un verbe court."),
]
for nom, (ad, idk), (al, il), lib in ACCENTS:
    COULEURS.append((f"accent-{nom}", deux(ad, al),
                     f"Accent « {lib} » (`data-accent=\"{nom}\"`) : vif en sombre, foncé en clair. Comme texte, sur les quatre fonds, au moins 4,8:1."))
for nom, (ad, idk), (al, il), lib in ACCENTS:
    COULEURS.append((f"ink-{nom}", deux(idk, il),
                     f"Texte qu'on pose sur `accent-{nom}` (l'accent « {lib} » : bouton principal, puce active), au moins 5,3:1."))
COULEURS += [
    ("accent", "{accent-lavande}",
     "L'accent affiché : bouton principal, onglet actif, liens, valeur mise en avant, contour du focus clavier. Suit `data-accent` sur `<html>` (lavande par défaut) ; comme texte, au moins 4,8:1 sur les quatre fonds."),
    ("ink", "{ink-lavande}",
     "Texte qu'on pose sur un fond plein `accent` : jamais du blanc écrit en dur. Suit `data-accent` comme `accent`."),
]

OMBRES = [
    ("shadow", deux("0 18px 50px rgba(0, 0, 0, 0.45)", "0 18px 50px rgba(40, 34, 20, 0.16)"),
     "Ce qui flotte : menus, messages, bulles, recherche, fenêtres centrées, carte de connexion."),
    ("shadow-s", deux("0 8px 24px rgba(0, 0, 0, 0.35)", "0 8px 24px rgba(40, 34, 20, 0.12)"),
     "Ombre légère pour un élément qui doit se détacher d'une carte (aucune brique ne s'en sert par défaut)."),
    ("sh-tab", deux("0 14px 40px rgba(0, 0, 0, 0.35)", "0 14px 40px rgba(40, 34, 20, 0.16)"),
     "Ombre de la barre d'onglets flottante."),
    ("sh-feuille", deux("0 -24px 60px rgba(0, 0, 0, 0.4)", "0 -24px 60px rgba(40, 34, 20, 0.14)"),
     "Ombre portée vers le haut d'une feuille du bas (téléphone)."),
    ("sh-plat", "0 2px 8px rgba(0, 0, 0, 0.45)",
     "Ombre courte et dense sous une vignette posée sur une image."),
    ("sh-sw", "0 1px 3px rgba(0, 0, 0, 0.3)",
     "Ombre du rond de l'interrupteur (`.sw`)."),
    ("sh-past", "inset 0 0 0 2px rgba(0, 0, 0, 0.15)",
     "Liseré intérieur des pastilles d'accent (`.past i`)."),
]

ESPACES = [
    ("pad", "16px", "Marge des côtés sur téléphone (`.pages`, `.top`), écrite `max(var(--pad), env(safe-area-inset-left, 0px))` pour s'écarter de l'encoche."),
    ("tab-h", "62px", "Hauteur de la barre d'onglets flottante ; le bas des pages réserve `tab-h` + 52 px."),
    ("side-w", "248px", "Largeur du menu de gauche (1000 px et plus)."),
]
RAYONS = [
    ("r-lg", "14px", "Cartes, tuiles, listes, zone sensible, menus et messages."),
    ("r-md", "10px", "Lignes du menu de gauche, champ de copie, code, avertissements."),
    ("r-sm", "8px", "Petits boutons (`.btn.xs`), coches carrées."),
    ("r-po", "10px", "Squelettes de chargement (`.sk`)."),
    ("r-btn", "10px", "Boutons (`.btn`)."),
]

POLICES = [
    ("Archivo", "archivo-latin.woff2", "400 700", "normal"),
    ("DM Serif Display", "dm-serif-display-latin.woff2", "400", "normal"),
    ("DM Serif Display", "dm-serif-display-italic-latin.woff2", "400", "italic"),
    ("DM Mono", "dm-mono-400-latin.woff2", "400", "normal"),
    ("DM Mono", "dm-mono-500-latin.woff2", "500", "normal"),
]
FAMILLES = {
    "title": '"DM Serif Display", Georgia, "Times New Roman", serif',
    "body": '"Archivo", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    "mono": '"DM Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
}


def style(nom, taille, hauteur, graisse, espacement, exemple, usage):
    return {"name": nom, "fontSize": taille, "lineHeight": hauteur, "fontWeight": graisse,
            "letterSpacing": espacement, "sample": exemple, "usage": usage}


GROUPES_TYPO = [
    {"name": "Titres", "family": "title",
     "note": "DM Serif Display, toujours en graisse 400 : jamais en gras. Les tailles sont multipliées par --t-scale (1,05).",
     "styles": [
         style("titre-page", "28.35px", 1.05, 400, "0", "Bonjour Noë",
               "Titre de page (`.page-t`) : 27 px × 1,05, et 30 px × 1,05 sur ordinateur."),
         style("titre-feuille", "22.05px", 1.1, 400, "0", "Retirer ce titre ?",
               "Titre d'une feuille ou d'une fenêtre (`.feuille-t`), nom du site (`.wm`)."),
         style("titre-section", "19.95px", 1.15, 400, "0", "Activité récente",
               "Titre de section (`.sec-t`), titre d'une zone sensible."),
         style("chiffre", "28.35px", 1.02, 400, "0", "2 930 h",
               "Valeur d'une tuile (`.tuile .v`)."),
         style("chiffre-grand", "54.6px", 1.02, 400, "0", "2 930",
               "Valeur de la grande tuile sur ordinateur (`.tuile.big .v` ; 42 px sur téléphone)."),
     ]},
    {"name": "Texte", "family": "body",
     "note": "Archivo : tout ce qui se lit. Paragraphes de 68 caractères au plus.",
     "styles": [
         style("texte", "15px", 1.5, 400, "0", "Le texte de tous les jours : résumés, boutons, réglages.",
               "Corps de texte (`body`)."),
         style("ligne-liste", "14px", 1.5, 400, "0", "Marqué comme terminé",
               "Ligne de liste (`.li`), menu de gauche (`.side-it`), corps d'une bulle."),
         style("bouton", "14px", 1.5, 600, "0", "Enregistrer",
               "Boutons (`.btn` ; 13 px en `.sm`, 12 px en `.xs`) et titre d'un réglage."),
         style("texte-petit", "12.5px", 1.5, 400, "0", "Il y a 5 minutes · depuis ton téléphone",
               "Sous-lignes et notes (`.petit`, `small` d'une ligne de liste en 12 px)."),
         style("onglet", "10.5px", 1, 500, "0", "Accueil",
               "Libellé sous l'icône d'un onglet de la barre flottante (`.tab`)."),
         style("saisie", "16px", 1.5, 400, "0", "Soirées pop-corn",
               "Texte tapé dans un champ : jamais moins de 16 px (sinon l'iPhone zoome)."),
     ]},
    {"name": "Libellés", "family": "mono",
     "note": "DM Mono : petits libellés en capitales, compteurs, touches et code.",
     "styles": [
         style("libelle", "11px", 1, 600, "0.1em", "MON COMPTE",
               "Petits libellés au-dessus d'un groupe (`.lbl-mono`, `.reg-g`, `.faq-g`) : toujours en capitales (`text-transform: uppercase`)."),
         style("chiffre-mono", "11.5px", 1.5, 500, "0", "377 · Ctrl K · 14 h 02",
               "Compteurs (`.n`), touches (`.kbd`, 11 px), version du site."),
     ]},
]

TOKENS = {
    "version": 1,
    "name": TITRE,
    "color": {
        "themes": [{"id": SOMBRE, "name": "Sombre"}, {"id": CLAIR, "name": "Clair"}],
        "tokens": [{"name": n, "value": v, "usage": u} for n, v, u in COULEURS],
    },
    "type": {
        "fonts": [{"family": f, "file": "fonts/" + fichier, "weight": g, "style": s} for f, fichier, g, s in POLICES],
        "families": FAMILLES,
        "groups": GROUPES_TYPO,
    },
    "spacing": {"tokens": [{"name": n, "value": v, "usage": u} for n, v, u in ESPACES]},
    "radius": {"tokens": [{"name": n, "value": v, "usage": u} for n, v, u in RAYONS]},
    "shadow": {"tokens": [{"name": n, "value": v, "usage": u} for n, v, u in OMBRES]},
}
ecrire("tokens.json", json.dumps(TOKENS, ensure_ascii=False, indent=2) + "\n")

for _, fichier, _, _ in POLICES:
    shutil.copyfile(DOSSIER / "polices" / fichier, SORTIE / "fonts" / fichier)


# ------------------------------------------------- tokens.css (comme compilé)
def nettoie(u):
    return re.sub(r"[\r\n\f]+", " ", u.replace("*/", "* /").replace("</", "< /")).strip()


def valeur(v):
    m = re.fullmatch(r"\{([^}]+)\}", v)
    return f"var(--{m.group(1)})" if m else v


def nombre(x):
    return str(x) if not isinstance(x, float) else ("%g" % x)


lignes = [f"/* {TITRE} — generated from tokens.json */", f':root, [data-theme="{SOMBRE}"] {{']
for n, v, u in COULEURS:
    v1 = v[SOMBRE] if isinstance(v, dict) else v
    lignes.append(f"  --{n}: {valeur(v1)}; /* {nettoie(u)} */")
for n, v, u in OMBRES:
    v1 = v[SOMBRE] if isinstance(v, dict) else v
    lignes.append(f"  --{n}: {v1}; /* {nettoie(u)} */")
lignes.append("}")
lignes.append(f'[data-theme="{CLAIR}"] {{')
for n, v, u in COULEURS:
    if isinstance(v, dict):
        lignes.append(f"  --{n}: {valeur(v[CLAIR])};")
    elif v.startswith("{"):
        lignes.append(f"  --{n}: {valeur(v)};")
for n, v, u in OMBRES:
    if isinstance(v, dict):
        lignes.append(f"  --{n}: {v[CLAIR]};")
lignes.append("}")
lignes.append(":root {")
for n, v, u in ESPACES + RAYONS:
    lignes.append(f"  --{n}: {v}; /* {nettoie(u)} */")
for cle, pile in FAMILLES.items():
    lignes.append(f"  --font-{cle}: {pile};")
for g in GROUPES_TYPO:
    for s in g["styles"]:
        lignes.append(f"  --text-{s['name']}: {s['fontWeight']} {s['fontSize']}/{nombre(s['lineHeight'])} "
                      f"var(--font-{g['family']}); /* {nettoie(s['usage'])} */")
lignes.append("}")
for g in GROUPES_TYPO:
    for s in g["styles"]:
        lignes += [f".{s['name']} {{", f"  font-family: var(--font-{g['family']});", f"  font-size: {s['fontSize']};",
                   f"  line-height: {nombre(s['lineHeight'])};", f"  font-weight: {s['fontWeight']};",
                   f"  letter-spacing: {s['letterSpacing']};", "}"]
for f, fichier, g, s in POLICES:
    lignes += ["@font-face {", f'  font-family: "{f}";', f'  src: url("fonts/{fichier}") format("woff2");',
               f"  font-weight: {g};", f"  font-style: {s};", "  font-display: swap;", "}"]
ecrire("tokens.css", "\n".join(lignes) + "\n")

# ======================================================= bundle.css et .js
css = (DOSSIER / "encre.css").read_text(encoding="utf-8")
debut = css.index("/* ------------------------------------------------------------------ jetons */")
fin = css.index("/* -------------------------------------------------------------------- base */")
for nom, *_ in ACCENTS:
    ancien = f'.past[data-v="{nom}"] i {{ background: var(--sw-{nom}); }}'
    assert css.count(ancien) == 1, ancien
    css = css.replace(ancien, f'.past[data-v="{nom}"] i {{ background: var(--accent-{nom}); }}')
assert "--sw-" not in css[fin:], "pastille non convertie"
ENTETE_CSS = """/* =========================================================================
   Design encre — les briques (classes CSS), à charger après tokens.css.
   Les valeurs (couleurs, polices, rayons, ombres, mesures) vivent dans
   tokens.json / tokens.css ; ce fichier ne garde que ce qui en découle.
   - Thème : sombre par défaut, clair avec data-theme="light" sur <html>.
   - Accent : data-accent sur <html> (or, ambre, corail, menthe, lavande).
   ========================================================================= */

/* --------------------------------------------- relais vers les jetons */
:root {
  color-scheme: dark;
  --f-title: var(--font-title);
  --f-body: var(--font-body);
  --f-mono: var(--font-mono);
  --t-scale: 1.05;          /* agrandit ou réduit tous les titres d'un coup */
  --ease: cubic-bezier(.2, .8, .2, 1);
}
[data-theme="light"] { color-scheme: light; }
/* Accent choisi (lavande sinon) : la paire accent-<nom> / ink-<nom> des jetons. */
""" + "".join(f':root[data-accent="{n}"] {{ --accent: var(--accent-{n}); --ink: var(--ink-{n}); }}\n' for n, *_ in ACCENTS) + """/* Jetons dérivés de l'accent (recalculés quand il change). */
:root, :root[data-theme] {
  --acc-dim: color-mix(in srgb, var(--accent) 14%, transparent);
  --acc-line: color-mix(in srgb, var(--accent) 45%, transparent);
  --prog-dim: color-mix(in srgb, var(--prog) 16%, transparent);
  --ok-dim: color-mix(in srgb, var(--ok) 14%, transparent);
  --danger-dim: color-mix(in srgb, var(--danger) 12%, transparent);
}

"""
bundle_css = ENTETE_CSS + css[fin:]
assert "</style" not in bundle_css.lower()
ecrire("components/bundle.css", bundle_css)

js = (DOSSIER / "encre.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
assert "<!--" not in js and "</script" not in js.lower()
entete_js = '/* @ds-bundle: {"format":4,"namespace":"Encre","components":[]} */\n'
ecrire("components/bundle.js", entete_js + js)

ecrire("components/index.d.ts", r"""/* Design encre : l'objet global window.Encre (components/bundle.js).
   Les briques elles-mêmes sont des classes CSS (components/bundle.css) :
   aucune n'est un composant React. */

export type EncreAccent = "or" | "ambre" | "corail" | "menthe" | "lavande";
export type EncreTheme = "auto" | "clair" | "sombre";
export interface EncrePrefs { accent: EncreAccent; theme: EncreTheme }

export interface EncreFeuille {
  el: HTMLElement;
  corps: HTMLElement;
  fermer(): Promise<void>;
  readonly ferme: boolean;
}
export interface EncreFeuilleOptions {
  /** HTML du titre (échappé par toi : Encre.esc). */
  titre?: string;
  /** HTML du contenu ; un élément [data-fermer] ferme la feuille. */
  html?: string;
  /** 860 px au lieu de 520 px sur ordinateur. */
  large?: boolean;
  classe?: string;
  surFermer?: () => void;
}
export interface EncreMenuItem {
  icone?: string;
  texte: string;
  /** Raccourci clavier affiché à droite (souris seulement). */
  touche?: string;
  danger?: boolean;
  action?: () => void;
}
export interface EncreToastOptions {
  /** Affiche « Annuler » pendant 5 s ; une promesse rejetée affiche l'erreur. */
  annuler?: () => unknown | Promise<unknown>;
  erreur?: boolean;
  apres?: () => void;
  /** En millisecondes (2,6 s, 4,5 s pour une erreur, 5 s avec « Annuler »). */
  duree?: number;
}
export interface EncreRaccourci {
  titre: string;
  sous?: string;
  icone?: string;
  /** Mots en plus pour la recherche (sans accents ni majuscules). */
  mots?: string;
  /** « #page » ou adresse du site ; sinon action. */
  href?: string;
  action?: () => void;
  /** Pour un résultat de chercher() : le groupe où le ranger. */
  groupe?: string;
  iconeGroupe?: string;
}

export interface Encre {
  version: string;
  /** Adresse du fichier d'icônes ("" si les symboles sont collés dans la page). */
  sprite: string;
  apparence: {
    ACCENTS: EncreAccent[];
    THEMES: EncreTheme[];
    defaut: EncrePrefs;
    prefs: EncrePrefs | null;
    /** À fournir pour garder le choix sur le compte (côté serveur). */
    sauver: ((prefs: EncrePrefs, changement: Partial<EncrePrefs>) => Promise<void>) | null;
    choisir(changement: Partial<EncrePrefs>, options?: { message?: string }): Promise<void>;
    marquer(racine?: ParentNode): void;
  };
  nav: {
    /** data-page sur <body>, sinon le début de l'adresse après #. */
    page(): string;
    marquer(page?: string): void;
    aller(cible: string): Promise<void>;
    plus(bouton: HTMLElement): EncreFeuille | null;
  };
  recherche: {
    raccourcis: EncreRaccourci[];
    chercher: ((texte: string, options: { signal: AbortSignal }) => Promise<EncreRaccourci[]>) | null;
    placeholder: string;
    readonly active: boolean;
    ouvrir(texte?: string): unknown;
  };
  feuille(options: EncreFeuilleOptions): EncreFeuille;
  confirmer(message: string, options?: { ok?: string; danger?: boolean; titre?: string; detail?: string }): Promise<boolean>;
  demander(titre: string, options?: { label?: string; valeur?: string; placeholder?: string; ok?: string }): Promise<string | null>;
  /** Menu flottant à la souris, feuille du bas au doigt ; null = séparateur. */
  menu(ancre: HTMLElement, elements: (EncreMenuItem | null)[], options?: { titre?: string }): unknown;
  toast(message: string, options?: EncreToastOptions): { fermer(): void };
  toastErr(erreur: unknown): { fermer(): void };
  /** Grise le bouton et montre une roue jusqu'à la fin du travail. */
  occupe<T>(bouton: HTMLElement | null, travail: () => Promise<T>): Promise<T | undefined>;
  copier(texte: string, bouton?: HTMLElement): Promise<void>;
  animerEntree(conteneur: Element | null): void;
  appuiLong(racine: Element, selecteur: string, surAppui: (el: Element) => void, options?: { delai?: number }): void;
  ouvrirBulle(bouton: HTMLElement): void;
  fermerBulle(): void;
  /** Explications des bulles « ? » par clé (data-q) : { t, d, k?, pre? }. */
  bulles: Record<string, { t: string; d: string; k?: string; pre?: string }>;
  /** HTML d'une icône du jeu : Encre.ic("home", "s18"). */
  ic(nom: string, classes?: string): string;
  esc(texte: unknown): string;
  vibrer(ms?: number): void;
  ecranOrdi(): boolean;
  ecranLarge(): boolean;
  pointeurFin(): boolean;
  $(selecteur: string, racine?: ParentNode): Element | null;
  $$(selecteur: string, racine?: ParentNode): Element[];
  Couches: { readonly ouvertes: number; fermer(): Promise<void>; fermerTout(): Promise<void> };
  demarrer(): void;
}

declare global {
  interface Window { Encre: Encre }
}
""")

# ============================================================ les fiches
SPRITE = (DOSSIER / "icones.svg").read_text(encoding="utf-8")
SYMBOLES = dict(re.findall(r'(<symbol id="i-([a-z0-9]+)"[^>]*>.*?</symbol>)', SPRITE, re.S)[i][::-1]
                for i in range(len(re.findall(r'<symbol id="i-', SPRITE))))
assert len(SYMBOLES) == 77, len(SYMBOLES)
BASE_ICONES = ["x", "check", "alert", "search", "zap", "arrow", "dot", "chev"]


def icones(html):
    def svg(m):
        nom, *classes = m.group(1).split()
        assert nom in SYMBOLES, nom
        return f'<svg class="{" ".join(["i", *classes])}" aria-hidden="true"><use href="#i-{nom}"/></svg>'
    return re.sub(r"\{\{i:([^}]+)\}\}", svg, html)


def sprite(noms):
    noms = [n for n in dict.fromkeys(noms) if n in SYMBOLES]
    return ('<svg class="sprite" aria-hidden="true" style="position:absolute;width:0;height:0;overflow:hidden">\n'
            + "\n".join(SYMBOLES[n] for n in noms) + "\n</svg>")


CSS_APERCU = """  html { scrollbar-gutter: auto; }
  body { min-height: 0; padding: 16px; }
"""
CSS_STATIQUE = """  /* Pièces flottantes montrées à leur place, dans le cours de la page. */
  .statique { position: relative; inset: auto; transform: none; animation: none; z-index: auto; margin-left: auto; margin-right: auto; }
"""
# Liens « #page » : on allume l'onglet au lieu de changer l'adresse de l'aperçu.
JS_LIENS = """  const aller = (page) => { document.body.dataset.page = page; Encre.nav.marquer(); };
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[href^='#']");
    if (!a) return;
    e.preventDefault();
    Encre.Couches.fermerTout().then(() => aller(a.getAttribute("href").slice(1)));
  }, true);
"""
JS_RACCOURCIS = """  Encre.recherche.raccourcis = [
    { titre: "Accueil", sous: "Ouvrir la page", icone: "home", action: () => aller("accueil") },
    { titre: "Liste", sous: "520 éléments", icone: "list", action: () => aller("liste") },
    { titre: "Réglages", sous: "Couleur d'accent, thème", icone: "gear", mots: "couleur theme apparence", action: () => aller("reglages") },
    { titre: "Changer de thème", sous: "Automatique, clair, sombre", icone: "moon", mots: "sombre clair nuit", action: () => Encre.toast("Thème : à brancher sur ton site") },
  ];
"""

BRIQUES = []


def brique(nom, groupe, hauteur, sous_titre, lisezmoi, html, css="", js="", page=None, icones_en_plus=()):
    BRIQUES.append(dict(nom=nom, groupe=groupe, hauteur=hauteur, sous_titre=sous_titre, lisezmoi=lisezmoi.strip() + "\n",
                        html=html.strip("\n"), css=css, js=js, page=page, icones=list(icones_en_plus)))


# ------------------------------------------------------------ Navigation
MUR_CSS = """  .mur { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
  .mur div { height: 92px; border-radius: var(--r-lg); padding: 10px; display: flex; align-items: flex-end; color: var(--on-img); font: 400 17px/1.1 var(--f-title); position: relative; overflow: hidden; isolation: isolate; }
  .mur div::after { content: ""; position: absolute; inset: 0; z-index: -1; background: linear-gradient(180deg, transparent 35%, var(--verre-img)); }
  .m1 { background: linear-gradient(135deg, var(--accent-lavande), var(--accent-corail)); }
  .m2 { background: linear-gradient(135deg, var(--accent-menthe), var(--accent-lavande)); }
  .m3 { background: linear-gradient(135deg, var(--accent-ambre), var(--accent-corail)); }
  .m4 { background: linear-gradient(135deg, var(--accent-or), var(--accent-menthe)); }
  .m5 { background: linear-gradient(135deg, var(--accent-corail), var(--accent-or)); }
  .m6 { background: linear-gradient(135deg, var(--prog), var(--accent-menthe)); }
"""
brique("BarreFlottante", "Navigation", 320, "Verre flouté, au-dessus du contenu",
       """
# BarreFlottante

La barre d'onglets du téléphone : une pilule en verre flouté qui flotte au-dessus du contenu, à 12 px des côtés et 14 px du bas.

- **Ce que tu fournis** : `<nav class="tabbar">` avec quatre liens `.tab[data-page]` au plus (`<span class="ti">` + icône `s22`, puis le mot), et un bouton « Plus » `data-encre-plus="<id>"` qui ouvre le `<template id="<id>">` en feuille. Place-la après `.app`, hors du défilement.
- **Onglet actif** : `Encre.nav.marquer()` pose `.on` d'après `data-page` sur `<body>` (ou `#page` dans l'adresse) : texte `accent` et pilule `--acc-dim` derrière l'icône. « Plus » s'allume pour une page qui n'a pas d'onglet.
- **Verre** : fond `glass`, bord `line2`, ombre `sh-tab`, `backdrop-filter: blur(16px) saturate(1.5)`. Haute de `tab-h`, coins de 26 px.
- **Écrans** : 520 px de large et centrée dès 640 px ; remplacée par le menu de gauche dès 1000 px. Elle s'efface quand une feuille est ouverte (`body.overlay-ouvert`) ou pendant une sélection (`body.mode-sel`).
- **À faire** : réserver le bas des pages (`.pages` le fait : `tab-h` + 52 px). **À éviter** : plus de cinq onglets, des onglets sans mot, une barre collée au bord.
""",
       """
<div class="mur" aria-hidden="true">
  <div class="m1">Lavande</div><div class="m2">Menthe</div><div class="m3">Ambre</div><div class="m4">Or</div>
  <div class="m5">Corail</div><div class="m6">Verre</div><div class="m1">Flou</div><div class="m2">Accent</div>
  <div class="m3">Encre</div><div class="m4">Barre</div><div class="m5">Onglets</div><div class="m6">Plus</div>
</div>
<nav class="tabbar" aria-label="Navigation">
  <a class="tab" href="#accueil" data-page="accueil"><span class="ti">{{i:home s22}}</span>Accueil</a>
  <a class="tab" href="#liste" data-page="liste"><span class="ti">{{i:list s22}}</span>Liste</a>
  <a class="tab" href="#stats" data-page="stats"><span class="ti">{{i:chart s22}}</span>Stats</a>
  <a class="tab" href="#reglages" data-page="reglages"><span class="ti">{{i:gear s22}}</span>Réglages</a>
  <button class="tab" type="button" data-encre-plus="encre-plus" aria-haspopup="dialog"><span class="ti">{{i:dots s22}}</span>Plus</button>
</nav>
<template id="encre-plus">
  <div class="q-tuiles plus-t">
    <a class="qt" href="#aide">{{i:help s22}}Aide</a>
    <a class="qt" href="#compte">{{i:user s22}}Compte</a>
    <a class="qt" href="#sauvegarde">{{i:download s22}}Sauvegarde</a>
    <a class="qt" href="#couleurs">{{i:palette s22}}Couleurs</a>
  </div>
</template>
""",
       css=MUR_CSS + """  body { padding: 16px 16px 0; }
  @media (min-width: 1000px) { html .tabbar { display: flex !important; } }
""",
       js=JS_LIENS, page="accueil")

brique("MenuGauche", "Navigation", 500, "Ordinateur, 1000 px et plus",
       """
# MenuGauche

Le menu de gauche de l'ordinateur (1000 px et plus) : il remplace la barre du haut et la barre flottante.

- **Ce que tu fournis** : `<aside class="side">` en premier enfant de `.app`, avec le nom du site (`.brand` > `.wm`), le bouton de recherche `.side-search[data-encre-recherche]`, les pages en `.side-it[data-page]` (icône, `.nom`, compteur `.n`), un titre de groupe `.side-lbl`, des listes `.side-listes` (pastille `.dot`, `.dot.sys` en accent, `.dot.ordo` en `prog`) et le pied `.side-foot` > `.side-compte`.
- **Mesures** : largeur `side-w`, fond `surface`, trait `line` à droite, collé en haut (`position: sticky`).
- **Page active** : `.side-it.on` (fond `pop`, liseré `line2`, icône en `accent`), posé par `Encre.nav.marquer()`.
- **À éviter** : plus d'une douzaine d'entrées ; une entrée sans icône.
""",
       """
<aside class="side" aria-label="Menu principal">
  <div class="ligne">
    <a class="brand" href="#accueil"><span class="wm">mon<b>site</b></span></a>
    <span class="ver" title="Version du site">2.4</span>
  </div>
  <button class="side-search" type="button" data-encre-recherche>{{i:search s18}}Rechercher…<span class="kbd">Ctrl K</span></button>
  <nav aria-label="Pages">
    <a class="side-it" href="#accueil" data-page="accueil">{{i:home}}<span class="nom">Accueil</span></a>
    <a class="side-it" href="#liste" data-page="liste">{{i:list}}<span class="nom">Liste</span><span class="n">520</span></a>
    <a class="side-it" href="#decouvrir" data-page="decouvrir">{{i:compass}}<span class="nom">Découvrir</span></a>
    <a class="side-it" href="#stats" data-page="stats">{{i:chart}}<span class="nom">Statistiques</span></a>
  </nav>
  <div class="side-lbl">Mes listes<button type="button" aria-label="Nouvelle liste">{{i:plus s16}}</button></div>
  <div class="side-listes">
    <a class="side-it" href="#a-faire" data-page="a-faire"><span class="dot sys"></span><span class="nom">À faire</span><span class="n">210</span></a>
    <a class="side-it" href="#ordre" data-page="ordre"><span class="dot ordo"></span><span class="nom">Dans l'ordre</span><span class="n">12</span></a>
    <a class="side-it" href="#soirees" data-page="soirees"><span class="dot"></span><span class="nom">Soirées pop-corn</span><span class="n">8</span></a>
  </div>
  <div class="side-foot">
    <div class="side-compte"><span class="av" aria-hidden="true">N</span><span>noe@exemple.fr</span>
      <button type="button" class="ib form-deco" aria-label="Se déconnecter">{{i:logout s18}}</button></div>
  </div>
</aside>
""",
       css="""  html .side { display: flex !important; flex-direction: column; position: relative; top: auto; height: 468px; width: var(--side-w); max-width: 100%; overflow-y: auto; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg); padding: 18px 14px 14px; }
""",
       js=JS_LIENS + JS_RACCOURCIS, page="accueil", icones_en_plus=["home", "list", "gear", "moon"])

TOP = """<header class="top{cls}">
    <a class="brand" href="#accueil"><span class="wm">mon<b>site</b></span></a>
    <span class="esp"></span>
    <button class="ib" type="button" data-theme-suivant aria-label="Changer de thème">{{{{i:moon}}}}</button>
    <button class="ib" type="button" data-encre-recherche aria-label="Rechercher">{{{{i:search}}}}</button>
  </header>"""
brique("BarreHaut", "Navigation", 330, "Téléphone et tablette, au-dessus de la page",
       """
# BarreHaut

La barre du haut du téléphone et de la tablette : le nom du site à gauche, deux ou trois boutons-icônes à droite, sur un fond `bg` à 86 % flouté.

- **Ce que tu fournis** : `<header class="top">` en premier enfant de `.main` : `.brand` > `.wm` (le nom, seconde moitié en `<b>`), `<span class="esp">` pour pousser le reste à droite, puis des `.ib` (40 × 40, icône seule, avec `aria-label`).
- **Défilement** : `bundle.js` ajoute `.ombre` (un trait `line` dessous) dès qu'on défile.
- **Bandeau** : juste sous la barre, `.bandeau` signale un état qui dure (« Tu vois le site en tant que Léa ») : fond `--acc-dim`, trait `--acc-line`, icône en `accent`, un bouton à droite.
- **Écrans** : cachée dès 1000 px (le menu de gauche prend le relais), sauf sur une page simple (`body.page-simple`).
- **À éviter** : un titre de page dans la barre (il va dans `.page-h`) ; plus de trois boutons.
""",
       """
<div class="ecran">
  <div class="lbl-mono cap">Au repos</div>
  """ + TOP.format(cls="") + """
  <div class="page-h"><h1 class="page-t">Bonjour</h1></div>
</div>
<div class="ecran">
  <div class="lbl-mono cap">Après défilement</div>
  """ + TOP.format(cls=" ombre") + """
  <div class="bandeau">{{i:eye s18}}<span>Tu vois le site en tant que <b>lea@exemple.fr</b></span><span class="esp"></span><button type="button" class="btn xs">Revenir</button></div>
</div>
""",
       css="""  body { display: grid; gap: 14px; }
  .ecran { border: 1px solid var(--line); border-radius: var(--r-lg); overflow: hidden; background: var(--bg); }
  .cap { padding: 12px 16px 4px; }
  html .top { display: flex !important; position: relative; }
  .ecran .page-h { padding: 0 16px 6px; }
""",
       js=JS_LIENS + JS_RACCOURCIS + """  document.addEventListener("click", (e) => {
    if (!e.target.closest("[data-theme-suivant]")) return;
    const suite = { auto: "clair", clair: "sombre", sombre: "auto" }[Encre.apparence.prefs.theme];
    Encre.apparence.choisir({ theme: suite }, { message: { auto: "Thème automatique", clair: "Thème clair", sombre: "Thème sombre" }[suite] });
  });
""", page="accueil", icones_en_plus=["home", "list", "gear", "moon"])

FEUILLE_STATIQUE_CSS = """  .feuille.statique { left: auto; right: auto; top: auto; bottom: auto; width: auto; max-width: 520px; max-height: none; overflow: visible;
    border: 1px solid var(--line2); border-radius: 24px; padding: 8px 16px 22px; box-shadow: var(--sh-feuille); }
  .feuille.statique .grab { display: block; }
"""
brique("FeuillePlus", "Navigation", 400, "Ce qui ne tient pas dans la barre",
       """
# FeuillePlus

La feuille « Plus » : ce qui ne tient pas dans la barre flottante, en quatre grandes tuiles puis en lignes.

- **Ce que tu fournis** : un `<template id="encre-plus">` avec `.q-tuiles.plus-t` (quatre `a.qt` : icône `s22` + un mot) puis, si besoin, une `.liste-r` de `.li`. Le bouton `data-encre-plus="encre-plus"` de la barre l'ouvre.
- **La feuille** : `Encre.feuille({ titre, html })` monte du bas sur téléphone (coins de 24 px, ombre `sh-feuille`, poignée `.grab`) et devient une fenêtre centrée de 520 px dès 760 px. Voile `scrim` derrière ; elle se ferme en touchant le voile, en tirant vers le bas, avec Échap ou avec le bouton retour du téléphone.
- **Tuile active** : `.qt.on` (fond `--acc-dim`, trait `--acc-line`, icône en `accent`).
- **À éviter** : plus de huit tuiles ; une feuille qui contient une autre feuille.
""",
       """
<div class="feuille statique">
  <div class="grab" aria-hidden="true"></div>
  <div class="feuille-t"><span class="tt">Plus</span><span class="esp"></span><button type="button" class="ib" aria-label="Fermer">{{i:x}}</button></div>
  <div class="feuille-c">
    <div class="q-tuiles plus-t">
      <a class="qt on" href="#reglages">{{i:gear s22}}Réglages</a>
      <a class="qt" href="#aide">{{i:help s22}}Aide</a>
      <a class="qt" href="#sauvegarde">{{i:download s22}}Sauvegarde</a>
      <a class="qt" href="#couleurs">{{i:palette s22}}Couleurs</a>
    </div>
    <div class="liste-r">
      <a class="li" href="#comptes"><span class="li-ic">{{i:users}}</span><span class="tx">Comptes et profils<small>Accès, « voir en tant que »</small></span>{{i:chev s18 muted}}</a>
      <button type="button" class="li"><span class="li-ic">{{i:logout}}</span><span class="tx">Se déconnecter<small>noe@exemple.fr</small></span></button>
    </div>
  </div>
</div>
<div class="ligne vrai"><button class="btn" type="button" data-encre-plus="encre-plus">{{i:dots s18}}Ouvrir la vraie feuille</button></div>
<template id="encre-plus">
  <div class="q-tuiles plus-t">
    <a class="qt" href="#reglages">{{i:gear s22}}Réglages</a>
    <a class="qt" href="#aide">{{i:help s22}}Aide</a>
    <a class="qt" href="#sauvegarde">{{i:download s22}}Sauvegarde</a>
    <a class="qt" href="#couleurs">{{i:palette s22}}Couleurs</a>
  </div>
</template>
""",
       css=CSS_STATIQUE + FEUILLE_STATIQUE_CSS + """  .vrai { justify-content: center; margin-top: 16px; }
""",
       js=JS_LIENS)

brique("Recherche", "Navigation", 450, "Ctrl K, ⌘ K ou « / »",
       """
# Recherche

La recherche rapide : Ctrl K (⌘ K), « / » hors d'un champ, ou un bouton `[data-encre-recherche]` ouvre une liste de raccourcis et de résultats.

- **Ce que tu fournis** : `Encre.recherche.raccourcis = [{ titre, sous, icone, mots, href | action }]` (les pages et réglages du site), et si le site cherche dans ses données, `Encre.recherche.chercher = async (texte, { signal }) => [{ groupe, iconeGroupe, titre, sous, icone, href | action }]`. Sans raccourci ni fonction, la recherche reste éteinte.
- **Rendu** : bandeau en haut du téléphone, fenêtre de 640 px à 12 % du haut dès 760 px ; voile `scrim` flouté de 3 px ; groupes en `.pal-g` (`libelle`), lignes `.pal-it` (pastille `.ico`, titre en gras, sous-ligne `muted`), la ligne choisie en `card`.
- **Clavier** : ↑ ↓ pour choisir, Entrée pour ouvrir, Échap pour fermer ; la saisie attend 180 ms et ne tient pas compte des accents.
- **À éviter** : plus de huit raccourcis à vide ; une recherche qui recharge la page.
""",
       """
<div class="palette statique">
  <label class="champ">{{i:search s18}}<input type="search" value="ré" readonly tabindex="-1" aria-label="Rechercher"><span class="kbd">Échap</span></label>
  <div class="res-p">
    <div class="pal-g">{{i:list s16}}Résultats</div>
    <button type="button" class="pal-it on"><span class="ico">{{i:clock s18}}</span><span class="tx"><b>Récemment ajoutés</b><span>12 éléments cette semaine</span></span></button>
    <button type="button" class="pal-it"><span class="ico">{{i:cal s18}}</span><span class="tx"><b>Résumé de la semaine</b><span>Chaque dimanche soir</span></span></button>
    <div class="pal-g">{{i:zap s16}}Raccourcis</div>
    <button type="button" class="pal-it"><span class="ico">{{i:gear s18}}</span><span class="tx"><b>Réglages</b><span>Couleur d'accent, thème</span></span></button>
  </div>
  <div class="pal-pied"><span><span class="kbd">↑</span> <span class="kbd">↓</span> choisir</span><span><span class="kbd">Entrée</span> ouvrir</span><span><span class="kbd">Échap</span> fermer</span></div>
</div>
<div class="ligne vrai"><button class="btn" type="button" data-encre-recherche>{{i:search s18}}Ouvrir la recherche<span class="kbd">Ctrl K</span></button></div>
""",
       css=CSS_STATIQUE + """  .palette.statique { left: auto; right: auto; top: auto; width: auto; max-width: 640px; max-height: none; border: 1px solid var(--line2); border-radius: 18px; padding: 12px; }
  .palette.statique .pal-pied { display: flex; flex-wrap: wrap; }
  .vrai { justify-content: center; margin-top: 16px; }
""",
       js=JS_LIENS + JS_RACCOURCIS + """  Encre.recherche.chercher = async (texte) => ["Récemment ajoutés", "Résumé de la semaine", "Reprendre la lecture"]
    .filter((t) => t.toLowerCase().includes(texte.toLowerCase()))
    .map((t) => ({ groupe: "Résultats", iconeGroupe: "list", titre: t, sous: "Exemple", icone: "clock", action: () => Encre.toast(t) }));
""", icones_en_plus=["home", "list", "gear", "moon", "clock"])

# --------------------------------------------------------------- Actions
brique("Bouton", "Actions", 270, "Principal, normal, discret, danger",
       """
# Bouton

Les boutons : un seul principal par écran (`accent`), les autres en `card` ou transparents, et le rouge pour ce qu'on ne peut pas défaire.

- **Classes** : `.btn` (44 px, `r-btn`, `bouton`) ; `.pri` (fond `accent`, texte `ink`), `.gh` (transparent), `.dn` (texte `danger`), `.dn.plein` (fond `danger`, pour une confirmation), `.prg` / `.okb` (teintes « en cours » / « réussi ») ; tailles `.sm` (34 px), `.xs` (28 px), `.w` (pleine largeur), `.ico` (carré), `.deux` (deux lignes, `.sub` dessous).
- **Bouton-icône** : `.ib` (40 × 40, coins de 12 px, fond `surface`), `.ib.on` (icône en `accent`), `.ib.verre` sur une image (`verre-img`, `img-trait2`, `on-img`). Toujours un `aria-label`.
- **Liens** : `.lien` (accent, gras, 13 px) et `.lien-r` (« Tout voir › » au bout d'un titre de section).
- **Pendant l'envoi** : `Encre.occupe(bouton, async () => …)` grise le bouton et montre une roue : pas de double envoi.
- **Texte** : un verbe à l'infinitif (« Enregistrer », « Retirer », « Tout effacer »), jamais « OK ». Le bouton s'enfonce à l'appui (`scale(.97)`).
""",
       """
<div class="pile">
  <div class="ligne">
    <button type="button" class="btn pri">{{i:check s18}}Enregistrer</button>
    <button type="button" class="btn">Annuler</button>
    <button type="button" class="btn gh">Plus tard</button>
    <button type="button" class="btn dn">{{i:trash s18}}Supprimer</button>
  </div>
  <div class="ligne">
    <button type="button" class="btn sm pri">Petit</button>
    <button type="button" class="btn sm">Petit</button>
    <button type="button" class="btn xs">Mini</button>
    <button type="button" class="btn ico" aria-label="Ajouter">{{i:plus}}</button>
    <button type="button" class="btn sm prg">En cours</button>
    <button type="button" class="btn sm okb">Terminé</button>
  </div>
  <div class="ligne">
    <button type="button" class="btn pri deux" data-occupe><span>{{i:upload s18}}Envoyer</span><span class="sub">touche : il se grise le temps d'envoyer</span></button>
    <button type="button" class="btn dn plein">Tout effacer</button>
    <button type="button" class="btn" disabled>Indisponible</button>
  </div>
  <div class="ligne">
    <button type="button" class="ib" aria-label="Partager">{{i:share}}</button>
    <button type="button" class="ib on" aria-label="Favori">{{i:heartfill}}</button>
    <span class="image" aria-hidden="true"><button type="button" class="ib verre" tabindex="-1">{{i:heart}}</button><button type="button" class="ib verre" tabindex="-1">{{i:share}}</button></span>
    <a class="lien" href="#exemple">Un lien{{i:arrow s16}}</a>
    <a class="lien-r" href="#exemple">Tout voir{{i:chev s16}}</a>
  </div>
</div>
""",
       css="""  .pile { display: grid; gap: 12px; }
  .image { display: inline-flex; gap: 8px; padding: 10px; border-radius: var(--r-lg); background: linear-gradient(135deg, var(--accent-menthe), var(--accent-lavande)); }
""",
       js="""  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-occupe]");
    if (b) Encre.occupe(b, () => new Promise((r) => setTimeout(r, 1400))).then(() => Encre.toast("Envoyé"));
    if (e.target.closest("a[href='#exemple']")) e.preventDefault();
  });
""")

brique("PucesSegments", "Actions", 130, "Filtrer, choisir une vue",
       """
# PucesSegments

Les puces filtrent une liste, le segment choisit une vue ou une période : un seul choix allumé à la fois.

- **Puces** : `.chips` (une rangée qui défile de côté sans barre) > `button.chip` (pilule de 32 px, fond `surface`, trait `line2`) ; `.chip.on` = fond `accent`, texte `ink`. Compteur `.n` en `chiffre-mono`, pastille ronde `.pastille` pour un nombre de filtres actifs.
- **Segment** : `.seg` (rail `creux`, trait `line`, coins de 12 px) > `button` ; `button.on` ressort en `pop` avec un liseré `line2`. `.seg.ico` pour des icônes seules (avec `aria-label`).
- **Ce que tu fournis** : le changement de `.on` (et `aria-pressed`) au clic ; `data-encre-theme` branche tout seul le choix du thème.
- **À éviter** : plus de quatre choix dans un segment ; des puces pour une action (c'est un bouton).
""",
       """
<div class="chips" role="group" aria-label="Filtre">
  <button type="button" class="chip on" data-un>Tout <span class="n">520</span></button>
  <button type="button" class="chip" data-un>Films <span class="n">377</span></button>
  <button type="button" class="chip" data-un>Séries <span class="n">143</span></button>
  <button type="button" class="chip">{{i:filter s16}}Filtres <span class="pastille">2</span></button>
</div>
<div class="ligne" style="margin-top: 14px; flex-wrap: nowrap">
  <div class="seg" role="group" aria-label="Période" style="flex: 1">
    <button type="button" class="on" data-un>Jour</button><button type="button" data-un>Semaine</button><button type="button" data-un>Mois</button>
  </div>
  <div class="seg ico" role="group" aria-label="Affichage">
    <button type="button" class="on" data-un aria-label="Grille">{{i:grid s18}}</button><button type="button" data-un aria-label="Lignes">{{i:rows s18}}</button>
  </div>
</div>
""",
       js="""  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-un]");
    if (b) [...b.parentElement.querySelectorAll("[data-un]")].forEach((x) => x.classList.toggle("on", x === b));
  });
""")

# ---------------------------------------------------------------- Saisie
brique("Champs", "Saisie", 480, "Recherche, texte, choix, note",
       """
# Champs

Les champs de saisie : fond `card`, trait `line`, coins de 12 px, et un halo `--acc-dim` avec un trait `--acc-line` quand on écrit.

- **Classes** : `.champ` (champ avec icône et touche `.kbd`, 42 px), `.input` (texte, 44 px), `.select` (liste, flèche dessinée), `textarea.input` ; `.lbl` au-dessus (13 px, `soft`) ; `.form` empile avec 12 px ; `.ligne` met un champ et un bouton côte à côte ; `.statut.ok` / `.statut.err` pour le retour sous le formulaire.
- **Taille** : le texte tapé fait 16 px (`saisie`), jamais moins : sinon l'iPhone zoome.
- **Ce que tu fournis** : un `<label>` relié à chaque champ (ou `aria-label`), un `placeholder` qui donne un exemple (« Ex. : Soirées pop-corn »), l'enregistrement.
- **À éviter** : un champ sans libellé ; un message d'erreur seulement en rouge (écris ce qui ne va pas).
""",
       """
<div class="form">
  <label class="champ">{{i:search s18}}<input type="search" placeholder="Chercher un titre…" aria-label="Chercher"><span class="kbd">Ctrl K</span></label>
  <div><label class="lbl" for="nom">Nom de la liste</label><input class="input" id="nom" placeholder="Ex. : Soirées pop-corn"></div>
  <div><label class="lbl" for="rythme">Rappel</label><select class="select" id="rythme"><option>Tous les jours</option><option>Chaque semaine</option></select></div>
  <div><label class="lbl" for="note">Note</label><textarea class="input" id="note" rows="2" placeholder="Quelques mots…"></textarea></div>
  <div class="ligne"><input class="input" aria-label="Adresse e-mail" placeholder="ami@exemple.fr"><button type="button" class="btn pri">Inviter</button></div>
  <p class="statut ok">Enregistré à 14 h 02</p>
  <p class="statut err">Cette adresse est déjà invitée.</p>
</div>
""")

brique("Interrupteurs", "Saisie", 310, "Réglages qui s'enregistrent seuls",
       """
# Interrupteurs

Interrupteurs et coches : un réglage qui s'enregistre dès qu'on le touche, une chose faite ou pas.

- **Interrupteur** : `<input type="checkbox" class="sw">` (42 × 25, rail `line2`, rond `blanc` avec `sh-sw` ; allumé en `accent`). Dans une ligne de réglage `.reg-l` : `.tx` > `b` (titre, `bouton`) + `span` (explication, `muted`), l'interrupteur à droite.
- **Coche** : `button.ck` (rond de 30 px) ; `.ck.on` = fond `ok`, coche en `ok-ink` (une chose vue, terminée) ; `.ck.sq` = carrée, cochée en `accent` (une sélection). Toujours `aria-pressed` et `aria-label`.
- **Ce que tu fournis** : l'enregistrement au changement, puis `Encre.toast("Enregistré")` ; en cas d'échec, remets l'état d'avant et affiche l'erreur.
- **À éviter** : un bouton « Enregistrer » sous des interrupteurs.
""",
       """
<div class="carte" style="padding: 4px 16px">
  <div class="reg-l"><div class="tx"><b>Notifications</b><span>Un message le jour de la sortie</span></div><input type="checkbox" class="sw" checked aria-label="Notifications"></div>
  <div class="reg-l"><div class="tx"><b>Mode compact</b><span>Moins d'espace entre les lignes</span></div><input type="checkbox" class="sw" aria-label="Mode compact"></div>
  <div class="reg-l"><div class="tx"><b>Sauvegarde automatique</b><span>Réglée par le serveur</span></div><input type="checkbox" class="sw" checked disabled aria-label="Sauvegarde automatique"></div>
  <div class="reg-l"><div class="tx"><b>Coches</b><span>Vu, pas vu, sélectionné</span></div>
    <button type="button" class="ck on" data-ck aria-pressed="true" aria-label="Vu">{{i:check s16}}</button>
    <button type="button" class="ck" data-ck aria-pressed="false" aria-label="Pas vu">{{i:check s16}}</button>
    <button type="button" class="ck sq on" data-ck aria-pressed="true" aria-label="Sélectionné">{{i:check s16}}</button>
  </div>
</div>
""",
       js="""  document.addEventListener("click", (e) => {
    const ck = e.target.closest("[data-ck]");
    if (!ck) return;
    const on = !ck.classList.contains("on");
    ck.classList.toggle("on", on);
    ck.setAttribute("aria-pressed", String(on));
  });
  document.addEventListener("change", (e) => { if (e.target.matches(".sw")) Encre.toast("Enregistré"); });
""")

brique("Pastilles", "Saisie", 250, "Couleur d'accent et thème",
       """
# Pastilles

Le choix de l'apparence : cinq pastilles pour la couleur d'accent, un segment pour le thème. Touche une pastille : tout l'aperçu change de couleur.

- **Ce que tu fournis** : `.pastilles[data-encre-accent]` > `button.past[data-v="or|ambre|corail|menthe|lavande"]` (un `<i>` rond de 44 px + le nom), et `.seg[data-encre-theme]` > `button[data-v="auto|clair|sombre"]`. `bundle.js` allume le bon choix, l'applique (`data-accent`, `data-theme` sur `<html>`), le garde sur l'appareil et affiche « Enregistré ».
- **Sur le compte** : donne `Encre.apparence.sauver = async (prefs) => …` ; une erreur remet le choix d'avant. Le serveur pose alors lui-même `data-accent`, `data-theme` et `data-encre-prefs` sur `<html>`.
- **Clavier** : les pastilles forment un groupe radio (flèches gauche et droite).
- **À éviter** : proposer une couleur hors des cinq accents (ajoute plutôt `accent-<nom>` et `ink-<nom>` aux jetons).
""",
       """
<section class="carte" style="padding: 18px">
  <div class="reg-sec" style="margin-top: 0">
    <div class="lbl-mono">Couleur d'accent</div>
    <div class="pastilles" data-encre-accent role="radiogroup" aria-label="Couleur d'accent">
      <button type="button" class="past" data-v="or" role="radio"><i></i>Or</button>
      <button type="button" class="past" data-v="ambre" role="radio"><i></i>Ambre</button>
      <button type="button" class="past" data-v="corail" role="radio"><i></i>Corail</button>
      <button type="button" class="past" data-v="menthe" role="radio"><i></i>Menthe</button>
      <button type="button" class="past" data-v="lavande" role="radio"><i></i>Lavande</button>
    </div>
  </div>
  <div class="reg-sec">
    <div class="lbl-mono">Thème</div>
    <div class="seg" data-encre-theme role="group" aria-label="Thème">
      <button type="button" data-v="auto">{{i:refresh s16}}Automatique</button><button type="button" data-v="clair">{{i:sun s16}}Clair</button><button type="button" data-v="sombre">{{i:moon s16}}Sombre</button>
    </div>
  </div>
</section>
""")

# --------------------------------------------------------------- Contenu
brique("Cartes", "Contenu", 420, "En-têtes, cartes, blocs, pied de page",
       """
# Cartes

La mise en page du contenu : un en-tête de page, des en-têtes de section, des cartes et des blocs, un pied de page discret.

- **En-tête de page** : `.page-h` > `h1.page-t` (`titre-page`, compteur `.n` en `chiffre-mono`) + un segment ou un bouton à droite ; `.intro-p` dessous (14 px, `soft`, 68 caractères au plus).
- **Section** : `.sec-h` > `h2.sec-t` (`titre-section`, bulle `.q` possible) + `.lien-r` « Tout voir › » ; un mot mis en avant en `em` (couleur `accent`).
- **Carte** : `.carte` (fond `card`, trait `line`, `r-lg`, marge intérieure à choisir, 18 px d'habitude) ; `.bloc` (même allure, 14 px dedans) pour regrouper quelques briques. Pas d'ombre sur une carte.
- **Pied** : `.pied` centré en 12 px `muted` ; `.pied.dans-page` dans une page (sinon il réserve la place de la barre flottante).
- **À éviter** : une carte dans une carte ; une bordure de couleur sur un côté.
""",
       """
<div class="page-h"><h1 class="page-t">Bibliothèque <span class="n">520</span></h1>
  <div class="seg" role="group" aria-label="Vue"><button type="button" class="on">Grille</button><button type="button">Liste</button></div></div>
<p class="intro-p">Une phrase pour dire à quoi sert la page, en 14 px, jamais plus de deux lignes.</p>
<div class="sec-h"><h2 class="sec-t">Activité <em>récente</em> <button type="button" class="q" aria-label="Explication" data-t="Activité récente" data-d="Ce qui a changé ces sept derniers jours, du plus récent au plus ancien.">?</button></h2><a class="lien-r" href="#tout">Tout voir{{i:chev s16}}</a></div>
<div class="carte" style="padding: 18px">
  <div class="lbl-mono">Carte</div>
  <p class="soft" style="margin-top: 8px">Fond <code>card</code>, trait <code>line</code>, coins de 14 px : elle porte une section entière (un réglage, un résumé, un formulaire).</p>
</div>
<div class="bloc" style="margin-top: 12px"><div class="lbl-mono">Bloc</div><p class="soft petit" style="margin-top: 6px">Même allure, 14 px de marge intérieure : pour regrouper quelques briques.</p></div>
<footer class="pied dans-page"><span>Mon site · version 2.4</span><span>Mis à jour le 3 novembre</span></footer>
""",
       js="""  document.addEventListener("click", (e) => { if (e.target.closest("a[href='#tout']")) e.preventDefault(); });
""")

brique("Tuiles", "Contenu", 260, "Chiffres clés",
       """
# Tuiles

Les chiffres clés : un petit titre, une valeur en grand dans la police des titres, une ligne d'explication.

- **Classes** : `.tuiles` (2 colonnes, 4 dès 760 px) > `.tuile` (fond `card`, `r-lg`) : `.k` (titre 12,5 px `muted` avec icône `s16`), `.v` (valeur en `chiffre`, unité en `small`), `.s` (12 px `soft`).
- **Grande tuile** : `.tuile.big` prend toute la largeur sur téléphone et 2 × 2 cases dès 760 px (`chiffre-grand`) ; une répartition `.split` (`i.f` en `accent`, `i.s` en `prog`) et sa légende `.leg`.
- **Chiffres** : à la française, espace entre les milliers et avant l'unité (« 2 930 h », « 22 % »).
- **À éviter** : plus de deux couleurs dans une répartition ; une valeur sans unité ni explication.
""",
       """
<div class="tuiles">
  <div class="tuile big">
    <div class="k">{{i:clock s16}}Temps total</div>
    <div class="v">2 930 <small>h</small></div>
    <div class="s">soit 122 jours, d'après tout ce qui est enregistré</div>
    <div class="split" aria-hidden="true"><i class="f" style="width: 22%"></i><i class="s" style="width: 78%"></i></div>
    <div class="leg"><span><i class="f"></i>Films 22 %</span><span><i class="s"></i>Séries 78 %</span></div>
  </div>
  <div class="tuile"><div class="k">{{i:check s16}}Terminés</div><div class="v">377</div><div class="s">+12 ce mois-ci</div></div>
  <div class="tuile"><div class="k">{{i:play s16}}En cours</div><div class="v">8</div><div class="s">dont 3 cette semaine</div></div>
  <div class="tuile"><div class="k">{{i:bookmark s16}}À faire</div><div class="v">210</div><div class="s">la liste qui grandit</div></div>
  <div class="tuile"><div class="k">{{i:staron s16}}Favoris</div><div class="v">24</div><div class="s">les indispensables</div></div>
</div>
""")

brique("Listes", "Contenu", 280, "Lignes avec icône, sous-ligne et valeur",
       """
# Listes

Les listes en lignes : une icône dans une pastille, un titre, une sous-ligne, une valeur ou une flèche à droite.

- **Classes** : `.liste-r` (fond `card`, trait `line`, `r-lg`) > `.li` (54 px au moins, `ligne-liste`, trait `line` entre deux lignes) : `.li-ic` (32 px, fond `pop` ; `.li-ic.acc` en `--acc-dim` / `accent`), `.tx` > texte + `small` (12 px `muted`, coupé par « … »), `.v` (valeur `muted` à droite) ou une icône `chev`.
- **États** : `.li.on` (fond `--acc-dim`, l'élément ouvert), `.li.dn` (action qui supprime, en `danger`). Une ligne qui agit est un `button.li` ou un `a.li` (survol en `pop`).
- **Groupe** : un titre `.reg-g` (`libelle`) au-dessus de chaque liste.
- **À éviter** : deux lignes de texte dans le titre ; une flèche sur une ligne qui ne mène nulle part.
""",
       """
<div class="reg-g">Activité récente</div>
<div class="liste-r">
  <button type="button" class="li on"><span class="li-ic acc">{{i:check}}</span><span class="tx">Marqué comme terminé<small>Il y a 5 minutes · depuis ton téléphone</small></span><span class="v">14 h 02</span></button>
  <button type="button" class="li"><span class="li-ic">{{i:listplus}}</span><span class="tx">Ajouté à « Soirées pop-corn »<small>Hier soir</small></span><span class="v">21 h 47</span></button>
  <a class="li" href="#maj"><span class="li-ic">{{i:refresh}}</span><span class="tx">Site mis à jour en 2.4<small>Tout s'est bien passé</small></span>{{i:chev s18 muted}}</a>
  <button type="button" class="li dn"><span class="li-ic">{{i:trash}}</span><span class="tx">Vider l'historique<small>Demande une confirmation</small></span></button>
</div>
""",
       js="""  document.addEventListener("click", (e) => { if (e.target.closest("a[href='#maj']")) e.preventDefault(); });
""")

brique("Progression", "Contenu", 190, "Barres d'avancement et badges",
       """
# Progression

Les barres d'avancement et les petits badges d'état.

- **Barre** : `.pg` (4 px, rail `line2`) > `<i style="width: 64%">` en `prog` ; `.pg.ok` quand c'est fini (`ok`), `.pg.acc` pour l'accent, `.pg.epais` (6 px). Écris toujours la valeur à côté (« 12 / 18 épisodes »).
- **Badges** : `.badge` (pilule de 26 px, `libelle` en capitales, trait `line2`) pour un statut neutre (« Accès privé ») ; `.kbd` pour une touche du clavier.
- **Ce que tu fournis** : la largeur en pourcentage ; le texte qui dit la même chose (la couleur seule ne suffit pas).
""",
       """
<div class="pile">
  <div><div class="ligne entre"><span class="petit soft">Saison 2</span><span class="petit muted">12 / 18 épisodes</span></div><div class="pg"><i style="width: 64%"></i></div></div>
  <div><div class="ligne entre"><span class="petit soft">Saison 1</span><span class="petit muted">Terminée</span></div><div class="pg ok"><i style="width: 100%"></i></div></div>
  <div><div class="ligne entre"><span class="petit soft">Objectif de l'année</span><span class="petit muted">38 %</span></div><div class="pg acc epais"><i style="width: 38%"></i></div></div>
  <div class="ligne"><span class="badge">Accès privé</span><span class="badge">Version 2.4</span><span class="kbd">Échap</span><span class="kbd">Ctrl K</span></div>
</div>
""",
       css="""  .pile { display: grid; gap: 14px; }
  .entre { justify-content: space-between; margin-bottom: 6px; }
""")

brique("Vide", "Contenu", 400, "Rien à montrer, ou pas encore",
       """
# Vide

Ce qu'on montre quand une liste est vide, et pendant le chargement.

- **Vide** : `.vide` (centré, 34 px de marge) > une icône (34 px, couleur `line2`), `b` (ce qui se passe, 15 px `text`), `span` (ce qu'on peut faire, 13,5 px `muted`), puis un bouton `.btn.sm.pri` qui le fait.
- **Chargement** : des squelettes `.sk` qui scintillent (fond `card` → `pop`, coins `r-po`) : `.sk.ln` (une ligne de texte), `.sk.ln.t` (un titre), `.sk.sk-l` (une ligne de liste), `.sk-res` (une carte). Ils ont la forme de ce qui arrive.
- **Ton** : doux et utile (« Rien ici pour l'instant »), jamais « Erreur » pour une liste vide.
- **À éviter** : une roue qui tourne seule au milieu d'une page vide.
""",
       """
<div class="carte">
  <div class="vide">{{i:list}}<b>Rien ici pour l'instant</b><span>Ta première liste apparaîtra ici. Elle peut être rangée dans l'ordre ou au hasard.</span><button type="button" class="btn sm pri">{{i:plus s16}}Créer une liste</button></div>
</div>
<div class="sk ln t"></div><div class="sk sk-l"></div><div class="sk ln" style="width: 70%"></div>
""")

brique("ZoneSensible", "Contenu", 170, "Ce qu'on ne peut pas défaire",
       """
# ZoneSensible

La zone sensible : les actions qu'on ne peut pas défaire, rangées tout en bas d'un réglage, en rouge, et toujours confirmées.

- **Classes** : `.zone-d` (fond `--danger-dim`, trait `danger` mêlé à `line`, `r-lg`) > `h3` (`titre-section` en `danger`, icône `alert`), `p` (13,5 px `soft` : ce qui sera perdu et ce qui est gardé), `.btn.dn.sm` (« Tout effacer »).
- **Ce que tu fournis** : `await Encre.confirmer(message, { ok: "Tout effacer", danger: true, titre, detail })` avant d'agir ; une sauvegarde si possible.
- **À éviter** : plus d'une zone sensible par page ; un bouton sensible ailleurs qu'ici.
""",
       """
<div class="zone-d">
  <h3>{{i:alert s18}}Zone sensible</h3>
  <p>Efface tout l'historique. Une sauvegarde complète est faite juste avant.</p>
  <button type="button" class="btn dn sm" style="margin-top: 12px" data-danger>{{i:trash s16}}Tout effacer</button>
</div>
""",
       js="""  document.addEventListener("click", async (e) => {
    if (!e.target.closest("[data-danger]")) return;
    const ok = await Encre.confirmer("Tout ton historique sera effacé. Une sauvegarde complète est faite juste avant.", { ok: "Tout effacer", danger: true, titre: "Effacer l'historique ?", detail: "Cette action ne peut pas être annulée." });
    if (ok) Encre.toast("Exemple seulement : rien n'a été effacé");
  });
""")

brique("Copie", "Contenu", 210, "Copier, avertir, montrer une commande",
       """
# Copie

Trois briques pour le technique : une valeur à copier, un avertissement à lire, une commande à taper.

- **Copier** : `.copie` (fond `surface`, trait `line`, `r-md`) > `code` (12,5 px) + `.btn.sm` « Copier » ; `Encre.copier(texte, bouton)` copie et affiche « Copié » sur le bouton.
- **Avertir** : `.bandeau-c` (fond `warn` à 14 %, trait `warn`, icône `alert` en `warn`) : une phrase, ce qu'il faut faire maintenant.
- **Commande** : `pre.bloc-code` (DM Mono 12,5 px, fond `surface`), une commande par ligne.
- **À éviter** : un secret affiché sans avertissement ; une commande coupée en plein milieu (elle passe à la ligne toute seule).
""",
       """
<div class="copie"><code>cle-api-exemple-1234</code><button type="button" class="btn sm" data-copier>{{i:copy s16}}Copier</button></div>
<div class="bandeau-c" style="margin-top: 10px">{{i:alert s18}}<span>Copie cette clé maintenant : elle ne sera plus jamais affichée.</span></div>
<pre class="bloc-code">sudo bash /opt/mon-site/scripts/reset-admin-password.sh</pre>
""",
       js="""  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-copier]");
    if (b) Encre.copier(b.parentElement.querySelector("code").textContent, b);
  });
""")

brique("Aide", "Contenu", 310, "Questions et réponses",
       """
# Aide

La page d'aide en questions-réponses, rangées par thème.

- **Classes** : `.faq` (860 px au plus) > `.faq-g` (titre de groupe en `libelle`, avec icône) puis `details` (carte `card`, `r-lg`) > `summary` (icône, la question en 14,5 px gras, `svg.chev` qui tourne à l'ouverture) + `.rep` (la réponse en 14 px `soft`, alignée sous la question ; `pre` pour une commande).
- **Recherche** : un `.champ` au-dessus (`.aide-cherche`) qui filtre les questions.
- **Ton** : la question telle qu'on la poserait (« Pourquoi le site devient clair le matin ? »), la réponse en deux ou trois phrases, au tutoiement.
""",
       """
<div class="faq">
  <div class="faq-g">{{i:palette s16}}Apparence</div>
  <details open><summary>{{i:help}}Comment changer la couleur du site ?{{i:chev s18 chev}}</summary>
    <div class="rep"><p>Dans Réglages → Apparence, touche une des cinq pastilles. Le changement est immédiat et enregistré.</p></div></details>
  <details><summary>{{i:help}}Pourquoi le site devient clair le matin ?{{i:chev s18 chev}}</summary>
    <div class="rep"><p>Le thème « Automatique » suit ton téléphone. Choisis « Sombre » pour le garder sombre tout le temps.</p></div></details>
  <div class="faq-g">{{i:zap s16}}Navigation</div>
  <details><summary>{{i:help}}Le bouton retour du téléphone ferme le site ?{{i:chev s18 chev}}</summary>
    <div class="rep"><p>Non : il referme d'abord la feuille, le menu ou la fenêtre ouverte.</p></div></details>
</div>
""",
       css="""  .faq-g:first-child { margin-top: 0; }
""")

# --------------------------------------------------------------- Retours
brique("Message", "Retours", 250, "« Enregistré », « Annuler », erreur",
       """
# Message

Les messages en bas de l'écran : un mot pour dire que c'est fait, « Annuler » pendant 5 s quand on peut revenir en arrière, une phrase en rouge quand ça n'a pas marché.

- **Ce que tu fournis** : `Encre.toast("Enregistré")` ; `Encre.toast("Ajouté à « Soirées pop-corn »", { annuler: async () => … })` pour toute action réversible ; `Encre.toastErr(erreur)` pour une erreur. Trois messages au plus à la fois.
- **Rendu** : `.toast` (fond `pop`, trait `line2`, `r-lg`, ombre `shadow`), icône `check` en `ok` ou `alert` en `danger`, « Annuler » en `accent`, minuteur fin en `accent` dessous. Au-dessus de la barre flottante sur téléphone, 420 px centrés dès 640 px.
- **Durées** : 2,6 s, 4,5 s pour une erreur, 5 s avec « Annuler ».
- **Ton** : un ou deux mots (« Enregistré », « Annulé », « Copié ») ; une erreur dit quoi faire (« Réessaie dans un instant »). Jamais `alert()`.
""",
       """
<div class="toasts statique">
  <div class="toast">{{i:check}}<span class="tx">Enregistré</span></div>
  <div class="toast">{{i:check}}<span class="tx">Ajouté à « Soirées pop-corn »</span><button type="button" class="a">Annuler</button><span class="tm"><i></i></span></div>
  <div class="toast err">{{i:alert}}<span class="tx">Le site ne répond pas. Réessaie dans un instant.</span></div>
</div>
<div class="ligne vrai">
  <button type="button" class="btn sm" data-msg="simple">Message</button>
  <button type="button" class="btn sm" data-msg="annuler">Avec « Annuler »</button>
  <button type="button" class="btn sm" data-msg="erreur">Erreur</button>
</div>
""",
       css=CSS_STATIQUE + """  .toasts.statique { left: auto; right: auto; bottom: auto; width: auto; max-width: 420px; pointer-events: auto; }
  .toasts.statique .toast { animation: none; }
  .toasts.statique .tm i { animation: none; transform: scaleX(.62); }
  .vrai { justify-content: center; margin-top: 16px; }
""",
       js="""  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-msg]");
    if (!b) return;
    if (b.dataset.msg === "simple") Encre.toast("Enregistré");
    if (b.dataset.msg === "annuler") Encre.toast("Ajouté à « Soirées pop-corn »", { annuler: () => new Promise((r) => setTimeout(r, 300)) });
    if (b.dataset.msg === "erreur") Encre.toastErr(new Error("Le site ne répond pas. Réessaie dans un instant."));
  });
""")

brique("Confirmation", "Retours", 320, "À la place de confirm() et prompt()",
       """
# Confirmation

La question posée avant d'agir : une feuille du bas (fenêtre centrée sur ordinateur) avec « Annuler » et le verbe de l'action.

- **Ce que tu fournis** : `const ok = await Encre.confirmer(message, { ok: "Retirer", titre: "Retirer ce titre ?" })` ; pour une action sensible, `danger: true` (bouton plein `danger`) et `detail: "Cette action ne peut pas être annulée."`. Pour demander un nom : `const nom = await Encre.demander("Nouvelle liste", { label, placeholder, ok: "Créer" })` (`null` si on annule).
- **Rendu** : `.conf` > `p` (14,5 px `soft`), `.det` (12,5 px `muted`), `.bts` (deux boutons qui se partagent la largeur, l'action à droite).
- **Ton** : le titre est la question (« Effacer l'historique ? »), le bouton est le verbe (« Tout effacer »), jamais « OK ».
- **À éviter** : `confirm()`, `alert()`, `prompt()` du navigateur ; demander confirmation pour une action qu'on peut annuler (propose plutôt « Annuler » dans le message).
""",
       """
<div class="feuille statique">
  <div class="grab" aria-hidden="true"></div>
  <div class="feuille-t"><span class="tt">Effacer l'historique ?</span><span class="esp"></span><button type="button" class="ib" aria-label="Fermer">{{i:x}}</button></div>
  <div class="feuille-c"><div class="conf"><p class="msg">Tout ton historique sera effacé. Une sauvegarde complète est faite juste avant.</p><p class="muted petit det">Cette action ne peut pas être annulée.</p>
    <div class="bts"><button type="button" class="btn">Annuler</button><button type="button" class="btn dn plein">Tout effacer</button></div></div></div>
</div>
<div class="ligne vrai">
  <button type="button" class="btn sm" data-q="confirmer">Confirmer</button>
  <button type="button" class="btn sm dn" data-q="danger">Action sensible</button>
  <button type="button" class="btn sm" data-q="demander">Demander un nom</button>
</div>
""",
       css=CSS_STATIQUE + FEUILLE_STATIQUE_CSS + """  .vrai { justify-content: center; margin-top: 16px; }
""",
       js="""  document.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-q]");
    if (!b) return;
    if (b.dataset.q === "confirmer") {
      const ok = await Encre.confirmer("« Dune : deuxième partie » sera retiré de cette liste.", { ok: "Retirer", titre: "Retirer ce titre ?" });
      Encre.toast(ok ? "Retiré" : "Rien n'a changé");
    } else if (b.dataset.q === "danger") {
      const ok = await Encre.confirmer("Tout ton historique sera effacé. Une sauvegarde complète est faite juste avant.", { ok: "Tout effacer", danger: true, titre: "Effacer l'historique ?", detail: "Cette action ne peut pas être annulée." });
      if (ok) Encre.toast("Exemple seulement : rien n'a été effacé");
    } else {
      const nom = await Encre.demander("Nouvelle liste", { label: "Nom de la liste", placeholder: "Ex. : Soirées pop-corn", ok: "Créer" });
      if (nom) Encre.toast(`Liste « ${nom} » créée`);
    }
  });
""", icones_en_plus=["undo"])

brique("Menu", "Retours", 320, "Menu flottant à la souris, feuille au doigt",
       """
# Menu

Le menu d'actions d'un élément : flottant à côté du bouton « ⋯ » à la souris, en feuille du bas au doigt.

- **Ce que tu fournis** : `Encre.menu(bouton, [{ icone, texte, touche, danger, action }, null, …], { titre })` (`null` = séparateur), depuis un bouton `.ib` « ⋯ », un clic droit ou un appui long (`Encre.appuiLong`).
- **À la souris** : `.pop` (fond `pop`, trait `line2`, `r-lg`, ombre `shadow`, 230 px au moins) > `.pop-t` (le nom de l'élément), `.mi` (38 px, icône `soft`, touche `.k` à droite), `.msep`, `.mi.dn` en `danger`. Flèches, Entrée et Échap marchent.
- **Au doigt** : une feuille avec des lignes `.q-ext` (48 px, icône `soft`, `.dn` en `danger`).
- **À éviter** : plus de sept actions ; une action sensible sans confirmation derrière.
""",
       """
<div class="duo">
  <div>
    <div class="lbl-mono cap">À la souris</div>
    <div class="pop statique" role="menu" aria-label="Soirées pop-corn">
      <div class="pop-t">Soirées pop-corn</div>
      <button type="button" class="mi" role="menuitem">{{i:edit}}<span>Renommer</span><span class="k">R</span></button>
      <button type="button" class="mi on" role="menuitem">{{i:share}}<span>Partager</span></button>
      <button type="button" class="mi" role="menuitem">{{i:copy}}<span>Dupliquer</span></button>
      <div class="msep"></div>
      <button type="button" class="mi dn" role="menuitem">{{i:trash}}<span>Supprimer</span></button>
    </div>
  </div>
  <div>
    <div class="lbl-mono cap">Au doigt</div>
    <div class="carte doigt">
      <button type="button" class="q-ext">{{i:edit}}<span>Renommer</span></button>
      <button type="button" class="q-ext">{{i:share}}<span>Partager</span></button>
      <button type="button" class="q-ext dn">{{i:trash}}<span>Supprimer</span></button>
    </div>
  </div>
</div>
<div class="ligne vrai"><button type="button" class="ib" data-menu aria-label="Actions de la liste">{{i:dots}}</button><span class="petit muted">Le vrai menu</span></div>
""",
       css=CSS_STATIQUE + """  .duo { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; align-items: start; }
  .cap { margin-bottom: 10px; }
  .pop.statique { margin: 0; max-width: 300px; }
  .doigt { padding: 0 14px; }
  .doigt .q-ext:first-child { border-top: 0; }
  .vrai { justify-content: center; margin-top: 16px; }
""",
       js="""  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-menu]");
    if (!b) return;
    Encre.menu(b, [
      { icone: "edit", texte: "Renommer", touche: "R", action: () => Encre.toast("Renommer") },
      { icone: "share", texte: "Partager", action: () => Encre.toast("Lien copié") },
      { icone: "copy", texte: "Dupliquer", action: () => Encre.toast("Copie créée", { annuler: () => new Promise((r) => setTimeout(r, 200)) }) },
      null,
      { icone: "trash", texte: "Supprimer", danger: true, action: () => Encre.confirmer("La liste sera supprimée.", { ok: "Supprimer", danger: true, titre: "Supprimer la liste ?" }) },
    ], { titre: "Soirées pop-corn" });
  });
""")

brique("Selection", "Retours", 240, "Barre d'actions en verre",
       """
# Selection

La barre d'actions flottante, en verre comme la barre d'onglets : pendant une sélection multiple, ou pour les actions d'une fiche.

- **Ce que tu fournis** : `.barre-act` (fixée en bas, fond `glass`, flou de 14 px, trait `line2`, coins de 20 px, ombre `shadow`) avec `.compte` (« 3 choisis ») puis des `.btn.sm` (icône + `.lib`) et un `.ib` pour sortir. Ajoute `.sel` et `body.mode-sel` pendant une sélection : la barre d'onglets s'efface.
- **Fiche** : sans `.compte`, un bouton principal qui prend la place (`.btn.pri.croit`) et des boutons-icônes.
- **Écrans** : sous 480 px, les boutons de la sélection ne gardent que l'icône ; 640 px centrés dès 760 px.
- **Ton** : chaque action groupée propose « Annuler » dans le message qui suit.
""",
       """
<div class="scene">
  <div class="mur" aria-hidden="true"><div class="m2"></div><div class="m1"></div><div class="m3"></div><div class="m4"></div></div>
  <div class="barre-act sel statique">
    <span class="compte">3 choisis</span>
    <button type="button" class="btn sm" aria-label="Ajouter à une liste">{{i:listplus s18}}<span class="lib">Liste</span></button>
    <button type="button" class="btn sm" aria-label="Marquer terminé">{{i:check s18}}<span class="lib">Terminé</span></button>
    <button type="button" class="btn sm dn" aria-label="Retirer">{{i:trash s18}}<span class="lib">Retirer</span></button>
    <button type="button" class="ib" aria-label="Quitter la sélection">{{i:x}}</button>
  </div>
</div>
<div class="barre-act statique fiche">
  <button type="button" class="btn pri croit">{{i:play s18}}Reprendre l'épisode 4</button>
  <button type="button" class="btn ico" aria-label="À faire">{{i:bookmark}}</button>
  <button type="button" class="btn ico" aria-label="Plus d'actions">{{i:dots}}</button>
</div>
""",
       css=CSS_STATIQUE + MUR_CSS + """  .barre-act.statique { left: auto; right: auto; bottom: auto; width: auto; max-width: 640px; }
  .scene .barre-act { margin-top: -38px; }
  .fiche { margin-top: 16px; }
""")

brique("Bulle", "Retours", 240, "Le « ? » qui explique",
       """
# Bulle

Le petit « ? » à côté d'un titre, d'un chiffre ou d'un réglage : il ouvre une bulle d'explication.

- **Ce que tu fournis** : `<button type="button" class="q" aria-label="Explication" data-t="Titre" data-d="Texte">?</button>` ; pour une explication longue ou réutilisée, `data-q="cle"` et `Encre.bulles.cle = { t, d, k, pre }` (`pre` : un calcul ou une commande, sous un libellé `k`).
- **Rendu** : `.q` (rond de 18 px, DM Mono) ; `.bulle` (fond `pop`, trait `line2`, `r-lg`, ombre `shadow`, 340 px au plus) placée sous le bouton, ou au-dessus s'il n'y a pas la place. Elle se ferme en touchant ailleurs, en défilant ou avec Échap.
- **À éviter** : une bulle pour une information indispensable (elle va dans la page) ; plus d'un « ? » par ligne.
""",
       """
<p class="soft">Temps total <button type="button" class="q" aria-label="Explication" data-t="Temps total" data-d="La somme des durées de tout ce qui est marqué comme vu.">?</button> · touche le « ? »</p>
<div class="bulle statique"><b>Temps total</b><div>La somme des durées de tout ce qui est marqué comme vu.</div><div class="k">Le calcul</div><pre>films vus + épisodes vus
= 2 930 h</pre></div>
""",
       css=CSS_STATIQUE + """  .bulle.statique { margin: 12px 0 0; }
""")

# ---------------------------------------------------------------- Écrans
brique("Reglages", "Écrans", 320, "Liste à gauche, réglage à droite",
       """
# Reglages

La page des réglages : une liste de rubriques, et le réglage ouvert à côté (ordinateur) ou à la place (téléphone, avec un bouton retour).

- **Ce que tu fournis** : `.reglages` > `.reg-liste` (groupes `.reg-g` + `.liste-r` de `a.li`) et `.reg-det` (un `.btn.sm.gh.reg-retour` vers la liste, puis une `section.carte` par rubrique : `h2` en `titre-feuille` avec icône `accent`, `.intro`, des `.reg-sec` titrées en `.lbl-mono`, des lignes `.reg-l`). Ajoute `.detail` à `.reglages` quand une rubrique est ouverte sur téléphone.
- **Écrans** : sous 1000 px, la liste puis le réglage (l'un ou l'autre) ; dès 1000 px, liste de 340 px collée à gauche et réglage à droite.
- **Enregistrement** : chaque réglage s'enregistre seul, suivi de « Enregistré » ; pas de bouton « Enregistrer » en bas de page.
""",
       """
<div class="reglages">
  <div class="reg-liste">
    <div>
      <div class="reg-g">Mon compte</div>
      <div class="liste-r">
        <a class="li on" href="#apparence" data-reg="apparence"><span class="li-ic acc">{{i:palette}}</span><span class="tx">Apparence<small>Couleur d'accent, thème</small></span>{{i:chev s18 muted}}</a>
        <a class="li" href="#notifications" data-reg="notifications"><span class="li-ic">{{i:bell}}</span><span class="tx">Notifications<small>Discord, rappels</small></span>{{i:chev s18 muted}}</a>
      </div>
    </div>
    <div>
      <div class="reg-g">Site</div>
      <div class="liste-r">
        <a class="li" href="#apparence" data-reg="apparence"><span class="li-ic">{{i:refresh}}</span><span class="tx">Mise à jour<small>Version 2.4</small></span>{{i:chev s18 muted}}</a>
      </div>
    </div>
  </div>
  <div class="reg-det">
    <a class="btn sm gh reg-retour" href="#liste" data-retour>{{i:chevl s18}}Réglages</a>
    <section class="carte" data-panneau="apparence">
      <h2>{{i:palette s22 acc}}Apparence</h2>
      <p class="intro">Tout s'enregistre dès que tu changes un réglage.</p>
      <div class="reg-sec">
        <div class="lbl-mono">Thème</div>
        <div class="seg" data-encre-theme role="group" aria-label="Thème">
          <button type="button" data-v="auto">Automatique</button><button type="button" data-v="clair">Clair</button><button type="button" data-v="sombre">Sombre</button>
        </div>
      </div>
      <div class="reg-sec"><div class="reg-l"><div class="tx"><b>Animations</b><span>Les listes apparaissent en cascade</span></div><input type="checkbox" class="sw" checked aria-label="Animations"></div></div>
    </section>
    <section class="carte" data-panneau="notifications" hidden>
      <h2>{{i:bell s22 acc}}Notifications</h2>
      <p class="intro">Une ligne par réglage, chacun s'enregistre tout seul.</p>
      <div class="reg-l"><div class="tx"><b>Sorties</b><span>Le jour de la sortie, à 9 h</span></div><input type="checkbox" class="sw" checked aria-label="Sorties"></div>
      <div class="reg-l"><div class="tx"><b>Résumé de la semaine</b><span>Chaque dimanche soir</span></div><input type="checkbox" class="sw" aria-label="Résumé de la semaine"></div>
    </section>
  </div>
</div>
""",
       css="""  @media (min-width: 600px) {
    html .reglages { grid-template-columns: minmax(0, 250px) minmax(0, 1fr); align-items: start; }
    html .reglages:not(.detail) .reg-det { display: block; }
    html .reglages.detail .reg-liste { display: grid; }
    html .reglages .reg-retour { display: none; }
  }
""",
       js="""  const reg = document.querySelector(".reglages");
  document.addEventListener("click", (e) => {
    const a = e.target.closest("[data-reg], [data-retour]");
    if (!a) return;
    e.preventDefault();
    if (a.dataset.retour !== undefined) { reg.classList.remove("detail"); return; }
    reg.querySelectorAll("[data-reg]").forEach((x) => x.classList.toggle("on", x === a));
    reg.querySelectorAll("[data-panneau]").forEach((s) => { s.hidden = s.dataset.panneau !== a.dataset.reg; });
    reg.classList.add("detail");
  });
  document.addEventListener("change", (e) => { if (e.target.matches(".sw")) Encre.toast("Enregistré"); });
""")

brique("Connexion", "Écrans", 460, "Connexion et accès en attente",
       """
# Connexion

Les écrans d'accès : connexion, demande en attente, accès refusé, avec le même style que le reste du site.

- **Ce que tu fournis** : `<body class="login-page">` (centré, halo d'`accent` en haut) > `.login-card` (400 px, fond `card`, trait `line2`, coins de 22 px, ombre `shadow`) : `.login-logo` (logo ou `.wm`), `.badge` (« Accès privé »), `h2.h-acces` (26 px × 1,05), le formulaire (champs de 48 px sur `surface`, bouton `.btn.pri.w`), `.login-error` en cas d'erreur, `.forgot-link`.
- **Écran d'état** : `.access-icon` (rond de 64 px ; `.acc`, `.warn`, `.err`, `.ok`), `h2.h-acces`, `.mail-chip` (l'adresse en DM Mono), `.access-text` et `.access-note`. Variante large `.onboarding-card` / `.forgot-card` (520 px, texte à gauche) avec `.onb-steps`, `.forgot-steps`, `.forgot-cmd`.
- **Ton** : rassurant et précis (« Ta demande d'accès est bien arrivée. Tu pourras entrer dès qu'elle sera validée. »).
""",
       """
<div class="fond">
  <div class="login-card">
    <div class="login-logo"><span class="wm">mon<b>site</b></span></div>
    <span class="badge">Accès privé</span>
    <h2 class="h-acces">Connexion</h2>
    <form data-form>
      <input type="password" placeholder="Mot de passe" aria-label="Mot de passe" autocomplete="current-password">
      <div class="login-error">Mot de passe incorrect.</div>
      <button type="submit" class="btn pri w">Se connecter</button>
    </form>
    <a class="forgot-link" href="#oubli">Mot de passe oublié ?</a>
  </div>
  <div class="login-card">
    <div class="access-icon warn">{{i:hourglass}}</div>
    <h2 class="h-acces">Demande en attente</h2>
    <span class="mail-chip">noe@exemple.fr</span>
    <p class="access-text">Ta demande d'accès est bien arrivée. Tu pourras entrer dès qu'elle sera validée.</p>
    <p class="access-note">Rien d'autre à faire pour l'instant.</p>
  </div>
</div>
""",
       css="""  .fond { border-radius: var(--r-lg); border: 1px solid var(--line); padding: 22px 12px; display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; justify-items: center; align-items: start;
    background: radial-gradient(70% 50% at 50% 0%, color-mix(in srgb, var(--accent) 16%, transparent), transparent 70%), var(--bg); }
""",
       js="""  document.addEventListener("submit", (e) => { e.preventDefault(); Encre.toast("Connexion : à brancher sur ton site"); });
  document.addEventListener("click", (e) => { if (e.target.closest("a[href='#oubli']")) e.preventDefault(); });
""")

brique("Comptes", "Écrans", 270, "Comptes, rôles et accès",
       """
# Comptes

La liste des comptes d'un site à plusieurs personnes : qui a accès, avec quel rôle.

- **Ce que tu fournis** : `.acct-section` > `.sec-h` (`h2.sec-t` + `.acct-count`) puis `.acct-list` (carte `card`, `r-lg`) > `.acct-row` : `.acct-av` (initiale sur un dégradé `accent` → `prog`, texte `ink`), `.acct-main` > `.acct-mail` (gras) + `.acct-sub` (12 px `muted`), `.acct-actions` (badges et `.btn.xs`). La page entière : `body.page-simple` > `.acct-wrap` (760 px centrés).
- **Rôles** : `.role-badge.role-super` (accent), `.role-membre` (`ok`), `.role-bloque` (`danger`) : toujours avec le mot.
- **À éviter** : retirer le dernier super-admin (le site le refuse) ; une action sur un compte sans confirmation.
""",
       """
<div class="acct-section" style="margin-top: 0">
  <div class="sec-h" style="margin-top: 0"><h2 class="sec-t">Comptes</h2><span class="acct-count">3</span></div>
  <div class="acct-list">
    <div class="acct-row"><span class="acct-av">N</span><div class="acct-main"><span class="acct-mail">noe@exemple.fr</span><span class="acct-sub">Toi · connecté il y a 2 min</span></div><div class="acct-actions"><span class="role-badge role-super">Super-admin</span></div></div>
    <div class="acct-row"><span class="acct-av">L</span><div class="acct-main"><span class="acct-mail">lea@exemple.fr</span><span class="acct-sub">Depuis le 12 octobre</span></div><div class="acct-actions"><span class="role-badge role-membre">Membre</span><button type="button" class="btn xs">{{i:eye s16}}Voir en tant que</button></div></div>
    <div class="acct-row"><span class="acct-av">S</span><div class="acct-main"><span class="acct-mail">sam@exemple.fr</span><span class="acct-sub">Bloqué le 2 novembre</span></div><div class="acct-actions"><span class="role-badge role-bloque">Bloqué</span><button type="button" class="btn xs">Débloquer</button></div></div>
  </div>
</div>
""")

# ---------------------------------------------------------------- Icônes
NOMS = list(SYMBOLES)
brique("Icones", "Icônes", 870, "77 icônes tracées au trait",
       """
# Icones

Le jeu d'icônes : 77 symboles tracés au trait (24 × 24, trait 1,8, bouts et angles arrondis), dans `components/Icones/icones.svg`.

- **Ce que tu fournis** : colle `icones.svg` juste après `<body>` puis écris `<svg class="i" aria-hidden="true"><use href="#i-home"/></svg>` ; ou garde le fichier à part et pose `data-encre-sprite="/chemin/icones.svg"` sur `<html>` (`<use href="/chemin/icones.svg#i-home"/>`). En JavaScript : `Encre.ic("home", "s18")`.
- **Tailles** : 20 px par défaut, `.s16`, `.s18`, `.s22` (onglets, tuiles), `.s24`. Couleur : celle du texte (`currentColor`) ; `.acc`, `.muted`, `.dan` pour la changer.
- **Règles** : une icône accompagne un mot, ou porte un `aria-label` sur son bouton. Pas d'émoji, pas d'autre jeu d'icônes.
- **Logo** : pas de logo commun ; chaque site écrit son nom en `.wm` (seconde moitié en `<b>` : italique, couleur `accent`). Un site qui a son logo le dessine en SVG dans `.logo`, formes en `.lg-a` (accent) et `.lg-b` (fond).
""",
       '<div class="tailles">' + "".join(f'<span>{{{{i:star {c}}}}}<span class="mono">{t}</span></span>' for c, t in
                                       [("s16", "s16"), ("s18", "s18"), ("", "20"), ("s22", "s22"), ("s24", "s24")])
       + '<span class="wm">mon<b>site</b></span></div>\n<div class="grille">\n'
       + "\n".join(f'  <div>{{{{i:{n} s24}}}}<span class="mono">{n}</span></div>' for n in NOMS) + "\n</div>",
       css="""  .tailles { display: flex; align-items: flex-end; gap: 18px; flex-wrap: wrap; margin-bottom: 16px; color: var(--text); }
  .tailles > span:not(.wm) { display: grid; justify-items: center; gap: 6px; }
  .tailles .wm { margin-left: auto; }
  .mono { font-size: 10.5px; color: var(--muted); }
  .grille { display: grid; grid-template-columns: repeat(auto-fill, minmax(82px, 1fr)); gap: 8px; }
  .grille div { display: grid; justify-items: center; gap: 6px; padding: 12px 4px 10px; border: 1px solid var(--line); border-radius: var(--r-md); background: var(--card); color: var(--text); min-width: 0; }
""")
shutil.copyfile(DOSSIER / "icones.svg", SORTIE / "components" / "Icones" / "icones.svg") \
    if (SORTIE / "components" / "Icones").exists() else None

# ----------------------------------------------------------- assemblage
for b in BRIQUES:
    corps = icones(b["html"])
    utilisees = re.findall(r'href="#i-([a-z0-9]+)"', corps)
    noms = utilisees + b["icones"] + (BASE_ICONES if b["js"] or "data-encre" in b["html"] else [])
    if b["nom"] == "Icones":
        noms = NOMS
    lignes = [f'<!-- @dsCard group="{b["groupe"]}" height={b["hauteur"]} subtitle="{b["sous_titre"]}" -->',
              "<!doctype html>",
              '<html lang="fr" data-encre-prefs data-encre-sans-retour>',
              "<head>",
              '<meta charset="utf-8">',
              f"<title>{b['nom']} — aperçu</title>",
              "<style>", CSS_APERCU + b["css"] + "</style>",
              "</head>",
              f'<body{" data-page=" + chr(34) + b["page"] + chr(34) if b["page"] else ""}>',
              sprite(noms),
              corps]
    if b["js"]:
        lignes += ["<script>", "(() => {", b["js"].rstrip("\n"), "})();", "</script>"]
    lignes += ["</body>", "</html>", ""]
    page = "\n".join(lignes)
    assert "{{" not in page, b["nom"]
    for interdit in ("<iframe", "<object", "<embed", "<frame", "<portal", "<noscript"):
        assert interdit not in page, (b["nom"], interdit)
    ecrire(f"components/{b['nom']}/preview.html", page)
    ecrire(f"components/{b['nom']}/README.md", b["lisezmoi"])
shutil.copyfile(DOSSIER / "icones.svg", SORTIE / "components" / "Icones" / "icones.svg")

# ------------------------------------------------------------ couverture
ecrire("components/Cover/preview.html", """<!-- @dsCard height=288 -->
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Design encre</title>
<style>
  html, body { margin: 0; height: 100%; scrollbar-gutter: auto; }
  body { min-height: 0; padding: 0; background: var(--bg); color: var(--text); font-family: var(--font-body); overflow: hidden; }
  .cover { position: relative; width: 960px; height: 288px; overflow: hidden; }
  /* La composition : une boîte de 480 px sur la moitié droite, à l'écart du nom. */
  .art { position: absolute; top: 0; left: 480px; width: 480px; height: 288px; overflow: hidden; }
  .art svg { display: block; width: 480px; height: 288px; }
  .lavande { fill: var(--accent-lavande); }
  .menthe { fill: var(--accent-menthe); }
  .corail { fill: var(--accent-corail); }
  .or { fill: var(--accent-or); }
  .encre { fill: var(--text); }
  .blk { rx: var(--r-lg); }
  .petit { rx: var(--r-md); }
  /* La barre flottante : haute de tab-h, coins à la moitié de sa hauteur. */
  .barre { fill: var(--glass); stroke: var(--line2); stroke-width: 1; rx: calc(var(--tab-h) / 2); }
  .ti { fill: var(--line2); rx: 14px; }
  .ti.on { fill: var(--accent); }
  /* Le nom et la phrase, posés sur le fond, en bas à gauche. */
  .words { position: absolute; left: 32px; bottom: 30px; max-width: 440px; }
  .name { margin: 0; font-family: var(--font-title); font-weight: 400; font-size: 104px; line-height: .95; letter-spacing: 0; color: var(--text); }
  .name i { font-style: italic; color: var(--accent); }
  .tag { margin: 12px 0 0 4px; font-size: 14px; line-height: 20px; color: var(--muted); }
</style>
</head>
<body>
<div class="cover">
<div class="art" aria-hidden="true">
<svg viewBox="0 0 480 288" width="480" height="288">
<!--
  blocs       accent-lavande 144×224 qui sort par le haut (l'accent par défaut, le plus grand) · accent-menthe 96×144 · text 208×112 et accent-corail 208×96 qui sortent à droite · accent-or 96×64, une fois, petit — environ 31 % de 960×288
  disposition un mur de tuiles en trois colonnes, bas alignés, gouttières de pad (16) : le contenu coloré au-dessus duquel flotte la barre
  motif       la barre d'onglets flottante, telle quelle : une pilule haute de tab-h (rx moitié de tab-h) en glass avec un bord line2, à cheval sur le bas des tuiles, cinq pilules d'onglet de 46×28, l'active en accent ; choisie parce que la barre en verre flouté est ce qu'on retient de ce design
  échelles    côtés en multiples de pad (16) ; gouttières pad ; hauteur de barre tab-h (62) ; coins r-lg, le petit bloc r-md ; pilules d'onglet rx moitié de leur hauteur
-->
<rect class="lavande blk" x="16" y="-16" width="144" height="224" rx="14"/>
<rect class="or petit" x="176" y="-16" width="96" height="64" rx="10"/>
<rect class="menthe blk" x="176" y="64" width="96" height="144" rx="14"/>
<rect class="encre blk" x="288" y="-16" width="208" height="112" rx="14"/>
<rect class="corail blk" x="288" y="112" width="208" height="96" rx="14"/>
<rect class="barre" x="32" y="176" width="432" height="62" rx="31"/>
<rect class="ti on" x="52" y="193" width="46" height="28" rx="14"/>
<rect class="ti" x="139" y="193" width="46" height="28" rx="14"/>
<rect class="ti" x="225" y="193" width="46" height="28" rx="14"/>
<rect class="ti" x="311" y="193" width="46" height="28" rx="14"/>
<rect class="ti" x="398" y="193" width="46" height="28" rx="14"/>
</svg>
</div>
<div class="words">
<h1 class="name">Design<br><i>encre</i></h1>
<p class="tag">Un seul style pour tous tes sites.</p>
</div>
</div>
</body>
</html>
""")

# ------------------------------------------------------------ la charte
CHARTE = """Le design encre donne le même visage à tous les sites de Noë : un fond couleur d'encre, une seule couleur d'accent au choix du visiteur, des titres en DM Serif Display et une barre d'onglets qui flotte en verre flouté au-dessus du contenu. Les couleurs, tailles, coins et ombres sont des jetons (`tokens.css`), les briques sont des classes (`components/bundle.css`) et les comportements (feuilles, menus, messages, recherche rapide, bouton retour du téléphone) vivent dans `window.Encre` (`components/bundle.js`). Aucun framework : du HTML, ces trois fichiers, `fonts/` et le jeu d'icônes.

## Brancher le design sur une page

1. Charge `tokens.css`, puis `components/bundle.css`, puis `components/bundle.js` avec `defer`. Garde `fonts/` à côté de `tokens.css` : ses `@font-face` y pointent. Ne charge pas les polices depuis Google Fonts.
2. Colle le contenu de `components/Icones/icones.svg` juste après `<body>`. Pour le garder dans un fichier à part, pose `data-encre-sprite="/chemin/icones.svg"` sur `<html>` et écris `<use href="/chemin/icones.svg#i-home"/>`.
3. Mets ceci dans le `<head>`, avant les styles. Le zoom reste permis, l'encoche est prise en compte, et le thème est posé avant l'affichage, donc rien ne clignote :

```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark light">
<script>
  try {
    var p = JSON.parse(localStorage.getItem("encre-apparence") || "{}"), h = document.documentElement;
    if (p.accent) h.dataset.accent = p.accent;
    if (p.theme === "sombre") h.dataset.theme = "dark";
    else if (p.theme === "clair") h.dataset.theme = "light";
    else { h.dataset.theme = matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"; h.dataset.encreAuto = ""; }
  } catch (e) {}
</script>
```

   Si le serveur pose lui-même `data-accent` et `data-theme` d'après le compte, remplace ce script par `data-encre-prefs` sur `<html>`.
4. Garde la charpente, la même sur tous les sites :

```html
<div class="app">
  <aside class="side">…</aside>                        <!-- menu de gauche, 1000 px et plus -->
  <div class="main">
    <header class="top">…</header>                      <!-- barre du haut, téléphone et tablette -->
    <main class="pages">
      <section class="page on" data-page="accueil">…</section>
    </main>
  </div>
</div>
<nav class="tabbar" aria-label="Navigation">…</nav>   <!-- la barre flottante, hors de .app -->
<template id="encre-plus">…</template>                <!-- ce que montre « Plus » -->
```

   Une seule `section.page` porte `on` à la fois. Un site dont chaque page est une adresse du serveur pose `<body data-page="accueil">` et garde sa page en `page on`.

## Ce qui ne change jamais

- Une seule couleur d'accent, `accent`, pour ce qui compte : bouton principal, onglet actif, liens, coches, anneau du focus clavier. Tout le reste est en `text`, `soft` et `muted` sur les fonds.
- Écris le texte posé sur un fond `accent` en `ink`, jamais en blanc ni en `text`.
- Garde la barre d'onglets flottante en verre sur téléphone et tablette, détachée des bords, et le menu de gauche à partir de 1000 px.
- Titres en `title` (DM Serif Display), jamais en gras. Petits libellés en `libelle` : DM Mono, capitales espacées.
- Coins doux, traits d'un pixel, ombres seulement sur ce qui flotte : une carte posée dans la page n'a pas d'ombre.
- N'utilise jamais `alert()`, `confirm()` ni `prompt()` : `Encre.confirmer()` et `Encre.demander()` posent la question dans la page.
- Chaque action qu'on peut défaire propose « Annuler » pendant 5 secondes : `Encre.toast("Retiré de ta bibliothèque", { annuler })`.
- Le bouton retour du téléphone referme d'abord ce qui est ouvert (feuille, menu, réglage) avant de quitter la page.
- Laisse le zoom permis et les champs à 16 px. Boutons de 44 px de haut, boutons-icônes de 40 px ; `btn sm` (34 px) et `btn xs` (28 px) restent pour les rangées serrées.
- Les marges des côtés valent `pad` et s'écartent de l'encoche (`env(safe-area-inset-left)`, `…-right`, `…-bottom`).
- Toutes les couleurs passent par les jetons : jamais de couleur écrite en dur dans une brique.

## Contenu et ton

- Écris en français et tutoie : « Ta liste est vide », « Choisis une couleur ».
- Majuscule au premier mot seulement : « Couleur d'accent », « Zone sensible ».
- Guillemets français avec espaces : « Plus », « À voir plus tard ».
- Après une action, quelques mots au participe : « Enregistré », « Liste renommée », « Retiré de ta bibliothèque ». Une erreur dit quoi faire : « Pas enregistré, réessaie. »
- Boutons à l'infinitif. Dans une confirmation, le bouton reprend l'action (« Retirer », « Révoquer », « Tout décocher »), jamais « OK » ; le titre est une question courte (« Tout décocher ? ») et le texte dit ce qui va se passer (« Tous les épisodes de la série redeviennent « non vus ». »).
- Nombres à la française, espace insécable avant l'unité : « 2 930 h », « 14 h 02 », « 4,5 ».
- Pas d'emoji dans l'interface, pas de point d'exclamation, pas de jargon : le technique se range dans « Avancé ».

## Couleurs

- Range les fonds du plus profond au plus haut : `bg` (la page), `surface` (menu de gauche, boutons-icônes, puces, code), `card` (cartes, listes, tuiles, champs, boutons), `pop` (feuilles, menus, messages, bulles, recherche).
- `line` sépare discrètement (bord des cartes, entre deux lignes) ; `line2` trace les bords qu'on doit voir (champs, boutons, barre flottante) ; `creux` est le fond d'un segment.
- Texte : `text` pour le contenu, `soft` pour le secondaire, `muted` pour les dates et les aides. `muted` tient 5,3:1 en sombre et 4,8:1 en clair : rien de plus pâle pour du texte.
- États : `ok` (réussi, vu), `prog` (en cours), `danger` (supprimer, erreur), `warn` (attention), avec `ok-ink` et `prog-ink` pour le texte posé dessus. Les fonds teintés sont calculés dans `bundle.css` : `acc-dim` (accent à 14 %), `acc-line` (à 45 %, bord d'un élément accent), `ok-dim`, `prog-dim`, `danger-dim`. Un état va toujours avec une icône ou un mot, jamais la couleur seule.
- `glass` est le verre des barres flottantes, toujours avec `backdrop-filter: blur(16px) saturate(1.5)` ; `scrim` est le voile derrière une feuille.
- Sur une image : `on-img` pour le texte, `verre-img` pour un bouton en verre, `img-trait2` pour son bord, `img-bg` tant que l'image charge.
- Le bouton plein de suppression (`btn dn plein`, `blanc` sur `danger`) ne tient que 2,7:1 en sombre : réserve-le au bouton qui confirme une suppression, et prends `btn dn` (texte `danger`, fond transparent) partout ailleurs.

### Couleur d'accent

- Cinq accents, chacun avec son texte posé dessus : `accent-lavande` (par défaut), `accent-or`, `accent-ambre`, `accent-corail`, `accent-menthe`, et leurs `ink-…`. `data-accent` sur `<html>` choisit celui que suivent `accent` et `ink`.
- Le défaut d'un site se pose avec `data-accent-defaut="menthe"` sur `<html>` ; sans lui, c'est lavande.
- Le visiteur choisit dans Réglages, rubrique Apparence, avec les pastilles (brique `Pastilles`). Le choix reste sur l'appareil, et sur le compte si `Encre.apparence.sauver` est branché.
- Pour une 6e couleur, « rubis » par exemple : ajoute `accent-rubis` et `ink-rubis` aux deux thèmes, la règle `:root[data-accent="rubis"] { --accent: var(--accent-rubis); --ink: var(--ink-rubis); }`, la pastille `.past[data-v="rubis"] i { background: var(--accent-rubis); }` et `"rubis"` dans la liste `ACCENTS` de `bundle.js`. Vérifie 4,5:1 pour `ink-rubis` sur `accent-rubis` et pour `accent-rubis` sur `bg`, dans les deux thèmes.

### Thème

- Sombre par défaut. `data-theme="light"` force le clair, `data-theme="dark"` le sombre. En automatique, `bundle.js` pose `data-theme` d'après l'appareil avec `data-encre-auto`, et suit l'appareil s'il change pendant la visite.
- Le clair n'est pas l'inverse du sombre : un papier chaud (`bg` crème) avec des cartes blanches, et des accents plus foncés pour rester lisibles.
- Le focus clavier est un anneau de 2 px en `accent`, décalé de 2 px : ne le retire jamais.

## Typographie

- Trois familles : `title` (DM Serif Display : titres et grands chiffres), `body` (Archivo : tout ce qui se lit), `mono` (DM Mono : libellés, compteurs, touches, code).

| Style | Classe | Pour |
|---|---|---|
| `titre-page` | `.page-t` | le titre de chaque page |
| `titre-feuille` | `.feuille-t`, `.wm` | titre d'une feuille ou d'une fenêtre, nom du site |
| `titre-section` | `.sec-t` | titre d'une section |
| `chiffre`, `chiffre-grand` | `.tuile .v`, `.tuile.big .v` | les chiffres clés |
| `texte` | `body` | le texte courant |
| `ligne-liste` | `.li`, `.side-it` | lignes de liste et du menu de gauche |
| `bouton` | `.btn` | boutons, titre d'un réglage |
| `texte-petit` | `.petit` | sous-lignes et notes |
| `onglet` | `.tab` | mot sous l'icône d'un onglet |
| `saisie` | `input`, `select`, `textarea` | texte tapé |
| `libelle` | `.lbl-mono`, `.reg-g` | petits libellés en capitales |
| `chiffre-mono` | `.n`, `.kbd` | compteurs, touches |

- Ne mets jamais un titre en gras : la mise en valeur passe par l'italique. Le nom d'un site s'écrit en `.wm` et sa seconde moitié en italique `accent` : `<span class="wm">mon<b>site</b></span>`.
- `--t-scale` (1,05) multiplie toutes les tailles de titres : change-le pour agrandir ou réduire tous les titres d'un coup.
- Jamais moins de 16 px dans un champ (style `saisie`), sinon l'iPhone zoome tout seul.
- Titres en `text-wrap: balance` ; un paragraphe ne dépasse pas 68 caractères de large.

## Formes, espaces, ombres et mouvement

- Coins : `r-lg` (14 px) pour cartes, listes, tuiles, menus et messages ; `r-btn` (10 px) pour les boutons ; `r-md` (10 px) pour les lignes du menu de gauche, le code et les avertissements ; `r-sm` (8 px) pour les petits boutons et les coches. Hors jetons : 12 px pour les champs, segments et boutons-icônes, 99 px pour une pilule (puces, interrupteurs, badges), 20 px pour une fenêtre centrée et la barre d'actions, 24 px pour le haut d'une feuille, 26 px pour la barre flottante.
- Espaces : `pad` (16 px) sur les côtés au téléphone, 34 px à partir de 1000 px ; 10 à 14 px entre les cartes. Range les groupes avec `gap`, jamais avec des marges entre éléments voisins.
- Ombres : `shadow` pour ce qui flotte (menus, messages, bulles, fenêtres), `sh-tab` pour la barre flottante, `sh-feuille` pour une feuille du bas, `shadow-s` pour détacher un élément d'une carte ; `sh-plat`, `sh-sw` et `sh-past` restent à leur brique.
- Mouvement : une seule courbe, `--ease` (`cubic-bezier(.2, .8, .2, 1)`), de 0,12 à 0,32 s ; un bouton s'enfonce un peu à l'appui (`scale(.97)`) ; `Encre.animerEntree(el)` fait entrer des blocs en cascade. Tout s'arrête quand l'appareil demande moins d'animations (`prefers-reduced-motion`).

## La barre flottante

La pièce qui fait reconnaître le design (brique `BarreFlottante`). Elle flotte en bas sur téléphone et tablette, ne touche aucun bord et floute ce qui passe dessous.

```css
.tabbar {
  position: fixed; z-index: 40;
  left: max(12px, env(safe-area-inset-left, 0px));
  right: max(12px, env(safe-area-inset-right, 0px));
  bottom: calc(14px + env(safe-area-inset-bottom, 0px));
  height: var(--tab-h);
  background: var(--glass);
  border: 1px solid var(--line2); border-radius: 26px;
  box-shadow: var(--sh-tab);
  -webkit-backdrop-filter: blur(16px) saturate(1.5);
  backdrop-filter: blur(16px) saturate(1.5);
}
```

- Mets 3 ou 4 onglets puis « Plus » : 5 cases au plus. Chaque onglet est une icône `s22` au-dessus d'un mot en style `onglet`.
- L'onglet actif passe en `accent`, avec une pilule `acc-dim` derrière l'icône. `Encre.nav.marquer()` l'allume d'après `#page` ou `<body data-page>` ; « Plus » s'allume pour une page qui n'a pas d'onglet.
- « Plus » ouvre une feuille faite du `<template id="encre-plus">` : de grandes tuiles d'abord, puis des lignes (brique `FeuillePlus`).
- `.pages` réserve en bas `tab-h` + 52 px : la dernière ligne n'est jamais cachée.
- À partir de 640 px, la barre se centre sur 520 px ; à partir de 1000 px, elle laisse la place au menu de gauche (`side-w`, 248 px).
- Elle glisse hors de l'écran quand une feuille ou un menu est ouvert (`body.overlay-ouvert`) et pendant une sélection (`body.mode-sel`) : `bundle.js` pose ces classes.
- La barre du haut (`.top`) est en verre elle aussi (flou de 14 px sur `bg` à 86 %). Les messages se posent juste au-dessus de la barre flottante ; la barre d'actions d'une sélection prend sa place.
- Pour régler l'effet : plus de pixels dans `blur()` floute davantage ; une opacité plus basse dans `glass` (0,74 en sombre, 0,8 en clair) rend le verre plus transparent.

## Écrans

| Largeur | Ce qui change |
|---|---|
| moins de 640 px | barre du haut et barre flottante ; feuilles qui montent du bas ; réglages : la liste, puis le réglage en plein écran |
| 640 px et plus | barre flottante centrée (520 px), messages centrés |
| 760 px et plus | les feuilles deviennent des fenêtres centrées (520 px), les menus s'ouvrent à la souris |
| 1000 px et plus | menu de gauche à la place des deux barres, réglages en deux colonnes, marges de 34 px |

- Rien ne défile sur le côté, même à 360 px : grilles en `minmax(0, 1fr)`, longs mots coupés (`overflow-wrap: anywhere`), hauteurs plein écran en `100dvh`.

## Comportements

`bundle.js` ajoute un seul objet, `window.Encre`, et démarre tout seul. Ses types sont dans `components/index.d.ts`.

```js
Encre.toast("Enregistré");
Encre.toast("Ajouté à « À voir plus tard »", { annuler: async () => { /* défaire */ } });
Encre.toastErr(erreur);
const ok = await Encre.confirmer("Ce titre sera retiré.", { ok: "Retirer", danger: true, titre: "Retirer ?" });
const nom = await Encre.demander("Nouvelle liste", { label: "Nom", placeholder: "Ex. : Soirées", ok: "Créer" });
const f = Encre.feuille({ titre: "Détails", html: "<p>…</p>" });            // f.fermer()
Encre.menu(bouton, [
  { icone: "edit", texte: "Renommer", touche: "R", action: renommer },
  null,                                                                      // séparateur
  { icone: "trash", texte: "Supprimer", danger: true, action: supprimer },
], { titre: "Ma liste" });
Encre.occupe(bouton, () => fetch("/api/enregistrer", { method: "POST" }));  // bloqué jusqu'à la réponse
Encre.copier("texte à copier", bouton);                                     // le bouton dit « Copié »
Encre.appuiLong(liste, ".carte", (carte) => selectionner(carte));
Encre.recherche.raccourcis = [{ titre: "Réglages", icone: "gear", href: "#reglages" }];
Encre.nav.marquer("accueil");
Encre.apparence.choisir({ accent: "menthe" });
```

| Attribut | Où | Effet |
|---|---|---|
| `data-accent-defaut` | `<html>` | l'accent par défaut du site |
| `data-encre-prefs` | `<html>` | le serveur pose accent et thème d'après le compte ; l'appareil n'est pas relu |
| `data-encre-sans-retour` | `<html>` | pas d'étape d'historique pour les feuilles (site qui a son propre routeur) |
| `data-encre-sprite` | `<html>` | adresse du jeu d'icônes gardé à part |
| `data-encre-accent`, `data-encre-theme` | pastilles, segment | choix de l'accent et du thème branchés tout seuls |
| `data-encre-plus="id"` | bouton « Plus » | ouvre la feuille faite du `<template id>` |
| `data-encre-recherche` | un bouton | ouvre la recherche rapide (aussi Ctrl K, ⌘ K et « / ») |
| `data-fermer` | dans une feuille | ferme la feuille |
| `class="q"` + `data-t`, `data-d` | bouton « ? » | bulle d'explication |

- Pour garder le choix d'apparence sur le compte, donne `Encre.apparence.sauver = async ({ accent, theme }) => …` : s'il échoue, le choix est annulé.
- Un bouton qui enregistre passe par `Encre.occupe()` : une petite roue tourne, et impossible d'envoyer deux fois.
- Une couche faite maison s'inscrit avec `Encre.Couches.ouvrir(fermer)`, pour que le bouton retour la referme.

## Iconographie

- 77 icônes au trait dans `components/Icones/icones.svg` (symboles `#i-<nom>`) : trait de 1,8 px, bouts arrondis, couleur héritée du texte. Brique `Icones`.
- Tailles : 20 px par défaut, `s16`, `s18` (dans un bouton), `s22` (onglets, tuiles), `s24`. Couleurs : `acc`, `soft`, `muted`, `okc`, `dan`.
- Jamais d'emoji à la place d'une icône.
- Il n'y a pas de logo commun : chaque site écrit son nom en `.wm` (`mon<b>site</b>`). Un site qui a déjà son logo le garde.
"""
for mot in ("cinéthèque", "v29", "refonte"):
    assert mot not in CHARTE, mot
ecrire("README.md", CHARTE)

# ------------------------------------------ l'index, écrit en tout dernier
maintenant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
INDEX = {
    "v": 3,
    "layout": "files",
    "createdOnFiles": {"v": 1, "at": "2026-11-03T17:48:28Z"},  # première mise en ligne : ne bouge plus
    "title": TITRE,
    "namespace": "Encre",
    "libraries": [],
    "sections": {},
    "groups": [],
    "assetGroups": {},
    "blobs": {},
    "docs": {"readme": "project/README.md", "sections": []},
    "lastChange": {"by": "Noë", "at": maintenant, "via": "Claude Code",
                   "note": "Le texte posé sur l'accent est vérifié sur son accent ; jetons, polices, 27 briques, barre flottante et charte."},
}
ecrire("design-system.json", json.dumps(INDEX, ensure_ascii=False, indent=2) + "\n")

print(f"{len(BRIQUES)} briques ; fichiers :", sum(1 for p in SORTIE.rglob('*') if p.is_file()))
