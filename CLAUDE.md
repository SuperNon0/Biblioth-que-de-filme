# cinéthèque — mémoire projet

Bibliothèque personnelle de films et séries, auto-hébergée. **v2 : multi-comptes
à données cloisonnées** (chaque compte a SA bibliothèque) derrière Cloudflare
Zero Trust — fondation « site-base ». Flask, thème sombre doré, déploiement
Proxmox, mise à jour auto-remplaçante.

## Stack

- **Backend** : Python 3 + Flask (installable via `apt`).
- **Base** : SQLite (`panel/db.py`), fichier unique, exportable.
- **Front** : HTML + CSS + JS vanilla (aucun build, aucun framework front).
- **Données** : API TMDB (`panel/tmdb.py`, urllib, sans dépendance).
- **Auth** : PyJWT + cryptography (`python3-jwt`, `python3-cryptography` via apt)
  pour vérifier le JWT Cloudflare Access. Seule dépendance ajoutée au socle.

## Auth v2 (fondation multi-comptes)

- **Cloudflare Access** = portier e-mail (JWT vérifié : `aud` + `iss`). L'app
  gère rôles + cycle de vie. Voir `docs/authentification-v2.md`.
- Rôles : `super_admin` (toi, login local + e-mail) et `membre`. Le **dernier
  super-admin est indestructible**.
- Site **« perso »** (`cap_account_management=off`) : un e-mail autorisé par
  Cloudflare mais inconnu est créé **auto en `actif`**.
- **Cloisonnement** : `titres` et `listes` portent `compte_id` ; tout le reste
  hérite via `titre_id`. Chaque requête métier filtre par `auth.compte_courant_id()`
  (impersonation-aware). Écritures gardées par `_owns()`.
- **Impersonation** (« voir en tant que ») : `cap_profiles=super_admin`.
- Permissions par site dans `config.json` (`cap_*`), preset « perso ».

## Architecture (`panel/`)

- `app.py` — création de l'app Flask + enregistrement des blueprints.
- `config.py` — config (`PANEL_CONFIG`, défauts, surcharge env, clés `cf_*`/`cap_*`).
- `settings_store.py` — réglages éditables (clé TMDB…) inscriptibles à l'exécution.
- `context.py` — accès partagé (config, client TMDB).
- `auth.py` — Cloudflare JWT + diagnostic, sessions `compte_id`/`role`,
  impersonation, `compte_courant_id()`, décorateurs.
- `permissions.py` — capabilities par site (`off`/`membre`/`super_admin`).
- `db.py` — SQLite par thread ; schéma `comptes`/`audit`/`app_settings` +
  `compte_id` ; `bootstrap_accounts()` (amorce super-admin + migration) ; `audit()`.
- `tmdb.py` — client de l'API TMDB.
- `routes/` — `pages`, `auth_routes` (gateway), `accounts_routes` (comptes +
  impersonation + Cloudflare/diagnostic), `library`, `titles`, `discover`,
  `lists`, `alerts`, `people`, `stats`, `settings`.
- `services/` — `posters`, `sync` (upsert par compte), `statistics` (par compte),
  `notifications`, `scheduler`.
- `static/` — `style.css`, `app.js`, `fonts.css`, `logo.svg`, `favicon.svg`, `sw.js`.
- `templates/` — `index.html`, `login.html`, `forgot.html`, écrans d'auth
  (`demande`, `attente`, `refus`, `bloque`), `comptes.html`.

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

## Hors périmètre

Animés, notation/avis, notifications e-mail, statistiques par période,
chronologie manuelle (remplacée par les listes). *(Le multi-utilisateurs,
d'abord hors v1, est intégré en v2 — voir « Auth v2 » ci-dessus.)*
