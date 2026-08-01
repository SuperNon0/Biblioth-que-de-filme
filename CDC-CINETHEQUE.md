# Cahier des charges — cinéthèque

Bibliothèque personnelle de films et séries : enregistrer ce que j'ai vu,
ce que je veux voir, suivre mes séries épisode par épisode, mesurer le temps
passé, découvrir de nouveaux films et être prévenu des sorties à venir.

Document issu des échanges de cadrage. Sert de référence pour le développement.
Langue du projet : **français** (interface, docs, commits).

---

## 1. Vision

Un site **auto-hébergé, pour un seul utilisateur (moi)**, qui remplace les
applications de suivi de films/séries existantes, avec ma propre interface et
mon propre thème. Pas de système d'avis, pas de réseau social : c'est **mon
carnet perso**.

Trois façons de trouver des films :
1. **Ma bibliothèque** — ce que j'ai déjà enregistré.
2. **Suggestions** — recommandations personnalisées d'après mes goûts.
3. **Découverte** — le catalogue large, pour explorer.

---

## 2. Contraintes (les seules imposées)

- **C1 — Connexion.** Identifiant fixe `admin` (pas de champ identifiant, juste
  un mot de passe). Le mot de passe est **modifiable dans les paramètres**.
- **C2 — Réinitialisation.** Un **script terminal** remet le mot de passe à zéro
  en cas d'oubli (repris du socle : `reset-admin-password.sh`).
- **C3 — Thème.** Respecter la **charte** du socle (fond quasi noir, texte
  DM Mono, titres serif dorés DM Serif Display, accents or/teal, chips, coins
  arrondis 12 px). Mise en page **libre**, mais ambiance imposée.
