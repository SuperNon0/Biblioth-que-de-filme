# Intégration des notifications avec botpanel

cinéthèque envoie ses notifications Discord **via botpanel** (aucun code Discord
côté cinéthèque). Botpanel gère la mise en forme ; cinéthèque ne fait qu'appeler
son API avec un **slug** et des **variables**.

Référence complète de l'API : `docs/API.md` du dépôt **botpanel**.

## Ce que cinéthèque envoie

```
POST {BOTPANEL_URL}/api/notify
Content-Type: application/json

{ "id": "<slug>", "vars": { … } }
```

Le `BOTPANEL_URL` et les slugs se règlent dans **cinéthèque → Paramètres →
Notifications**. cinéthèque utilise **trois slugs** (un par type d'événement) :

| Événement | Réglage cinéthèque | Variables (`vars`) envoyées |
|-----------|--------------------|------------------------------|
| Nouvel épisode d'une série suivie | slug « épisode » | `serie`, `code` (ex. S05E14), `titre` (nom de l'épisode), `saison`, `episode` |
| Film qui sort au cinéma | slug « ciné » | `titre`, `canal` (= « cinéma ») |
| Film dispo en streaming | slug « streaming » | `titre`, `plateformes` (ex. « Netflix, Disney+ ») |

## Modèles de notifications à créer dans botpanel

Crée trois notifications dans botpanel (page Notifications), avec ces slugs et
des emplacements `{var:nom}` correspondants. Exemples :

**Slug `cinetheque_episode`**
> Titre : `📺 {var:serie}`
> Message : `Nouvel épisode {var:code}{var:titre| }`

**Slug `cinetheque_cine`**
> Titre : `🎬 {var:titre}`
> Message : `Maintenant au {var:canal} !`

**Slug `cinetheque_streaming`**
> Titre : `📺 {var:titre}`
> Message : `Disponible sur {var:plateformes|une plateforme}.`

*(Choisis les slugs que tu veux : reporte-les simplement dans les Paramètres de
cinéthèque. La syntaxe `{var:nom|défaut}` fournit une valeur de repli.)*

## Rappels
- Route `/api/notify` **sans authentification** → garde botpanel sur le réseau
  local ou derrière un tunnel/VPN.
- `vars` est optionnel côté botpanel ; les champs inconnus sont ignorés.
- **ntfy** (autre canal, réglé dans cinéthèque) reçoit déjà le **texte complet**
  dynamique, indépendamment de botpanel.
