# Design « encre » — le dossier

Le style de cinéthèque (version 29), rangé dans un dossier pour le réutiliser
sur n'importe quel site. Version du dossier : **1.0** (3 novembre 2026).

**En deux phrases.** « encre » n'est pas un thème tout fait trouvé sur
internet : c'est le style fait sur mesure pour cinéthèque pendant la refonte, à
partir de tes réponses (le nom vient du fond couleur d'encre). Ce dossier en
garde tout ce qui n'est pas propre aux films, pour que n'importe quel site, le
tien ou celui qu'un Claude construit pour toi, prenne exactement le même look,
avec la barre de navigation flottante en verre flouté.

## Sommaire

1. [Ce qu'il y a dans le dossier](#1-ce-quil-y-a-dans-le-dossier)
2. [Les bases (tes règles)](#2-les-bases-tes-règles)
3. [Les couleurs](#3-les-couleurs)
4. [Les polices et les tailles](#4-les-polices-et-les-tailles)
5. [Formes, espaces, ombres, mouvements](#5-formes-espaces-ombres-mouvements)
6. [La barre de navigation flottante](#6-la-barre-de-navigation-flottante)
7. [Les briques](#7-les-briques)
8. [Le comportement (encre.js)](#8-le-comportement-encrejs)
9. [Tous les écrans](#9-tous-les-écrans)
10. [Appliquer le design à un site](#10-appliquer-le-design-à-un-site)
11. [Vérifier que c'est réussi](#11-vérifier-que-cest-réussi)
12. [La phrase à donner à Claude](#12-la-phrase-à-donner-à-claude)
13. [Ce qui reste propre à cinéthèque](#13-ce-qui-reste-propre-à-cinéthèque)

---

## 1. Ce qu'il y a dans le dossier

| Fichier | À quoi il sert |
|---|---|
| `LISEZMOI.md` | Ce guide. |
| `demo.html` | La démonstration : ouvre-la dans un navigateur (double-clic). Toutes les briques, en vrai, avec leur HTML. |
| `modele.html` | Le squelette minimal d'un site : 3 pages, barre flottante, menu de gauche, choix de la couleur. Le point de départ à copier. |
| `encre.css` | Tout le style : les jetons (couleurs, polices, formes), puis les briques. Un seul fichier, sans compilation. |
| `encre.js` | Les comportements : thème et couleur, feuilles, menus, « Annuler », bouton retour du téléphone… Sans dépendance. |
| `polices.css` + `polices/` | Les 3 polices (10 fichiers woff2), servies par le site lui-même. |
| `icones.svg` | Les 77 icônes au trait (24 × 24). |
| `tailwind/encre-tailwind.css` | Les jetons en classes Tailwind v4, pour un site Next.js (comme RecipeLog). |
| `captures/` | À quoi ça ressemble : téléphone, ordinateur, clair, sombre, les 5 couleurs. |

Rien à installer : copier les fichiers suffit. `encre.css` marche seul ;
`encre.js` ajoute les comportements.

---

## 2. Les bases (tes règles)

Ce sont tes choix de la refonte de cinéthèque. Un site au design « encre »
les respecte tous.

### L'allure

1. **Fond couleur d'encre** (bleu nuit presque noir) et **une seule couleur
   d'accent** pour ce qui compte : bouton principal, onglet actif, liens.
2. **La couleur d'accent se choisit** dans Réglages → Apparence : or, ambre,
   corail, menthe ou **lavande (par défaut)**. Elle reste sur l'appareil, et sur
   le compte si le site a des comptes.
3. **Thème automatique** : sombre ou clair selon l'appareil, avec la
   possibilité de forcer l'un ou l'autre.
4. **Trois polices** : DM Serif Display pour les titres, Archivo pour le texte,
   DM Mono pour les petits libellés en capitales et les chiffres. Servies par
   le site (pas d'appel à Google Fonts).
5. **Formes douces** : coins arrondis (8 à 14 px, 20 à 26 px pour les feuilles
   et la barre flottante), traits fins, ombres légères.
6. **Des icônes au trait**, jamais d'emojis dans l'interface.
7. **Animations douces** (apparitions en cascade, fondus), coupées quand
   l'appareil demande moins d'animations.

### La navigation

8. **Barre de navigation flottante en verre flouté** en bas, sur téléphone et
   tablette : elle ne touche pas les bords, le contenu défile dessous, adouci
   par le flou. 3 ou 4 onglets + « Plus » (5 cases au maximum).
9. Elle **se cache** quand une feuille, un menu ou la sélection multiple est
   ouvert, et revient à la fermeture.
10. **Sur ordinateur** (1000 px et plus), un **menu à gauche** remplace la
    barre du bas et la barre du haut.
11. **« Plus »** ouvre une feuille : de grandes tuiles d'abord, puis des lignes.
12. **Recherche rapide** : Ctrl K (⌘ K sur Mac) ou « / » sur ordinateur, la
    loupe de la barre du haut sur téléphone.
13. **Le bouton retour du téléphone** referme d'abord ce qui est ouvert
    (feuille, menu, réglage) avant de quitter la page.

### Les réactions du site

14. **Jamais de fenêtre grise du navigateur** (`alert`, `confirm`, `prompt`) :
    questions et confirmations s'ouvrent dans la page.
15. **Feuilles qui montent du bas** sur téléphone, **fenêtres centrées** sur
    ordinateur.
16. **« Annuler » pendant 5 secondes** après chaque action qu'on peut défaire.
17. **Un bouton qui enregistre se bloque** (petite roue) jusqu'à la réponse :
    impossible d'envoyer deux fois.
18. **Les réglages s'enregistrent tout seuls**, avec un petit « Enregistré ».
19. **Bulles « ? »** à côté d'un chiffre ou d'un réglage pour l'expliquer.
20. **Squelettes gris** pendant le chargement, **message doux** quand une liste
    est vide.
21. **Menus** : clic droit et raccourcis à la souris ; **appui long** au doigt
    pour sélectionner plusieurs éléments.

### Les réglages et l'aide

22. **Réglages en liste**, comme sur un téléphone ; sur ordinateur, **deux
    colonnes** (la liste à gauche, le réglage ouvert à droite).
23. **Recherche dans les réglages** ; les réglages techniques rangés dans
    **« Avancé »** (selon le rôle) ; la **zone sensible**, en rouge, tout en bas.
24. **Aide en questions-réponses**, et un **bouton « Copier »** à côté de tout
    ce qui se copie.
25. **Écrans de connexion assortis** au reste du site.

### Le confort

26. **S'adapte à tous les écrans**, d'un petit téléphone (360 px) à un grand
    écran, sans jamais défiler sur le côté, en laissant de la place à
    l'encoche et à la barre du bas des téléphones.
27. **Zoom autorisé** ; les champs de saisie font 16 px, donc l'iPhone ne zoome
    pas tout seul quand on touche un champ.
28. **Contraste d'au moins 4,5:1** entre chaque texte et son fond (vérifié sur
    les jetons : 5,67 au plus bas en sombre, 4,78 en clair, avec les 5 couleurs).
29. **Facile à toucher** : boutons de 44 px de haut, barre d'onglets de 62 px.
30. **Tout en français.**

### Pour le code

31. **Toutes les couleurs passent par les jetons** (les variables CSS de
    `:root`) : jamais de couleur écrite en dur ailleurs.
32. **Les mêmes noms de classes partout** (`btn pri`, `tabbar`, `feuille`…),
    pour qu'un Claude retrouve ses repères d'un site à l'autre.
33. Si le site a un service worker, **le nom du cache suit la version** du site.

---

## 3. Les couleurs

Toutes les couleurs sont des **jetons** : des variables CSS définies une seule
fois en haut de `encre.css`. Les briques ne font que s'en servir. Changer un
jeton change tout le site d'un coup.

Ce qui décide de l'affichage, sur la balise `<html>` :

```html
<html data-accent="menthe">       <!-- la couleur d'accent (lavande si absent) -->
<html data-theme="light">         <!-- clair forcé ; "dark" = sombre forcé ; absent = automatique -->
```

`encre.js` pose ces deux attributs tout seul d'après le choix du visiteur.
En automatique, il pose quand même `data-theme` d'après l'appareil (avec
`data-encre-auto`) et suit l'appareil s'il change pendant la visite.

### Les fonds, traits et textes

| Jeton | Rôle | Sombre | Clair |
|---|---|---|---|
| `--bg` | fond de la page | `#0b0f17` | `#f5f3ee` |
| `--surface` | barres, champs, menu de gauche | `#0f1520` | `#ffffff` |
| `--card` | cartes | `#141b28` | `#ffffff` |
| `--pop` | menus, feuilles, messages | `#182131` | `#ffffff` |
| `--line` | séparateurs discrets | `#1e2737` | `#e7e2d7` |
| `--line2` | bordures visibles | `#2b3549` | `#d5cfc1` |
| `--creux` | fond des segments | `#0f1520` | `#ebe7de` |
| `--text` | texte | `#e7ebf3` | `#1b1d22` |
| `--soft` | texte secondaire | `#aab3c5` | `#454a55` |
| `--muted` | texte discret | `#8a94aa` | `#666b77` |
| `--glass` | verre des barres flottantes | `rgba(24, 28, 40, .74)` | `rgba(255, 255, 255, .8)` |
| `--scrim` | voile derrière les feuilles | `rgba(3, 5, 9, .62)` | `rgba(20, 18, 12, .42)` |

Le clair n'est pas l'inverse du sombre : c'est un papier chaud (crème),
pas un blanc froid, avec des cartes blanches posées dessus.

### Les états

| Jeton | Rôle | Sombre | Clair |
|---|---|---|---|
| `--ok` (+ `--ok-ink` pour le texte posé dessus) | réussi, terminé, vu | `#4fc0ad` | `#17725f` |
| `--prog` (+ `--prog-ink`) | en cours, progression | `#8f9cf0` | `#5159c9` |
| `--danger` | supprimer, erreur | `#ef7d6b` | `#bf3f2c` |
| `--warn` | attention | `#efb36b` | `#94560a` |

### Les 5 couleurs d'accent

Chaque accent a une version pour le sombre et une plus foncée pour le clair
(pour rester lisible sur fond crème), plus la couleur du texte posé dessus.

| Accent | Sombre : accent / texte dessus | Clair : accent / texte dessus |
|---|---|---|
| **Lavande** (défaut) | `#a99bff` / `#120d2e` | `#5a48d0` / `#ffffff` |
| Or | `#e8c547` / `#1b1504` | `#8a6400` / `#ffffff` |
| Ambre | `#f0a64a` / `#1a1206` | `#995400` / `#ffffff` |
| Corail | `#ff7a59` / `#2a0d05` | `#b23c1d` / `#ffffff` |
| Menthe | `#4fd1b5` / `#05211b` | `#0b7562` / `#ffffff` |

Dans les briques, on n'utilise que `--accent` (l'accent affiché) et `--ink`
(le texte posé dessus), plus les teintes calculées automatiquement :
`--acc-dim` (fond teinté, 14 %), `--acc-line` (bordure, 45 %), `--ok-dim`,
`--prog-dim`, `--danger-dim`.

**Ajouter une 6e couleur** (par exemple « rubis ») :

1. dans `encre.css`, un bloc
   `:root[data-accent="rubis"] { --acc-d: …; --ink-d: …; --acc-l: …; --ink-l: …; }`,
   une pastille `--sw-rubis` (dans `:root` et dans les deux blocs du clair) et
   `.past[data-v="rubis"] i { background: var(--sw-rubis); }` ;
2. dans `encre.js`, ajouter `"rubis"` à la liste `ACCENTS` ;
3. un bouton `<button type="button" class="past" data-v="rubis" role="radio"><i></i>Rubis</button>`
   dans Réglages → Apparence ;
4. vérifier le contraste du texte posé dessus (au moins 4,5:1).

---

## 4. Les polices et les tailles

| Police | Rôle | Graisses |
|---|---|---|
| **DM Serif Display** | titres de page et de section, grands chiffres, nom du site | normale + italique |
| **Archivo** | tout le texte : résumés, boutons, réglages | 400 à 700 |
| **DM Mono** | petits libellés en capitales, chiffres, raccourcis clavier, code | 400, 500 |

| Élément | Classe | Police | Taille |
|---|---|---|---|
| Titre de page | `page-t` | DM Serif Display | 27 px (30 px sur ordinateur) |
| Titre de section | `sec-t` | DM Serif Display | 19 px |
| Grand chiffre | `tuile .v` | DM Serif Display | 27 px (40 à 52 px pour `tuile big`) |
| Texte courant | (le `body`) | Archivo | 15 px, interligne 1,5 |
| Bouton | `btn` | Archivo, gras | 14 px |
| Petit texte | `petit` | Archivo | 12,5 px |
| Libellé | `lbl-mono` | DM Mono, capitales espacées | 11 px |
| Onglet de la barre | `tab` | Archivo | 10,5 px |
| Champ de saisie | `input`, `select`… | Archivo | 16 px (jamais moins) |

Toutes les tailles de titres sont multipliées par `--t-scale` (1,05) : changer
ce seul jeton agrandit ou réduit tous les titres d'un coup.

---

## 5. Formes, espaces, ombres, mouvements

- **Coins** : `--r-lg` 14 px (cartes, listes, tuiles), `--r-btn` 10 px
  (boutons), `--r-md` 10 px, `--r-sm` 8 px ; segments et champs 12 px ; puces
  en pilule ; feuilles 24 px en haut (20 px en fenêtre) ; barre flottante 26 px.
- **Espaces** : 16 px de marge sur les côtés sur téléphone (`--pad`, plus si
  l'écran a une encoche), 34 px sur ordinateur ; 10 à 14 px entre les cartes ;
  les groupes se rangent avec `gap`, pas avec des marges.
- **Ombres** : `--shadow-s` (petite), `--shadow` (menus, fenêtres, messages),
  `--sh-tab` (barre flottante), `--sh-feuille` (feuille du bas).
- **Mouvement** : une seule courbe, `--ease` = `cubic-bezier(.2, .8, .2, 1)`,
  rapide au départ et qui se pose en douceur ; 0,12 à 0,45 s ; les boutons
  s'enfoncent un peu quand on appuie (`scale(.97)`) ; les pages apparaissent
  en fondu, leurs blocs en cascade. Tout est coupé si l'appareil demande
  « réduire les animations ».

---

## 6. La barre de navigation flottante

La pièce que tu aimes beaucoup. Elle flotte à 14 px au-dessus du bas de
l'écran et à 12 px des côtés, avec des coins de 26 px. Son fond est à moitié
transparent et **floute ce qui passe dessous** : en faisant défiler, les images
et les cartes glissent derrière elle, adoucies.

Le HTML :

```html
<nav class="tabbar" aria-label="Navigation">
  <a class="tab" href="#accueil" data-page="accueil">
    <span class="ti"><svg class="i s22" aria-hidden="true"><use href="#i-home"/></svg></span>Accueil</a>
  <a class="tab" href="#liste" data-page="liste">
    <span class="ti"><svg class="i s22" aria-hidden="true"><use href="#i-list"/></svg></span>Liste</a>
  <!-- … 3 ou 4 onglets en tout … -->
  <button class="tab" type="button" data-encre-plus="encre-plus" aria-haspopup="dialog">
    <span class="ti"><svg class="i s22" aria-hidden="true"><use href="#i-dots"/></svg></span>Plus</button>
</nav>

<!-- Ce que montre « Plus » : de grandes tuiles, puis des lignes. -->
<template id="encre-plus">
  <div class="q-tuiles plus-t">
    <a class="qt" href="#reglages"><svg class="i s22" aria-hidden="true"><use href="#i-gear"/></svg>Réglages</a>
  </div>
</template>
```

La recette de l'effet (déjà dans `encre.css`, montrée ici pour comprendre) :

```css
.tabbar {
  position: fixed; z-index: 40;
  left: max(12px, env(safe-area-inset-left, 0px));      /* détachée des bords */
  right: max(12px, env(safe-area-inset-right, 0px));
  bottom: calc(14px + env(safe-area-inset-bottom, 0px)); /* au-dessus de la barre de l'iPhone */
  height: var(--tab-h);                                  /* 62 px */
  background: var(--glass);                              /* fond à moitié transparent */
  border: 1px solid var(--line2); border-radius: 26px;
  box-shadow: var(--sh-tab);
  -webkit-backdrop-filter: blur(16px) saturate(1.5);     /* le flou (Safari) */
  backdrop-filter: blur(16px) saturate(1.5);             /* le flou */
}
.tab.on { color: var(--accent); }                        /* onglet actif */
.tab.on .ti { background: var(--acc-dim); }              /* + pilule teintée derrière l'icône */
```

Ce qui va avec :

- **Place en bas** : `.pages` garde un espace de la hauteur de la barre (+ 52 px)
  pour que la dernière ligne ne reste jamais cachée dessous.
- **Tablette** (640 px et plus) : la barre se centre et fait 520 px de large.
- **Ordinateur** (1000 px et plus) : elle disparaît, le menu de gauche (`.side`,
  248 px) prend le relais.
- **Elle se cache** en glissant vers le bas quand une feuille ou un menu est
  ouvert (`body.overlay-ouvert`) ou pendant une sélection (`body.mode-sel`) :
  `encre.js` pose ces classes.
- **Onglet actif** : `encre.js` met `class="on"` sur l'onglet de la page en
  cours (d'après l'adresse `#page`, ou `<body data-page="…">`). « Plus »
  s'allume pour une page qui n'a pas d'onglet à elle.
- **La barre du haut** (`.top`, téléphone et tablette) est en verre elle aussi
  (flou 14 px) et prend un trait fin dès qu'on fait défiler.
- **Les messages** se posent juste au-dessus de la barre ; la **barre d'actions**
  de la sélection (`.barre-act`) prend sa place, en verre elle aussi.
- **Régler le flou** : plus de pixels dans `blur(16px)` = plus flou ; l'opacité
  de `--glass` (0,74 en sombre, 0,8 en clair) : plus bas = plus transparent.

---

## 7. Les briques

Chaque brique garde le même nom de classe sur tous les sites. `demo.html` les
montre toutes, avec leur HTML.

| Brique | Classes | À savoir |
|---|---|---|
| Boutons | `btn` ; `pri` (principal), `gh` (discret), `dn` (danger, `dn plein` = rouge plein), `prg`, `okb` ; tailles `sm`, `xs`, `ico` ; `w` (pleine largeur), `deux` (deux lignes) | 44 px de haut |
| Bouton rond | `ib` (+ `on`), `ib verre` sur une image | 40 px |
| Liens | `lien`, `lien-r` (« Tout voir ») | |
| Puces | `chips` > `chip` (+ `on`), `n` (nombre), `pastille` | pilules |
| Segments | `seg` > `button` (+ `on`), `seg ico` | |
| Champs | `champ` (avec icône), `input`, `select`, `lbl`, `form`, `statut ok` | 16 px |
| Interrupteur | `<input type="checkbox" class="sw">` | |
| Coches | `ck` (ronde), `ck sq` (carrée), (+ `on`) | |
| Cartes | `carte`, `bloc`, `ligne` (rangée qui passe à la ligne) | |
| Têtes | `page-h` > `page-t` ; `sec-h` > `sec-t` + `lien-r` ; `intro-p` | |
| Chiffres | `tuiles` > `tuile` (`big`), avec `k`, `v`, `s` ; barre `split` + `leg` | |
| Lignes | `liste-r` > `li` (`li-ic`, `tx` + `small`, `v`) | 54 px mini |
| Progression | `pg` > `i` (`ok`, `acc`, `epais`) | |
| Badges | `badge`, `role-badge role-super / role-membre / role-bloque`, `kbd` | |
| Vide, chargement | `vide` ; `sk`, `sk ln`, `sk ln t`, `sk-l` | |
| Zone sensible | `zone-d` | en bas des réglages |
| Copier, avertir, code | `copie` (`code` + bouton), `bandeau-c`, `bloc-code` | |
| Aide | `faq` > `faq-g`, `details` > `summary` + `rep` | |
| Réglages | `reglages` > `reg-liste` (`reg-g`, `liste-r`) + `reg-det` (`reg-retour`, `reg-panneau`, `reg-sec`, `reg-l`) | `reglages detail` = un réglage ouvert (téléphone) |
| Couleur d'accent | `pastilles` > `past` (`data-v`) | |
| Connexion | `login-page` sur `body`, puis `login-card`, `login-logo`, `h-acces`, `access-icon` (`acc`, `warn`, `err`, `ok`), `access-text`, `access-note`, `mail-chip`, `forgot-link` | écrans « en attente », « refusé »… |
| Page sans menu | `page-simple` sur `body` | une page à part (comptes…) |
| Recherche rapide | `side-search` (bouton du menu de gauche) ; `palette`, `pal-g`, `pal-it` | faite par `encre.js` |
| Feuilles, menus | `voile`, `feuille` (`feuille-t`, `feuille-c`), `pop` > `mi`, `q-tuiles` > `qt`, `q-ext` | faits par `encre.js` |
| Messages | `toasts` > `toast` (`err`) | faits par `encre.js` |
| Sélection | `barre-act sel` | en verre |
| Bulle | `q` (le bouton « ? »), `bulle` | |
| Mise en page | `app`, `side`, `main`, `top`, `pages`, `page` (+ `on`), `tabbar`, `pied` | |
| Icônes | `<svg class="i s18"><use href="#i-nom"/></svg>` ; tailles `s16`, `s18`, `s22` ; couleurs `acc`, `muted` | |
| Apparition | `anim` + `Encre.animerEntree(el)` | |

**Les 77 icônes** (`#i-…`) : `home`, `lib`, `compass`, `bell`, `bellon`, `dots`, `search`, `list`, `listplus`, `user`, `users`, `chart`, `gear`, `help`, `check`, `checks`, `x`, `plus`, `bookmark`, `bookmarkon`, `play`, `info`, `chev`, `chevl`, `chevd`, `chevu`, `clock`, `film`, `tv`, `heart`, `trash`, `filter`, `sort`, `grid`, `rows`, `grip`, `shield`, `key`, `cloud`, `plug`, `download`, `refresh`, `alert`, `sparkle`, `moon`, `sun`, `palette`, `type`, `lock`, `logout`, `edit`, `undo`, `wrench`, `chat`, `eye`, `cal`, `share`, `arrow`, `layers`, `zap`, `hourglass`, `mail`, `signal`, `wifi`, `spin`, `copy`, `hash`, `dot`, `star`, `staron`, `heartfill`, `dice`, `upload`, `ticket`, `external`, `minus`, `rotate`.
Elles sont tracées au trait (24 × 24, trait de 1,8), et prennent la couleur du texte autour.

---

## 8. Le comportement (encre.js)

`encre.js` ajoute un seul objet global, `Encre`, et démarre tout seul. Il ne
dépend de rien et ne touche pas au fonctionnement du site : il s'occupe de
l'apparence et des réactions.

```js
// Messages
Encre.toast("Enregistré");
Encre.toast("Ajouté à la liste", { annuler: async () => { /* défaire */ } });  // « Annuler » 5 s
Encre.toastErr(erreur);                                                         // en rouge

// Questions (à la place de confirm() et prompt())
const ok = await Encre.confirmer("Ce titre sera retiré.", { ok: "Retirer", danger: true, titre: "Retirer ?" });
const nom = await Encre.demander("Nouvelle liste", { label: "Nom", placeholder: "Ex. : Soirées", ok: "Créer" });

// Feuilles et menus
const f = Encre.feuille({ titre: "Détails", html: "<p>…</p>" });   // f.fermer()
Encre.menu(bouton, [
  { icone: "edit", texte: "Renommer", touche: "R", action: renommer },
  null,                                                             // séparateur
  { icone: "trash", texte: "Supprimer", danger: true, action: supprimer },
], { titre: "Ma liste" });

// Boutons, copie, gestes
Encre.occupe(bouton, () => fetch("/api/enregistrer", { method: "POST" }));  // bloqué jusqu'à la réponse
Encre.copier("texte à copier", bouton);                                     // le bouton dit « Copié »
Encre.appuiLong(liste, ".carte", (carte) => selectionner(carte));           // au doigt
Encre.animerEntree(conteneur);                                              // apparition en cascade

// Recherche rapide : Ctrl K, ⌘ K, « / » ou un bouton data-encre-recherche
Encre.recherche.raccourcis = [
  { titre: "Réglages", sous: "Tous les réglages", icone: "gear", href: "#reglages" },
  { titre: "Nouvelle liste", icone: "listplus", mots: "créer ajouter", action: nouvelleListe },
];
Encre.recherche.chercher = async (texte, { signal }) => {          // facultatif : résultats du site
  const r = await fetch(`/api/chercher?q=${encodeURIComponent(texte)}`, { signal });
  return (await r.json()).map((x) => ({ groupe: "Recettes", titre: x.nom, sous: x.categorie, icone: "list", href: x.url }));
};

// Navigation et apparence
Encre.nav.marquer("accueil");          // allume l'onglet
Encre.nav.aller("#reglages");          // ferme ce qui est ouvert, puis y va
Encre.apparence.choisir({ accent: "menthe" });
Encre.ic("home", "s18");               // le HTML d'une icône
```

Les réglages par attribut :

| Attribut | Où | Effet |
|---|---|---|
| `data-accent-defaut="lavande"` | `<html>` | la couleur par défaut du site |
| `data-accent`, `data-theme` | `<html>` | la couleur et le thème affichés (posés par `encre.js`, ou par le serveur) |
| `data-encre-auto` | `<html>` | posé en thème automatique : `data-theme` suit alors l'appareil |
| `data-encre-prefs` | `<html>` | le serveur décide (préférences du compte) : l'appareil n'est pas relu |
| `data-encre-sans-retour` | `<html>` | pas d'historique pour les feuilles (Next.js, ou site qui a déjà son routeur) |
| `data-encre-sprite="/static/encre/icones.svg"` | `<html>` | icônes dans un fichier à part plutôt que collées dans la page |
| `data-page="…"` | `<body>` | la page courante, pour un site à plusieurs pages côté serveur |
| `data-encre-accent` | conteneur des pastilles | choix de la couleur branché tout seul |
| `data-encre-theme` | segment du thème | choix du thème branché tout seul |
| `data-encre-plus="id"` | bouton « Plus » | ouvre la feuille faite du `<template id="…">` |
| `data-encre-recherche` | n'importe quel bouton | ouvre la recherche rapide |
| `data-fermer` | dans une feuille | ferme la feuille |
| `class="q" data-t="Titre" data-d="Texte"` | bouton « ? » | bulle d'explication |

**Garder la couleur sur le compte** (site avec comptes) : le serveur pose
`data-accent`, `data-theme` et `data-encre-prefs` sur `<html>`, et la page
donne à `encre.js` de quoi enregistrer :

```js
Encre.apparence.sauver = async (prefs) => {        // prefs = { accent, theme }
  const r = await fetch("/api/prefs", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(prefs),
  });
  if (!r.ok) throw new Error("Pas enregistré, réessaie.");   // le choix est alors annulé
};
document.addEventListener("encre:apparence", (e) => console.log(e.detail));  // après chaque changement
```

**Le bouton retour du téléphone** : chaque feuille, menu ou fenêtre ouverte
ajoute une étape à l'historique ; « retour » la referme au lieu de quitter le
site. Un lien touché dans une feuille la referme d'abord, puis ouvre la page.
Pour une couche faite maison : `const c = Encre.Couches.ouvrir(fermerMaCouche)`
puis `Encre.Couches.fermer(c)`.

---

## 9. Tous les écrans

| Largeur | Ce qui change |
|---|---|
| Moins de 640 px (téléphone) | barre du haut + barre flottante (à 12 px des bords) ; feuilles du bas ; réglages : la liste, puis le réglage en plein écran |
| 640 px et plus (tablette) | barre flottante centrée (520 px), messages centrés |
| 760 px et plus | les feuilles deviennent des fenêtres centrées (520 px) ; menus flottants à la souris |
| 1000 px et plus (ordinateur) | menu de gauche (248 px) à la place des deux barres ; réglages en deux colonnes ; marges de 34 px |

Pour que rien ne déborde : les grilles utilisent `minmax(0, 1fr)`, les longs
textes se coupent (`overflow-wrap: anywhere`), les marges tiennent compte de
l'encoche (`env(safe-area-inset-…)`) et les hauteurs plein écran utilisent
`100dvh` (la barre d'adresse du téléphone ne coupe rien).

---

## 10. Appliquer le design à un site

### Étape par étape (tous les sites)

1. **Copier** `encre.css`, `encre.js`, `polices.css`, `polices/` et
   `icones.svg` dans les fichiers statiques du site (par exemple
   `static/encre/`).
2. **Dans `<head>`** (adresses à adapter) :

   ```html
   <!-- Zoom autorisé : pas de maximum-scale ni de user-scalable=no. -->
   <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
   <meta name="color-scheme" content="dark light">
   <meta name="theme-color" content="#0b0f17" media="(prefers-color-scheme: dark)">
   <meta name="theme-color" content="#f5f3ee" media="(prefers-color-scheme: light)">
   <script>
     /* Avant l'affichage : accent et thème gardés sur cet appareil (rien ne clignote). */
     try {
       var p = JSON.parse(localStorage.getItem("encre-apparence") || "{}"), h = document.documentElement;
       if (p.accent) h.dataset.accent = p.accent;
       if (p.theme === "sombre") h.dataset.theme = "dark";
       else if (p.theme === "clair") h.dataset.theme = "light";
       else { h.dataset.theme = matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"; h.dataset.encreAuto = ""; }
     } catch (e) {}
   </script>
   <link rel="preload" href="/static/encre/polices/archivo-latin.woff2" as="font" type="font/woff2" crossorigin>
   <link rel="stylesheet" href="/static/encre/polices.css">
   <link rel="stylesheet" href="/static/encre/encre.css">
   <script defer src="/static/encre/encre.js"></script>
   ```

   (Si le serveur pose lui-même `data-accent` / `data-theme` d'après le
   compte, le petit script est inutile : mets `data-encre-prefs` sur `<html>`.)
3. **Les icônes** : colle le contenu de `icones.svg` juste après `<body>`, ou
   laisse le fichier à part et mets `data-encre-sprite="/static/encre/icones.svg"`
   sur `<html>` (dans ce cas, écris `<use href="/static/encre/icones.svg#i-home"/>`).
4. **La structure** de `modele.html` : `.app` > `.side` (menu de gauche) +
   `.main` > `.top` (barre du haut) + `main.pages` ; puis `nav.tabbar`
   et `template#encre-plus`.
5. **Habiller le contenu** avec les briques (section 7), page par page. Le
   fonctionnement du site ne change pas : seulement l'apparence.
6. **Retirer les anciennes couleurs et polices** : tout passe par les jetons.
7. **Remplacer** chaque `alert`, `confirm`, `prompt` par `Encre.toast`,
   `Encre.confirmer`, `Encre.demander`.
8. **Ajouter Réglages → Apparence** : pastilles de couleur + thème, copiés de
   `modele.html` (ils marchent tout seuls).
9. **Vérifier** avec la liste de la section 11.

Site à plusieurs pages côté serveur (chaque page est une adresse) : mets
`<body data-page="nom">` sur chaque page, des liens normaux dans la barre
(`href="/commandes"`), et le contenu directement dans `main.pages` (ou dans
`<section class="page on">`).

### Flask + Jinja (cinéthèque, site-base)

- Fichiers dans `static/encre/`, liens avec
  `{{ url_for('static', filename='encre/encre.css') }}`.
- Icônes : copie `icones.svg` en `templates/_icons.html` et
  `{% include "_icons.html" %}` juste après `<body>` (comme cinéthèque).
- Un gabarit `_base.html` porte `<head>`, les barres et un
  `{% block contenu %}` ; chaque page l'étend.
- Couleur sur le compte : le gabarit pose
  `<html data-accent="{{ prefs.accent }}" data-encre-prefs …>` et une route
  `/api/prefs` reçoit `Encre.apparence.sauver` (voir section 8). Si le site a
  une protection anti-CSRF par en-tête, ajoute-le dans ce `fetch`.
- site-base suit aujourd'hui le thème RecipeLog (doré, sombre seulement, zoom
  bloqué) : pour un site en « encre », ce dossier remplace ce contrat visuel
  (zoom autorisé, champs en 16 px, clair et sombre).

### FastAPI + Jinja (BotPanel)

- `app.mount("/static", StaticFiles(directory="static"), name="static")`, puis
  `{{ url_for('static', path='encre/encre.css') }}` dans les gabarits.
- Le reste comme Flask.

### Next.js + Tailwind (RecipeLog)

- Copie le dossier dans `src/encre/` et les polices dans `public/polices/` ;
  dans `polices.css`, remplace `url(polices/` par `url(/polices/`.
- Dans `src/app/globals.css` :

  ```css
  @import "tailwindcss";
  @import "../encre/polices.css";
  @import "../encre/encre.css";
  @import "../encre/tailwind/encre-tailwind.css";
  ```

  Les jetons deviennent des classes : `bg-fond`, `bg-carte`, `text-texte`,
  `text-doux`, `text-discret`, `border-trait`, `bg-accent text-encre`,
  `bg-accent-dim`, `text-danger`, `font-titre`, `font-mono`, `rounded-doux`,
  `rounded-barre`, `shadow-barre`… (testé avec Tailwind 4.1). Les briques
  restent utilisables telles quelles : `className="btn pri"`.
- Dans `app/layout.tsx` :
  `<html lang="fr" data-accent-defaut="lavande" data-encre-sans-retour suppressHydrationWarning>`
  (Next.js a son propre historique : `data-encre-sans-retour` évite que les
  deux se marchent dessus ; `suppressHydrationWarning` parce que la couleur et
  le thème sont posés avant React). Le petit script de l'étape 2 se met
  dans `<head>` avec `dangerouslySetInnerHTML`.
- `encre.js` dans `public/`, chargé par
  `<Script src="/encre.js" strategy="afterInteractive" />` ; ensuite
  `window.Encre.toast("Enregistré")` depuis un composant client.
- La barre flottante en composant React : les mêmes classes (`tabbar`, `tab`,
  `ti`), des `<Link>`, et l'onglet actif d'après `usePathname()`
  (`className={actif ? "tab on" : "tab"}`, sans `data-page` : c'est React qui
  allume l'onglet).
- Icônes : `lucide-react` convient (même style au trait) avec
  `strokeWidth={1.8}` ; ou le sprite `icones.svg`.

### Un site en HTML simple

Copie `modele.html` et les fichiers à côté, puis remplace les pages.

---

## 11. Vérifier que c'est réussi

- [ ] Sur téléphone, la barre flotte en bas, détachée des bords, et le contenu
      passe dessous, flouté.
- [ ] Elle disparaît quand une feuille ou un menu s'ouvre, et revient ensuite.
- [ ] Le bouton retour du téléphone referme la feuille sans quitter la page.
- [ ] Sur ordinateur, le menu de gauche remplace les deux barres.
- [ ] Les 5 couleurs et les 3 thèmes se changent dans Réglages → Apparence et
      restent après un rechargement.
- [ ] Aucune page ne défile sur le côté, même à 360 px de large.
- [ ] Plus aucun `alert(`, `confirm(` ni `prompt(` dans le code.
- [ ] Aucune couleur écrite en dur en dehors des jetons de `encre.css`.
- [ ] Le zoom marche, et toucher un champ ne zoome pas tout seul.
- [ ] Les textes restent lisibles en clair comme en sombre.
- [ ] Aucune erreur dans la console du navigateur.

---

## 12. La phrase à donner à Claude

Pour habiller un site (existant ou nouveau), donne ce dossier à Claude dans le
projet du site (par exemple dans un dossier `design-encre/` du dépôt) avec :

> Applique le design « encre » à ce site. Tout est dans le dossier
> `design-encre/` : lis d'abord `LISEZMOI.md`, puis regarde `demo.html` et
> `modele.html`. Garde toutes les fonctions du site telles quelles, ne change
> que l'apparence et la navigation. Je veux la barre de navigation flottante en
> verre flouté en bas sur téléphone, le menu à gauche sur ordinateur, le choix
> de la couleur (lavande par défaut) et le thème automatique dans Réglages →
> Apparence. Respecte les règles de la section 2, coche la liste de la
> section 11, et montre-moi des captures téléphone et ordinateur avant de
> fusionner.

**Le même design, en ligne et en privé.** La page « Design encre » de ton
compte Claude montre les couleurs, les polices et chaque brique en vrai :
<https://claude.ai/artifact/1EJwFWYo5CDa9617N757fV>. Toi seul peux l'ouvrir.
Un Claude de tes autres projets peut la lire directement : ajoute à la phrase
« Le design est aussi décrit sur
https://claude.ai/artifact/1EJwFWYo5CDa9617N757fV ».

---

## 13. Ce qui reste propre à cinéthèque

Pas repris dans ce dossier : la fiche d'un film et ses affiches, le mur
d'affiches, les épisodes, Découvrir et ses filtres, le calendrier des sorties,
les statistiques de visionnage, les icônes d'application par couleur et le
manifeste. Quelques noms de classes viennent encore de cinéthèque
(`side-listes`, `dot ordo`, `split` Films / Séries) : ils marchent tels quels
pour n'importe quel contenu.

**Licences** : les trois polices sont sous licence libre SIL Open Font License
(on peut les servir avec le site) ; les icônes et le code ont été faits pour
cinéthèque.