- **C4 — Responsive.** Utilisable et joli sur **téléphone et ordinateur**.
- **C5 — Base de données.** Toutes les données stockées **proprement en base**,
  **exportables / sauvegardables** (secours, changement d'infrastructure).

Pas de contrainte « hors ligne » : le site **peut** appeler des API externes.

---

## 3. Choix techniques

| Élément | Choix | Raison |
|---|---|---|
| Backend | **Python + Flask** | Cohérent avec le socle existant (Palworld Panel) |
| Base de données | **SQLite** | Vraie base fiable dans un fichier → sauvegarde/export triviaux |
| Frontend | HTML + CSS + JS, thème du socle | Reprise de `style.css` / `fonts.css` |
| Données films/séries | **API TMDB** | Fiches, affiches, épisodes (nom/description/durée), dates, plateformes, bandes-annonces |
| Déploiement | **LXC Proxmox en 1 commande** | Repris du socle (`install.sh`, `update-panel.sh`, systemd) |

**Prérequis** : une **clé API TMDB** (gratuite), stockée dans `config.json`
(jamais committée).

**Coût & licence TMDB** : **gratuit et sans limite de durée** pour un usage
**personnel / non-commercial** (ce projet). Débit ~40-50 requêtes/seconde,
très au-dessus des besoins. Payant seulement en usage commercial. **Obligation**
: afficher en bas de page la mention *« This product uses the TMDb API but is
not endorsed or certified by TMDb »* + le logo TMDB.

**Sources de style** (inspiration UI, pas de code repris) : **FilmNoir**
(carrousels Discover : tendances / box-office / populaires), **Letterboxd**
(carrousels + « voir plus » + puces de filtre), **Simkl** (notifications de
sorties).

---

## 4. Fonctionnalités

### 4.1 Bibliothèque
- Contient **films et séries** (pas d'animés en v1, pas de documentaires/courts).
- **Statuts** : `Vu`, `À voir`, `En cours`, `Abandonné`.
- **Tri / filtre** : date, statut, genre, année, alphabétique.
- Affichage en **grille d'affiches**.

### 4.2 Ajouter un titre
- **Recherche par nom** dans TMDB → sélection → la fiche se remplit
  automatiquement (durée, date de sortie, description, affiche, plateformes).
- **Ajout manuel** possible (titre absent de TMDB).
- Section **Suggestions à ajouter** : films connus/classiques proposés en un
  clic pour remplir vite la bibliothèque au démarrage.

### 4.3 Fiche film
- Infos TMDB : affiche, durée, date de sortie, description, genres.
- **Où le regarder** : plateformes de streaming (TMDB « watch providers », FR).
- **Bande-annonce** (lien TMDB/YouTube).
- **Dates de visionnage** : une date au premier visionnage, possibilité d'en
  **ajouter d'autres** à chaque re-visionnage → **compteur de revisionnages**.

### 4.4 Fiche série
- **Volets déroulants par saison** (S1, S2, S3…).
- Chaque épisode affiche : **nom + image + description + durée** + bouton
  **`Vu`** (devient **`Revu`** si déjà vu).
- Boutons **« marquer toute la saison »** et **« marquer toute la série »** vue.
- **Prochain épisode** : date de sortie du prochain épisode (prévue ou
  confirmée), selon l'info disponible.

### 4.5 Profil / Statistiques
- **Temps passé** calculé automatiquement (durée × épisodes/films vus) :
  - **total en heures**,
  - **converti automatiquement en mois / années**,
  - **par série**.
- **Compteurs** : nb de films vus, nb d'épisodes vus, nb de séries vues.
- **Analyses** : genres les plus vus, acteurs/réalisateurs les plus vus,
  répartition par année.
- (Pas de stats par période — jugé inutile.)

### 4.6 Suggestions (page d'accueil)
Inspiration : **FilmNoir** / **Letterboxd** — une pile de **carrousels
horizontaux** (défilement gauche→droite), habillés du thème doré/sombre, avec
des **puces de filtre** `Tout / Films / Séries` en haut de page.

Carrousels proposés :
- ▸ **Reprendre** — séries en cours à continuer
- ▸ **Tendances cette semaine**
- ▸ **Au cinéma en ce moment** (l'esprit « box-office »)
- ▸ **Populaires**
- ▸ **Mieux notés**
- ▸ **Recommandé pour toi** — d'après la bibliothèque (recommandations TMDB)

Chaque carrousel a un bouton **« voir plus »**. Filtres & tri : par **genre**,
par **popularité / les plus vus**.

> Note « box-office » : TMDB ne fournit pas de classement officiel des recettes.
> On rend le même ressenti avec **« Au cinéma en ce moment »** + **tendances**
> (et les recettes affichées sur chaque fiche). Un vrai classement chiffré
> nécessiterait une source tierce payante — hors périmètre.

### 4.7 Découverte
- **Catalogue large** : voir **tous les films et séries** qui existent.
- Vue **« Top films »**, avec bascule **Films seuls / Séries seules / Tout**.
- **Filtres & tri** : par **genre**, **popularité / tendances**, **année de
  sortie**, **note TMDB**, **pays / langue**.
- **Pagination** (« par page ») pour parcourir de grands volumes.

### 4.8 Listes
- Liste **« À voir » présente par défaut**.
- **Création de listes** libres (ex. « Films de Noël »).
- Liste **Favoris** séparée (films préférés).
- **Import de listes générées** : je peux demander une liste toute prête (ex.
  « ordre idéal pour voir Marvel ») et l'importer en un clic.

### 4.9 Futur (sorties à venir)
- Page listant **tous les films à venir** avec **dates** et **bande-annonce**,
  récupérés automatiquement (TMDB « upcoming »).
- **Alertes de sortie** : poser une alerte sur un film → être prévenu quand il
  sort **au cinéma** ou **sur une plateforme de streaming**, avec l'info
  ciné/streaming **affichée sur la page**.
- Notification **dans le site** (badge/notif). E-mail / Discord : possible plus
  tard si souhaité.

### 4.10 Sauvegarde / export
- **Export** complet des données (fichier de secours, migration d'infra).
- **Import** du même fichier pour restaurer.

---

## 5. Navigation (onglets)

1. **Suggestions** *(page d'accueil par défaut ; propose aussi « reprendre » les séries en cours)*
2. **Bibliothèque**
3. **Découverte**
4. **Futur**
5. **Listes**
6. **Profil / Statistiques**
7. **Paramètres** *(mot de passe, clé API TMDB, sauvegarde/export)*

Navigation adaptée mobile (barre d'onglets responsive).

---

## 6. Données (aperçu du modèle SQLite)

- `titres` : id TMDB, type (film/série), titre, année, affiche (cachée en
  local), durée, genres, statut, date d'ajout.
- `visionnages` : titre, date, (revisionnage n°).
- `series_saisons` / `series_episodes` : n° saison/épisode, nom, description,
  durée, image, vu (oui/non), dates de visionnage.
- `listes` / `listes_items` : listes perso, favoris, « à voir ».
- `alertes` : titre suivi, type (ciné/streaming), état.
- `prefs` : préférences d'affichage, tri par défaut, etc.

Affiches et images d'épisodes **téléchargées et mises en cache localement**
pour un affichage rapide et une sauvegarde autonome.

---

## 7. Déploiement (repris du socle)

- `install.sh` idempotent : utilisateur dédié non-root, dossiers, config
  (secret de session + hash du mot de passe admin), unit systemd, sudoers
  minimal.
- `scripts/update-panel.sh` : mise à jour depuis GitHub (auto-remplaçant +
  redémarrage détaché).
- `scripts/reset-admin-password.sh` : réinitialisation du mot de passe.
- `proxmox/cinetheque-lxc.sh` : déploiement **LXC en une commande** (adapté de
  `palworld-vm.sh`).

---

## 8. Hors périmètre (v1)

- Animés (ajout ultérieur possible).
- Système de notation / avis.
- Chronologie manuelle (remplacée par les listes importables).
- Notifications e-mail / Discord.
- Statistiques par période.
- Multi-utilisateurs.

---

## 9. Identité

- Nom : **cinéthèque**.
- Logo du site (haut-gauche) : **clap de cinéma** doré + mot-symbole
  **ciné** (doré) *thèque* (blanc italique), dans le thème du site.
- Favicon (onglet navigateur + favori) : **clap minimal** (icône sans texte,
  assortie au logo), lisible en 16 px.
