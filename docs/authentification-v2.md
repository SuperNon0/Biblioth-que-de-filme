# Authentification v2 — comptes multi-utilisateurs

> **Statut : spécification.** Ce document décrit une évolution à implémenter.
> Il est destiné à un développeur qui reprendra le système de login actuel
> (`panel/auth.py`, compte `admin` unique) pour le transformer en un système
> multi-comptes avec validation par un super-admin, derrière Cloudflare Access.
>
> Le multi-utilisateurs était **hors périmètre v1** (voir `CLAUDE.md`). Cette
> spec le réintègre volontairement en v2.

---

## 1. Principe : deux couches de sécurité qui ne font pas la même chose

| Couche | Rôle | Ce qu'elle sait faire |
|---|---|---|
| **Cloudflare Zero Trust (Access)** | Portier e-mail | Laisser entrer / bloquer un e-mail Google. Rien d'autre. |
| **L'application (Flask)** | Profils, rôles, cycle de vie | Qui est admin, qui est en attente, qui est bloqué, qui voit quoi. |

**Règle d'or :** Cloudflare décide *qui peut frapper à la porte*. L'application
décide *ce qui se passe une fois la porte franchie*. Les **rôles** et le
**cycle de vie d'un compte** sont **toujours** gérés par l'app — Cloudflare ne
sait faire que « autorisé / refusé ».

### Modèle retenu (« Modèle A + gestion applicative »)

1. Le super-admin ajoute l'e-mail Google d'une personne dans **Cloudflare
   Zero Trust** (Access Policy). À partir de là, cette personne peut
   *atteindre* le site.
2. À sa première connexion, l'app ne la connaît pas encore → elle crée
   automatiquement une **demande d'accès** (compte à l'état `pending`) et
   affiche une **page d'attente**.
3. Un **super-admin / admin** voit la demande dans les Paramètres, et
   **accepte** ou **refuse**.
4. Ensuite, le super-admin peut **bloquer**, **supprimer**, **changer le rôle**
   ou **« voir en tant que »** n'importe quel compte.

---

## 2. Cycle de vie d'un compte (machine à états)

```
      (e-mail autorisé par Cloudflare, 1re connexion)
                        │
                        ▼
                   ┌─────────┐   refus    ┌──────────┐
                   │ pending │──────────▶ │ refused  │  → page de refus
                   │(attente)│            └──────────┘
                   └────┬────┘
              accepté   │
                        ▼
                   ┌─────────┐  bloquer   ┌──────────┐
                   │  actif  │──────────▶ │ bloqué   │  → page de blocage
                   │         │◀────────── │          │
                   └────┬────┘ débloquer  └──────────┘
                        │
                supprimer (hard delete)
                        │
                        ▼
              compte effacé → si la personne revient
              (toujours autorisée par Cloudflare), une
              nouvelle demande `pending` est recréée.
```

