# cinéthèque 🎬

Bibliothèque personnelle de **films et séries**, auto-hébergée : enregistre ce
que tu as vu, ce que tu veux voir, suis tes séries épisode par épisode, mesure
le temps passé et découvre de nouveaux films.

Site mono-utilisateur (compte `admin`), thème sombre doré, construit avec
**Python + Flask** et **SQLite**, alimenté par l'**API TMDB**. Aucune
dépendance front (HTML/CSS/JS vanilla), aucun build.

---

## Fonctionnalités

- **Bibliothèque** : films et séries, statuts (Vu / À voir / En cours),
  progression des séries (« où j'en suis : S x E y »), tri par date, genre,
  année, note, alphabétique.
- **Fiches** : durée, résumé, plateformes de streaming, bande-annonce.
  - Films : dates de visionnage multiples + revisionnages (« ↻ ×N »).
  - Séries : saisons dépliables, épisodes (nom, image, résumé, durée), marquage
    Vu/Revu par épisode / saison / série entière, prochain épisode.
- **Suggestions** (accueil) : carrousels Tendances, Au cinéma, Populaires, Mieux
  notés, « Parce que tu as aimé », sagas/chronologies.
- **Découverte** : catalogue filtrable (genre, année, note, pays, plateforme) et
  paginé.
- **Futur** : films à venir + alertes de sortie (cinéma / streaming).
- **Listes** : « À voir » et « Favoris » par défaut, listes perso.
- **Historique** : journal chronologique de chaque marquage (affiche + libellé
  + date/heure).
- **Profil** : temps total regardé, compteurs, genres les plus vus.
- **Notifications** : Discord via *botpanel* (voir plus bas).
- **Sauvegarde** : export/import complet des données.

---

## Architecture (pour lire, développer, modifier)

Tout le code applicatif est dans **`panel/`** :

| Fichier / dossier | Rôle |
|---|---|
| `app.py` | Création de l'app Flask + enregistrement des blueprints. |
| `config.py` | Chargement de la config (`PANEL_CONFIG`, défauts, mode dev). |
| `settings_store.py` | Réglages éditables à l'exécution (clé TMDB, notifs…). |
| `auth.py` | Login `admin` unique, décorateurs, auto-login Cloudflare Access. |
| `db.py` | Connexion SQLite par thread, schéma, migrations, helpers. |
| `tmdb.py` | Client de l'API TMDB (urllib, sans dépendance). |
| `routes/` | Blueprints : `pages`, `library`, `titles`, `discover`, `lists`, `alerts`, `people`, `stats`, `settings`. |
| `services/` | `posters` (cache local), `sync` (TMDB→base), `statistics`, `notifications`, `scheduler`. |
| `static/` | `style.css`, `app.js`, `fonts.css`, `logo.svg`, `favicon.svg`, `logo.png`, `sw.js`. |
| `templates/` | `index.html`, `login.html`, `forgot.html`. |

**Conventions**

- Langue : **français** partout (UI, docs, commits).
- Couleurs uniquement via les variables `:root` de `style.css`.
- Endpoints dynamiques : JSON sous `/api/*`, en `Cache-Control: no-store`.
- Secrets (`config.json`, `users.json`, `settings.json`, base) **jamais** commités.
- PWA : `static/sw.js` — penser à **incrémenter la version du cache** (`cinetheque-vNN`) à chaque changement de front.

**Vérifications avant chaque commit**

```bash
python3 -m py_compile panel/*.py panel/routes/*.py panel/services/*.py
node --check panel/static/app.js
bash -n install.sh scripts/*.sh proxmox/*.sh
```

**Déploiement**

- `install.sh` — idempotent (utilisateur dédié, config, systemd, sudoers).
- `scripts/update-panel.sh` — mise à jour GitHub (auto-remplaçante, détachée).
- `scripts/reset-admin-password.sh` — reset du mot de passe depuis le terminal.
- `proxmox/cinetheque-lxc.sh` — déploiement LXC en une commande.

---

## Installation

### Proxmox — une seule commande (recommandé)

Sur l'hôte Proxmox :

```bash
bash -c "$(wget -qLO - https://raw.githubusercontent.com/SuperNon0/Biblioth-que-de-filme/main/proxmox/cinetheque-lxc.sh)"
```

Crée un conteneur LXC Ubuntu, installe et démarre le site automatiquement.

### Manuelle (VM ou machine Ubuntu)

```bash
git clone https://github.com/SuperNon0/Biblioth-que-de-filme.git /opt/cinetheque-src
sudo bash /opt/cinetheque-src/install.sh
```

Puis ouvre `http://<ip>:8080`, connecte-toi avec le mot de passe affiché, et
renseigne ta **clé API TMDB** (gratuite) dans **Paramètres**.

### Développement local

```bash
cd panel
pip install flask          # ou apt install python3-flask
python3 app.py             # http://127.0.0.1:8080 avec une base ./.data
```

### Clé API TMDB

Gratuite pour un usage personnel : crée un compte sur
[themoviedb.org](https://www.themoviedb.org/), va dans Paramètres → API, copie
la clé, colle-la dans les Paramètres du site.

### Mot de passe oublié

```bash
sudo bash /opt/cinetheque/scripts/reset-admin-password.sh
```

---

## Notifications (Discord via botpanel)

cinéthèque **n'envoie rien à Discord directement**. Un planificateur
(`services/scheduler.py`) se réveille **toutes les 6 h** et, via l'API d'un outil
tiers **botpanel**, poste un message quand :

- un **nouvel épisode** d'une série suivie est diffusé ;
- un film sous **alerte** sort **au cinéma** ;
- un film sous **alerte** devient **disponible en streaming**.

Chaque événement n'est notifié **qu'une seule fois** (colonnes `episodes.notifie`
et `alertes.vue`). Le contrat réseau :

```
POST {URL_BOTPANEL}/api/notify
{ "id": "<slug>", "vars": { "nom": "valeur", … } }
```

**Réglages** (Paramètres → Notifications) : cocher *Discord*, renseigner l'**URL
botpanel**, et un **slug** par type d'événement (le slug est libre, recopié à
l'identique dans botpanel et cinéthèque). Bouton **Tester l'envoi** pour valider.

**Images** : chaque notif envoie `affiche` (poster, URL TMDB publique), `image`
(vignette d'épisode) et `logo` (logo cinéthèque). Dans botpanel, `{var:affiche}`
va dans *Large Image* et `{var:logo}` dans *Thumbnail*.

### Les 3 modèles + exemples de rendu

| Événement | Slug conseillé | Variables `vars` |
|---|---|---|
| Nouvel épisode | `cinetheque_episode` | `serie`, `code`, `titre`, `saison`, `episode`, `affiche`, `image` |
| Film au cinéma | `cinetheque_cine` | `titre`, `canal`, `affiche` |
| Film en streaming | `cinetheque_streaming` | `titre`, `plateformes`, `affiche` |

**📺 Nouvel épisode** — Titre `📺 {var:serie}` · Message
`Nouvel épisode {var:code} — {var:titre|à regarder} 🍿`
→ rendu :
> **📺 The Last of Us**
> Nouvel épisode S02E03 — Le sentier 🍿

**🎬 Film au cinéma** — Titre `🎬 {var:titre}` · Message
`C'est sorti — maintenant au {var:canal} ! 🎟️`
→ rendu :
> **🎬 Dune : Deuxième partie**
> C'est sorti — maintenant au cinéma ! 🎟️

**📺 Film en streaming** — Titre `📺 {var:titre}` · Message
`Disponible en streaming sur {var:plateformes|une plateforme} 🎬`
→ rendu :
> **📺 Oppenheimer**
> Disponible en streaming sur Netflix, Canal+ 🎬

Code de référence : `panel/services/notifications.py` (envoi) et
`panel/services/scheduler.py` (détection). ⚠️ Garde botpanel sur ton **réseau
local** (ou derrière un tunnel) : son API `/api/notify` n'a **pas**
d'authentification.

> Guide pas-à-pas complet (dépannage inclus) : [`docs/notifications.md`](docs/notifications.md).

---

## Logo & identité (liens réutilisables)

Fichiers dans `panel/static/`, servis **publiquement** sur GitHub (branche `main`) —
utilisables tels quels (miniature botpanel, favicon, etc.) :

| Fichier | Usage | Lien direct (raw) |
|---|---|---|
| `logo.png` (512×512) | Miniature Discord / thumbnail | `https://raw.githubusercontent.com/SuperNon0/Biblioth-que-de-filme/main/panel/static/logo.png` |
| `logo.svg` | Logo vectoriel (UI, impression) | `https://raw.githubusercontent.com/SuperNon0/Biblioth-que-de-filme/main/panel/static/logo.svg` |
| `favicon.svg` | Icône d'onglet / PWA | `https://raw.githubusercontent.com/SuperNon0/Biblioth-que-de-filme/main/panel/static/favicon.svg` |

> C'est le `logo.png` ci-dessus qui est envoyé comme variable `logo` dans les
> notifications (constante `LOGO_URL` de `services/notifications.py`).

**Couleurs du thème** (variables `:root` de `style.css`) : fond `#0e0f11`,
accent or `#e8c547`, vert `#4fc3a1`, violet `#a78bfa`, orange `#e87c47`,
rouge `#e85c47`, texte `#f0ede6`.

---

## Licence & attribution

Ce produit utilise l'API TMDb mais n'est ni approuvé ni certifié par TMDb.
*(This product uses the TMDb API but is not endorsed or certified by TMDb.)*
