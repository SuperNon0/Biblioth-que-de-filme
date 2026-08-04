# Notifications — guide complet (Discord)

cinéthèque peut te prévenir automatiquement sur **Discord** quand :

- un **nouvel épisode** d'une série que tu suis est diffusé ;
- un film sous **alerte** sort **au cinéma** ;
- un film sous **alerte** devient **disponible en streaming**.

> **En bref :** cinéthèque **n'envoie rien à Discord directement**. Il appelle
> l'API d'un outil tiers, **botpanel**, qui poste le message sur Discord.
> cinéthèque envoie juste un *slug* (l'identifiant d'un modèle créé dans
> botpanel) et des *variables* qui remplissent ce modèle.

---

## 1. Comment ça marche (sous le capot)

Un **planificateur** tourne en tâche de fond (`panel/services/scheduler.py`) et
se réveille **toutes les 6 heures**. À chaque cycle, si Discord est activé, il :

1. **Ré-synchronise les épisodes** des séries en statut *En cours* ou *À voir*,
   puis notifie les épisodes **déjà diffusés** (`date_diff ≤ aujourd'hui`) qui ne
   l'ont pas encore été.
2. Passe en revue les **alertes de sortie** (posées depuis l'onglet *Futur*) et
   notifie celles dont la condition est remplie (film sorti au ciné, ou plateforme
   de streaming détectée).

**Anti-spam garanti** : chaque événement n'est notifié **qu'une seule fois**.
- Épisodes : colonne `episodes.notifie` (les épisodes déjà sortis au moment où
  tu ajoutes une série sont marqués « déjà notifiés », donc pas de rafale).
- Alertes : colonne `alertes.vue`.

Le thread ne plante jamais : toute erreur (TMDB injoignable, botpanel down…) est
seulement journalisée, et sera retentée au cycle suivant.

### Le contrat réseau

```
POST {URL_BOTPANEL}/api/notify
Content-Type: application/json

{ "id": "<slug>", "vars": { "nom": "valeur", … } }
```

- `id` = le **slug** du modèle créé dans botpanel.
- `vars` = les variables qui remplissent les emplacements `{var:nom}` du modèle.
- **Aucun jeton d'authentification** n'est requis → voir la section *Sécurité*.

---

## 2. Réglages côté cinéthèque (Paramètres → Notifications)

| Champ | À remplir avec |
|-------|----------------|
| ☑️ **Discord (via botpanel)** | Coche pour activer les notifications |
| **URL botpanel** | L'adresse de ton botpanel, ex. `http://192.168.1.50:8080` (sans `/` final) |
| **slug épisode** | Le slug du modèle « nouvel épisode » créé dans botpanel |
| **slug ciné** | Le slug du modèle « film au cinéma » |
| **slug streaming** | Le slug du modèle « film en streaming » |

Puis **Enregistrer** et **Tester l'envoi**.

> Les slugs sont **libres** : tu choisis n'importe quel identifiant dans botpanel
> à la création du modèle, et tu recopies **exactement le même** dans cinéthèque.
> Tu n'es pas obligé de remplir les trois : seuls les événements dont le slug est
> renseigné seront envoyés.

---

## 3. Les 3 modèles à créer dans botpanel

Dans botpanel → **Notifications**, crée 3 notifications. Pour chacune : choisis
un **slug**, colle le **Titre** et le **Message** ci-dessous (avec leurs
emplacements `{var:…}`), et recopie le slug dans cinéthèque.

La syntaxe `{var:nom}` insère la variable ; `{var:nom|valeur par défaut}` affiche
la valeur de repli si la variable est absente.

> **Afficher l'affiche du film / de la série.** Chaque notification envoie aussi
> une variable `affiche` (URL publique du poster TMDB) et `image` (vignette de
> l'épisode pour les séries, poster sinon). Si ton botpanel permet de définir une
> **image / miniature d'embed**, mets-y `{var:affiche}` (ou `{var:image}`) : tu
> recevras la notification Discord **avec le poster**. Si botpanel ne gère pas les
> images, ces variables sont simplement ignorées.
>
> **Comment savoir si ton botpanel gère les images ?** Aucune modification de
> cinéthèque n'est nécessaire (l'image est déjà envoyée) — tout se règle côté
> botpanel :
> 1. Dans l'éditeur de notification de botpanel, cherche un champ **Image**,
>    **Thumbnail / Miniature**, **Embed image** ou **Média**. S'il existe, mets-y
>    `{var:affiche}`. Sinon, ta version ne gère pas les images.
> 2. **Le plus rapide : teste.** Mets `{var:affiche}` dans le champ image, puis
>    clique **« Tester l'envoi »** dans cinéthèque (le test envoie une vraie
>    affiche d'exemple). Si l'image apparaît sur Discord → c'est bon ; sinon,
>    botpanel ne l'affiche pas.
> 3. En dernier recours, la doc de botpanel (`docs/API.md` de son dépôt) indique
>    si l'API `/api/notify` accepte une image.

---

### 3.1 📺 Nouvel épisode d'une série

**Quand :** un épisode d'une série *En cours* / *À voir* vient d'être diffusé.

**Variables envoyées :**

| Variable | Signification | Exemple |
|----------|---------------|---------|
| `serie` | Nom de la série | `The Last of Us` |
| `code` | Code saison/épisode | `S02E03` |
| `titre` | Nom de l'épisode (peut être vide) | `Le sentier` |
| `saison` | Numéro de saison | `2` |
| `episode` | Numéro d'épisode | `3` |
| `affiche` | Poster de la série (URL TMDB) | `https://image.tmdb.org/…jpg` |
| `image` | Vignette de l'épisode (URL TMDB) | `https://image.tmdb.org/…jpg` |

**À coller dans botpanel** (slug conseillé : `cinetheque_episode`)

> **Titre :** `📺 {var:serie}`
> **Message :** `Nouvel épisode {var:code} — {var:titre|à regarder} 🍿`
> **Image / miniature** (si botpanel le permet) : `{var:affiche}`

**Ce que tu reçois sur Discord :**

> **📺 The Last of Us**
> Nouvel épisode S02E03 — Le sentier 🍿

---

### 3.2 🎬 Film qui sort au cinéma

**Quand :** un film sous alerte « cinéma » atteint sa date de sortie.

**Variables envoyées :**

| Variable | Signification | Exemple |
|----------|---------------|---------|
| `titre` | Nom du film | `Dune : Deuxième partie` |
| `canal` | Toujours `cinéma` | `cinéma` |
| `affiche` | Poster du film (URL TMDB) | `https://image.tmdb.org/…jpg` |

**À coller dans botpanel** (slug conseillé : `cinetheque_cine`)

> **Titre :** `🎬 {var:titre}`
> **Message :** `C'est sorti — maintenant au {var:canal} ! 🎟️`
> **Image / miniature** (si botpanel le permet) : `{var:affiche}`

**Ce que tu reçois sur Discord :**

> **🎬 Dune : Deuxième partie**
> C'est sorti — maintenant au cinéma ! 🎟️

---

### 3.3 📺 Film disponible en streaming

**Quand :** un film sous alerte « streaming » devient disponible sur une
plateforme (détecté via TMDB).

**Variables envoyées :**

| Variable | Signification | Exemple |
|----------|---------------|---------|
| `titre` | Nom du film | `Oppenheimer` |
| `plateformes` | 1 à 3 plateformes détectées | `Netflix, Canal+` |
| `affiche` | Poster du film (URL TMDB) | `https://image.tmdb.org/…jpg` |

**À coller dans botpanel** (slug conseillé : `cinetheque_streaming`)

> **Titre :** `📺 {var:titre}`
> **Message :** `Disponible en streaming sur {var:plateformes|une plateforme} 🎬`
> **Image / miniature** (si botpanel le permet) : `{var:affiche}`

**Ce que tu reçois sur Discord :**

> **📺 Oppenheimer**
> Disponible en streaming sur Netflix, Canal+ 🎬

---

## 4. La notification de test

Le bouton **« Tester l'envoi »** (Paramètres → Notifications) envoie un message
de test. Il utilise le **premier slug renseigné** (épisode, sinon ciné, sinon
streaming) — donc le test marche même si tu n'as rempli qu'un seul slug.

Les variables de test couvrent tous les modèles, donc peu importe le slug testé,
il s'affichera correctement. Exemple avec le modèle « épisode » :

> **📺 Série de test**
> Nouvel épisode S01E01 — Épisode pilote 🍿

Si le test échoue : « *Aucun canal activé/configuré, ou envoi échoué.* » →
vérifie que la case est cochée, que l'URL et au moins un slug sont remplis, et
que botpanel est joignable depuis le serveur cinéthèque.

---

## 5. Récapitulatif du contrat (référence développeur)

| Événement | Slug (réglage) | `kind` interne | Variables `vars` |
|-----------|----------------|----------------|------------------|
| Nouvel épisode | slug épisode | `episode` | `serie`, `code`, `titre`, `saison`, `episode`, `affiche`, `image` |
| Film au cinéma | slug ciné | `cine` | `titre`, `canal`, `affiche`, `image` |
| Film en streaming | slug streaming | `streaming` | `titre`, `plateformes`, `affiche`, `image` |

Les URLs `affiche` / `image` pointent vers `image.tmdb.org` (publiques, joignables
par Discord). L'affiche locale mise en cache par l'app n'est **pas** utilisée ici
car elle n'est pas accessible depuis l'extérieur.

Code de référence : `panel/services/notifications.py` (envoi) et
`panel/services/scheduler.py` (détection + déclenchement).

---

## 6. Dépannage

| Symptôme | Piste |
|----------|-------|
| Le test dit « Aucun canal activé/configuré » | Case décochée, URL/slug vides, ou botpanel injoignable. |
| Discord ne reçoit rien | URL botpanel fausse, slug non identique des deux côtés, ou botpanel inaccessible depuis le serveur. |
| Aucune notif d'épisode ne part | Vérifie que la série est en *En cours* ou *À voir* (les séries *Vu* ne sont pas surveillées) et que l'épisode est bien **déjà diffusé**. Le cycle passe toutes les 6 h. |
| Rafale de notifications au premier ajout | Ne devrait pas arriver : les épisodes déjà sortis sont marqués « notifiés » à l'ajout. Signale-le si tu l'observes. |
| Notifs en double | Chaque événement est marqué (`notifie` / `vue`) après envoi ; un doublon indique un bug — à signaler. |

---

## 7. Sécurité

- L'API botpanel `/api/notify` est appelée **sans authentification**. Garde
  botpanel sur ton **réseau local** (ou derrière un VPN / tunnel Cloudflare),
  jamais exposé nu sur Internet.
- cinéthèque ne stocke aucun jeton Discord : toute la logique Discord vit dans
  botpanel.
