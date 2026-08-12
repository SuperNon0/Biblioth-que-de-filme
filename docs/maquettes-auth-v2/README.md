# Maquettes — Authentification v2 (contrat visuel)

Ces maquettes sont le **rendu de référence** à reproduire **à la lettre** lors
de l'implémentation décrite dans [`../authentification-v2.md`](../authentification-v2.md).

Chaque page HTML utilise le **vrai thème** du site (`panel/static/style.css` +
`fonts.css`) plus une feuille complémentaire [`maquette.css`](maquette.css) —
à intégrer telle quelle dans `style.css`.

## Pages du parcours

| # | Maquette | Capture | Quand elle s'affiche |
|---|---|---|---|
| 1 | [`1-login-local.html`](1-login-local.html) | [png](captures/1-login-local.png) | Accès **local** (LAN) : login par mot de passe (super-admin). |
| 2 | [`2-demande.html`](2-demande.html) | [png](captures/2-demande.png) | Via Cloudflare, e-mail **autorisé mais inconnu** → bouton « Demander un accès ». |
| 3 | [`3-attente.html`](3-attente.html) | [png](captures/3-attente.png) | Compte **`pending`** : en attente de validation. |
| 4 | [`4-refus.html`](4-refus.html) | [png](captures/4-refus.png) | Compte **`refused`** : demande refusée. |
| 5 | [`5-bloque.html`](5-bloque.html) | [png](captures/5-bloque.png) | Compte **`bloqué`** : accès suspendu. |
| 6 | [`6-gestion.html`](6-gestion.html) | [png](captures/6-gestion.png) · [mobile](captures/6-gestion-mobile.png) | Paramètres → **Comptes** (super-admin) : valider / refuser / bloquer / supprimer / voir en tant que. |
| 7 | [`7-bandeau.html`](7-bandeau.html) | [png](captures/7-bandeau.png) | Bandeau **« voir en tant que »** (impersonation) actif. |

## Régénérer les captures

Ouvrir les fichiers HTML dans un navigateur, ou rendre via un script headless
(Chromium). Les captures fournies sont en `@2x` (haute résolution).

## Correspondance avec la spec

- Parcours & états → `authentification-v2.md` §2 et §4.
- Écran de gestion → §5.
- Bandeau / impersonation → §6.
- Modèle de données & sécurité → §7 à §9.
