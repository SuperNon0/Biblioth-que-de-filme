# Authentification v2 — multi-comptes à données cloisonnées

Résumé de ce que fait le code (`panel/auth.py`, `panel/permissions.py`,
`panel/routes/auth_routes.py`, `panel/routes/accounts_routes.py`). Les numéros
de section sont ceux cités dans les commentaires du code.

## §1 Deux couches

- **Cloudflare Access** est le portier : il décide quels e-mails peuvent
  *frapper à la porte* (règle Zero Trust).
- **L'application** gère le reste : rôles, état des comptes, données de chacun.

Derrière Cloudflare, la connexion est automatique (`cloudflare_sso()`, réglable
par `cf_sso_enabled`). En accès direct par l'IP locale, le mot de passe du
super-admin de base reste exigé (`allow_local_login`).

## §2 Rôles

- `super_admin` : toi. Le **super-admin de base** est celui qui a un mot de
  passe local ; il est amorcé au démarrage (`db.bootstrap_accounts()`).
- `membre` : un compte ordinaire, qui ne voit que sa bibliothèque.

Le dernier super-admin est indestructible (ni supprimé, ni rétrogradé).

## §3 États d'un compte

`pending` (demande en attente) → `actif`, ou `refused` / `bloque`. Seul un
compte `actif` entre ; les autres voient l'écran correspondant (`demande`,
`attente`, `refus`, `bloque`). Un super-admin non actif perd ses droits.

## §4 Site « perso » ou « géré » : les capabilities

Chaque fonction sensible a un niveau requis, `off`, `membre` ou `super_admin`,
fixé par `cap_<clé>` dans `config.json` (ou la variable d'environnement
correspondante) :

| Clé | Rôle | Preset « perso » |
|-----|------|------------------|
| `cap_account_management` | demandes d'accès, validation, blocage, suppression | `off` |
| `cap_profiles` | voir les profils, « voir en tant que » | `super_admin` |
| `cap_admin_password` | changer le mot de passe admin | `super_admin` |
| `cap_site_update` | bouton « Mettre à jour le site » | `super_admin` |

`cap_account_management=off` fait du site un site **perso** : un e-mail
autorisé par Cloudflare mais inconnu est créé directement en `actif`.

## §5 Gestion des comptes

Écran **Paramètres → Comptes & profils** (`/parametres/comptes`). Supprimer un
compte supprime toutes ses données (titres, listes, et ce qui en dépend).
Seul le super-admin de base peut changer un rôle.

## §6 Impersonation (« voir en tant que »)

Un super-admin peut consulter le compte d'un membre actif (jamais d'un autre
super-admin). Toutes les requêtes métier passent par
`auth.compte_courant_id()`, qui renvoie le compte consulté. Le journal d'audit
garde l'auteur réel (`auth.acteur()`). Pas de changement de mot de passe
pendant une impersonation.

## §7 Cloisonnement des données

`titres` et `listes` portent `compte_id` ; épisodes, visionnages, alertes,
journal et éléments de liste en héritent par `titre_id` / `liste_id`. Chaque
lecture filtre sur le compte courant, chaque écriture vérifie la propriété
(`_owns()`).

## §8 Protection des écritures (anti-CSRF)

Avant même l'auto-connexion Cloudflare, toute requête qui écrit (POST, PATCH,
DELETE) est refusée si le navigateur la signale comme venue d'un autre site
(`Sec-Fetch-Site: cross-site` ou `same-site`). Si le navigateur n'envoie pas
cet en-tête, les appels `/api/*` doivent porter `X-Cinetheque: 1`, que seul le
JavaScript du site pose (`api()` dans `app.js`). Le serveur MCP (`/mcp`) a sa
propre clé et n'est pas concerné.

## §9 Sécurité de l'en-tête Cloudflare

### §9.1 Jamais l'e-mail seul

L'en-tête `Cf-Access-Authenticated-User-Email` est falsifiable si l'origine est
joignable hors Cloudflare. On vérifie le JWT `Cf-Access-Jwt-Assertion` contre
les clés publiques de l'équipe (`<équipe>.cloudflareaccess.com`), avec `aud` et
`iss`. Le nom d'équipe est contrôlé (lettres, chiffres, tirets) : il sert à
construire l'URL des clés.

### §9.2 Mot de passe local

Hash `pbkdf2:sha256` (lisible par toutes les versions de Werkzeug). Après un
échec, le mot de passe suivant n'est examiné qu'au bout de 1, 2, 4… jusqu'à
30 s ; chaque échec est inscrit au journal d'audit (`login_echec`). Oubli :
`sudo bash /opt/cinetheque/scripts/reset-admin-password.sh`.

## §10 Connecteur Claude (MCP)

Clé API dédiée, générée dans Paramètres et gardée en base sous forme
d'empreinte seulement. Les outils agissent au nom du super-admin de base et
sont journalisés avec l'auteur « mcp ». Voir [mcp.md](mcp.md).
