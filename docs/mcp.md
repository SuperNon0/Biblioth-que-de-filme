# Connecteur Claude (serveur MCP)

Le serveur MCP permet à Claude de **tester et piloter cinéthèque en direct**,
comme tes connecteurs RecipeLog et BotPanel : vérifier que chaque écran
répond, consulter la bibliothèque, ajouter un film, marquer des épisodes, lancer
une mise à jour… Il est intégré au site (aucun service en plus à installer).

---

## Installation pas à pas

### 1. Mettre le site à jour

Une fois la PR fusionnée : **Paramètres → Mise à jour → « Mettre à jour le
site »**. Le serveur MCP est alors disponible à l'adresse `/mcp` de ton site.

### 2. Générer la clé API MCP

**Paramètres → Connecteur Claude (MCP) → « Générer une clé »** (réservé au
super-admin).

Le site affiche :

- la **clé** (`cine_…`) ;
- l'**URL du connecteur** : `https://<ton-site>/mcp/cine_…`.

⚠️ Copie l'URL tout de suite : la clé n'est **affichée qu'une seule fois**. Le
site n'en garde qu'une empreinte (SHA-256), impossible à relire. Clé perdue ?
Il suffit d'en générer une nouvelle (l'ancienne cesse aussitôt de marcher).

### 3. Ajouter le connecteur dans Claude

1. claude.ai → **Paramètres → Connecteurs → Ajouter un connecteur personnalisé**.
2. Nom : `cinéthèque`.
3. URL : colle l'**URL du connecteur** copiée à l'étape 2.
4. Laisse les options OAuth vides → **Ajouter**.

### 4. Vérifier

Dans une conversation, demande à Claude : *« Donne-moi l'état de cinéthèque
puis vérifie le site »*. Il appelle `etat_du_site` puis `verifier_site`, qui
ouvre chaque écran et renvoie son statut et son temps de réponse.

---

## Sécurité

- **Clé API dédiée** : distincte du mot de passe du site et de la clé TMDB.
  Sans clé valide, `/mcp` répond `401` (avec un léger délai contre les essais
  à l'aveugle).
- **Aucun secret dans le dépôt** : la clé est générée sur le serveur ; seule son
  empreinte est stockée en base (`app_settings.mcp_cle_hash`).
- **Révocation immédiate** : bouton « Révoquer » dans Paramètres.
- **Garde-fous** : suppression d'un titre, mise à jour du site et actions
  sensibles de `appel_api` (reset, import, comptes, mot de passe, tout `DELETE`)
  ne s'appliquent **que** si Claude passe `confirm="OUI"` ; sinon il reçoit un
  simple aperçu. Claude doit te demander ton accord avant.
- Générations / révocations de clé et mises à jour lancées par le MCP sont
  inscrites dans le journal d'audit.
- Accès réseau : le connecteur est appelé par les serveurs de Claude. Il passe
  par le même chemin que tes connecteurs RecipeLog et BotPanel. Si Claude
  reçoit une page de connexion au lieu d'une réponse, c'est que l'accès devant
  le site bloque `/mcp` : reprends le même réglage que pour RecipeLog.

La clé peut aussi être envoyée dans l'en-tête `Authorization: Bearer <clé>`
(pour un client MCP qui le permet) au lieu d'être dans l'URL.

---

## Les outils

| Outil | Rôle |
|---|---|
| `etat_du_site` | Version, dernier changement, heure de démarrage, TMDB configurée, taille de la bibliothèque. |
| `verifier_site` | Test en direct de ~20 écrans/API (statut + temps de réponse). Lecture seule. |
| `chercher` | Recherche TMDB (donne le `tmdb_id`). |
| `apercu_tmdb` | Fiche TMDB sans ajouter. |
| `lister_bibliotheque` | Bibliothèque filtrée (statut, type, genre, favori, titre, tri). |
| `voir_titre` | Fiche d'un titre (progression par saison ; `episodes=true` pour le détail). |
| `ajouter_titre` | Ajout depuis TMDB, ou manuel. |
| `modifier_titre` | Statut et/ou favori. |
| `supprimer_titre` | Suppression (**confirm="OUI"**). |
| `enregistrer_visionnage` | Vu / revu d'un film, à une date. |
| `marquer_episodes` | Un épisode, une saison ou toute la série. |
| `creer_alerte` | Alerte de sortie ciné / streaming. |
| `lister_listes`, `voir_liste`, `creer_liste`, `ajouter_a_liste`, `retirer_de_liste` | Listes. |
| `statistiques`, `journal` | Stats et historique de visionnage. |
| `suggestions`, `decouvrir`, `sorties_a_venir` | Découverte. |
| `reparer_donnees` | Réparation des incohérences (sans rien supprimer). |
| `appel_api` | Accès avancé à n'importe quelle route `/api/*` pour tester une fonction précise. |
| `mettre_a_jour_site` | Mise à jour GitHub + redémarrage (**confirm="OUI"**). |

Claude agit au nom du **super-admin de base** (ton compte) : il voit ta
bibliothèque, pas celle des autres membres.

---

## Fonctionnement (pour développer)

- `panel/routes/mcp.py` — point d'entrée `/mcp` : protocole MCP
  « Streamable HTTP » **sans état** (une requête JSON-RPC → une réponse JSON,
  pas de flux SSE ni de session à garder), vérification de la clé, et API de
  gestion de la clé pour Paramètres (`/api/mcp`, `/api/mcp/cle`).
- `panel/services/mcp_tools.py` — catalogue des outils. Chaque outil **rejoue
  une route `/api/*` du site dans le processus** (client de test Flask, aucun
  appel réseau), connecté en super-admin. Claude voit donc exactement ce que
  voit l'interface : mêmes règles, même cloisonnement, mêmes erreurs — et une
  correction dans une route profite aussitôt au MCP.
- Réponses allégées pour aller vite : listes limitées (50 par défaut), casting
  tronqué, épisodes résumés par saison sauf demande explicite.

**Ajouter un outil** : écrire `def mon_outil(args): return _ok("GET", "/api/…")`
dans `mcp_tools.py`, puis l'inscrire dans `TOOLS` avec une description et son
schéma (`_schema({...}, [obligatoires])`).

**Tester en local** :

```bash
curl -s -X POST http://localhost:8080/mcp \
  -H "Authorization: Bearer cine_…" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"verifier_site","arguments":{}}}'
```

## Dépannage

| Symptôme | Cause / solution |
|---|---|
| `401 Clé API MCP invalide` | Clé révoquée ou remplacée : génère-en une nouvelle et mets à jour l'URL du connecteur. |
| Page de connexion au lieu de JSON | L'accès devant le site bloque `/mcp` (voir « Sécurité »). |
| `verifier_site` signale des `502` TMDB | Clé TMDB absente ou invalide (Paramètres → Clé API TMDB). |
| `405` sur `/mcp` | Normal pour un `GET` : le serveur ne répond qu'en `POST`. |
