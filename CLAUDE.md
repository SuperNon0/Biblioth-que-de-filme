# cinéthèque — mémoire projet

Bibliothèque personnelle de films et séries, auto-hébergée, mono-utilisateur.
Basée sur le socle « CDC / MultiOutils » (Palworld Panel) : Flask, thème sombre
doré, déploiement Proxmox, mise à jour auto-remplaçante.

## Stack

- **Backend** : Python 3 + Flask (installable via `apt`).
- **Base** : SQLite (`panel/db.py`), fichier unique, exportable.
- **Front** : HTML + CSS + JS vanilla (aucun build, aucun framework front).
- **Données** : API TMDB (`panel/tmdb.py`, urllib, sans dépendance).

## Architecture (`panel/`)

- `app.py` — création de l'app Flask + enregistrement des blueprints.
- `config.py` — chargement de la config (`PANEL_CONFIG`, défauts, mode dev).
- `settings_store.py` — réglages éditables (clé TMDB…) inscriptibles à l'exécution.
- `context.py` — accès partagé (config, client TMDB).
- `auth.py` — login `admin` unique, décorateurs, Cloudflare SSO.
- `db.py` — connexion SQLite par thread, schéma, helpers.
- `tmdb.py` — client de l'API TMDB.
- `routes/` — blueprints : `pages`, `library`, `titles`, `discover`, `lists`,
  `alerts`, `stats`, `settings`.
- `services/` — `posters` (cache local), `sync` (TMDB→base), `statistics`.
- `static/` — `style.css`, `app.js`, `fonts.css`, `logo.svg`, `favicon.svg`.
- `templates/` — `index.html`, `login.html`, `forgot.html`.

## Conventions

- Langue : français partout (UI, docs, commits).
- Couleurs uniquement via les variables `:root` de `style.css`.
- Endpoints dynamiques : JSON sous `/api/*`, `Cache-Control: no-store`.
- Secrets (config.json, users.json, settings.json, base) jamais committés.

## Vérifications avant commit

```bash
python3 -m py_compile panel/*.py panel/routes/*.py panel/services/*.py
node --check panel/static/app.js
bash -n install.sh scripts/*.sh proxmox/*.sh
```

## Déploiement

- `install.sh` idempotent (utilisateur dédié, config, systemd, sudoers).
- `scripts/update-panel.sh` : mise à jour GitHub (auto-remplaçante, détachée).
- `scripts/reset-admin-password.sh` : reset du mot de passe depuis le terminal.
- `proxmox/cinetheque-lxc.sh` : déploiement LXC en une commande.

## Hors périmètre (v1)

Animés, notation/avis, notifications e-mail/Discord, multi-utilisateurs,
statistiques par période, chronologie manuelle (remplacée par les listes).