**États :** `pending`, `actif`, `refused`, `bloqué`.
La **suppression** efface la ligne (ou l'archive) ; l'utilisateur, s'il revient
via Cloudflare, retombe sur la page « demander un accès » qui recrée un
`pending`.

---

## 3. Rôles

| Rôle | Droits |
|---|---|
| `super_admin` | Tout. Seul à pouvoir : gérer les comptes (accepter/refuser/bloquer/supprimer), changer les rôles, « voir en tant que », se connecter **en local avec mot de passe**. Il en existe **au moins un**, non supprimable tant qu'il est le dernier. |
| `admin` | Peut accepter/refuser les demandes et gérer sa propre bibliothèque. Ne peut **pas** supprimer un super-admin ni s'auto-promouvoir. (Rôle optionnel — peut être fusionné avec `super_admin` si tu veux rester simple.) |
| `membre` | Utilise **sa** bibliothèque. Aucun accès à la gestion des comptes. |

> **Simplification conseillée pour un usage perso :** ne garder que
> `super_admin` (toi) + `membre`. Le rôle `admin` intermédiaire ajoute de la
> complexité pour peu de valeur tant que tu es seul aux commandes.

---

## 4. Parcours de connexion (les pages à créer)

### 4.1 Détection du canal d'entrée

- **Accès local / LAN** : l'en-tête `Cf-Access-Authenticated-User-Email` est
  **absent** → on présente la **page de login par mot de passe** (super-admin).
- **Accès via Cloudflare** : l'en-tête est **présent et vérifié** → connexion
  par e-mail Google, **sans mot de passe**.

### 4.2 Arbre de décision (connexion via Cloudflare)

```
e-mail Cloudflare reçu
   │
   ├─ e-mail inconnu en base ─────────▶ créer `pending` + page « Demande envoyée / en attente »
   │
   ├─ compte `pending` ───────────────▶ page « En attente de validation »
   │
   ├─ compte `refused` ───────────────▶ page « Votre demande a été refusée »
   │
   ├─ compte `bloqué` ────────────────▶ page « Votre accès a été suspendu »
   │
   └─ compte `actif` ─────────────────▶ accès à l'application (sa bibliothèque)
```

### 4.3 Pages à créer (templates)

| Page | Quand | Contenu |
|---|---|---|
| `login.html` (existe) | Accès local | Champ mot de passe (super-admin). |
| `attente.html` | `pending` | « Votre demande d'accès a bien été envoyée. Un administrateur doit la valider. » + bouton *Rafraîchir*. |
| `refus.html` | `refused` | « Un administrateur a refusé votre demande. » (pas de bouton retry, ou un bouton *Redemander* qui repasse en `pending`, au choix). |
| `bloque.html` | `bloqué` | « Votre accès a été suspendu par un administrateur. » |
| `demande.html` | e-mail inconnu | « Bienvenue *(e-mail)*. Cliquez pour demander un accès. » + bouton **Demander un accès** (crée le `pending`). |

> Ces pages doivent réutiliser le thème sombre doré (variables `:root` de
> `style.css`) et le logo, comme `login.html`.

---

## 5. Écran de gestion des comptes (Paramètres → « Comptes »)

Visible uniquement par `super_admin` (et `admin` selon les droits ci-dessus).

### 5.1 Section « Demandes en attente »
Liste des comptes `pending` : e-mail + date de la demande + boutons
**Accepter** / **Refuser**.

### 5.2 Section « Membres »
Pour chaque compte `actif`/`bloqué` :

- e-mail, rôle, date de création, dernière connexion ;
- **Bloquer / Débloquer** ;
- **Supprimer** (confirmation) ;
- **Changer le rôle** (membre ↔ admin) ;
- **« Voir en tant que »** (voir §6).

---

## 6. « Voir en tant que » (impersonation)

Le super-admin peut consulter la plateforme **comme si** il était un autre
utilisateur, avec la possibilité de **revenir en arrière** à tout moment, tout
en pouvant **interagir** (ajouter / supprimer / modifier) sur le profil de cet
utilisateur.

### Fonctionnement
- On stocke en session une paire : `user_id` (l'identité *effective*, celle
  impersonnée) et `impersonator_id` (le super-admin réel).
- Toutes les requêtes de données utilisent `user_id` effectif → le super-admin
  voit et modifie bien **les données de l'autre**.
- Un **bandeau permanent** en haut : « 👁️ Vous consultez le compte de
  *email* — [Revenir à mon compte] ».
- « Revenir » efface `impersonator_id` et restaure l'identité réelle.

### ⚠️ Précautions (importantes)
- **Journaliser** chaque entrée/sortie d'impersonation et chaque action faite
  pendant (dans le journal d'audit, §9). C'est un pouvoir sensible.
- Interdire l'auto-impersonation en cascade (pas d'impersonation dans
  l'impersonation).
- Un compte impersonné **ne peut pas** être un autre super-admin (évite les
  escalades) — au choix, mais recommandé.

---

## 7. Modèle de données (SQLite)

Nouvelle table `comptes` :

```sql
CREATE TABLE IF NOT EXISTS comptes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE,            -- e-mail Google (NULL pour le super-admin local seul)
    role          TEXT NOT NULL DEFAULT 'membre',  -- super_admin | admin | membre
    etat          TEXT NOT NULL DEFAULT 'pending', -- pending | actif | refused | bloque
    mdp_hash      TEXT,                   -- seulement pour un compte à login local (super-admin)
    cree          INTEGER,                -- timestamp de la demande
    valide        INTEGER,                -- timestamp d'acceptation
    derniere_cnx  INTEGER
);
```

### Impact majeur : cloisonner les données par utilisateur

> **C'est LE point d'architecture à trancher (voir §11).** Si chaque personne a
> « sa partie à elle » de la bibliothèque, alors **toutes** les tables de
> contenu doivent porter un propriétaire :
> `titres`, `visionnages`, `episodes`, `journal`, `listes`, `alertes`…
>
> Il faut ajouter `compte_id INTEGER REFERENCES comptes(id)` à ces tables et
> **filtrer chaque requête** par l'utilisateur effectif. C'est un chantier
> nettement plus lourd que la page de login elle-même.
>
> **Alternative légère :** bibliothèque **partagée** par tous les comptes
> actifs (tout le monde voit/édite la même collection), les comptes ne servant
> qu'au contrôle d'accès. Beaucoup moins de travail. À décider **avant** de
> commencer.

---

## 8. Endpoints API (proposition)

| Méthode | Route | Rôle requis | Effet |
|---|---|---|---|
| `POST` | `/api/access/request` | authentifié CF | Crée un `pending` pour l'e-mail courant. |
| `GET`  | `/api/comptes` | admin+ | Liste les comptes (+ demandes). |
| `POST` | `/api/comptes/<id>/valider` | admin+ | `pending` → `actif`. |
| `POST` | `/api/comptes/<id>/refuser` | admin+ | `pending` → `refused`. |
| `POST` | `/api/comptes/<id>/bloquer` | admin+ | `actif` → `bloque`. |
| `POST` | `/api/comptes/<id>/debloquer` | admin+ | `bloque` → `actif`. |
| `POST` | `/api/comptes/<id>/role` | super_admin | Change le rôle. |
| `DELETE` | `/api/comptes/<id>` | super_admin | Supprime le compte. |
| `POST` | `/api/comptes/<id>/impersonate` | super_admin | Démarre « voir en tant que ». |
| `POST` | `/api/impersonate/stop` | authentifié | Fin d'impersonation. |

Toutes les routes `/api/*` restent en `Cache-Control: no-store`.

---

## 9. Sécurité — à lire avant d'implémenter

1. **Ne jamais faire confiance à `Cf-Access-Authenticated-User-Email` si
   l'origine est joignable hors Cloudflare.** Un attaquant qui atteint le
   serveur en direct peut *forger* cet en-tête et se faire passer pour
   n'importe quel e-mail. Deux protections, au moins l'une des deux
   **obligatoire** :
   - **Vérifier le JWT** `Cf-Access-Jwt-Assertion` contre les clés publiques
     de ton équipe Cloudflare (`https://<team>.cloudflareaccess.com/cdn-cgi/access/certs`),
     et contrôler l'`aud` de l'application. C'est la vraie protection.
   - **Rendre l'origine injoignable sans Cloudflare** (tunnel `cloudflared`,
     pare-feu n'autorisant que les IP Cloudflare). L'accès local reste sur le
     LAN via mot de passe.
2. **Journal d'audit** : consigner acceptation, refus, blocage, suppression,
   changement de rôle, entrées/sorties d'impersonation (qui, quoi, quand).
3. **Le dernier super-admin est indestructible** : refuser sa suppression ou
   sa rétrogradation tant qu'il est seul, pour ne pas se verrouiller dehors.
4. **Session** : elle doit désormais porter `compte_id` + `role`
   (+ `impersonator_id` le cas échéant), pas seulement `logged_in`.
5. **Anti-force brute** sur le login local (déjà présent : `time.sleep(1)`).

---

## 10. Migration depuis l'existant

1. Créer la table `comptes`.
2. **Amorce** : insérer le super-admin actuel — reprendre `users.json`
   (`admin` + `mdp_hash`), `role='super_admin'`, `etat='actif'`, et y
   rattacher ton e-mail Google (celui de `cf_access_email`).
3. Remplacer la logique « `cf_access_email` = un seul e-mail » par la table
   `comptes` (l'e-mail autorisé n'est plus un réglage unique mais une ligne).
4. Adapter `login_required` : vérifier `session['compte_id']` + `etat == actif`.
5. Ajouter un décorateur `role_required('super_admin')` pour la gestion.
6. Si bibliothèque cloisonnée (§7) : ajouter `compte_id` aux tables de contenu
   et rattacher l'existant au super-admin, puis filtrer toutes les requêtes.

---

## 11. Découpage conseillé pour le développeur (lots)

| Lot | Contenu | Dépendance | Poids |
|---|---|---|---|
| **0. Décision** | Bibliothèque **partagée** ou **cloisonnée** par compte ? | — | bloquant |
| **1. Modèle** | Table `comptes`, migration, amorce super-admin. | 0 | moyen |
| **2. Auth** | JWT Cloudflare vérifié, session `compte_id`+`role`, décorateurs. | 1 | moyen |
| **3. Cycle de vie** | Pages attente/refus/blocage/demande + création `pending`. | 2 | moyen |
| **4. Gestion** | Écran Paramètres → Comptes (valider/refuser/bloquer/supprimer/rôle). | 2 | moyen |
| **5. Impersonation** | « Voir en tant que » + bandeau + audit. | 4 | léger |
| **6. Cloisonnement** *(si lot 0 = cloisonnée)* | `compte_id` sur toutes les tables + filtrage. | 1 | **lourd** |

> **Recommandation :** commencer par le lot **0** (la décision partagé vs
> cloisonné change tout le reste), puis 1→5. Le lot 6, s'il est retenu, est de
> loin le plus gros et gagne à être fait en dernier, isolément.
