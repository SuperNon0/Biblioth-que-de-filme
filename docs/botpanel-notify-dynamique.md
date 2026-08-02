# Demande d'évolution botpanel — contenu dynamique sur `/api/notify`

## Objectif (général, pour tous les projets)
Permettre à **n'importe quelle appli externe** (cinéthèque, un moniteur, un bot
CI…) d'injecter des **valeurs dynamiques** dans une notification botpanel, sans
que botpanel ait à connaître chaque projet. Le *design* de la notif (couleur,
salon, mode, boutons) reste **entièrement configuré dans botpanel** : seul le
contenu variable vient de l'appelant.

## Approche recommandée : notifications à **variables** (`vars`)

Dans l'éditeur de notification botpanel, on écrit des emplacements avec un
namespace `vars` (en s'appuyant sur le moteur de templates déjà présent) :

> Titre : `📺 {{ vars.serie }}`
> Message : `Nouvel épisode : {{ vars.code }} — {{ vars.titre }}`

L'appelant fournit ses valeurs :

```json
POST http://<botpanel>:8080/api/notify
Content-Type: application/json

{
  "id": "nouvel_episode",
  "vars": { "serie": "Breaking Bad", "code": "S05E14", "titre": "Ozymandias" }
}
```

botpanel substitue les `vars` dans le template, puis envoie.

### Pourquoi cette approche
- **Source unique de vérité** : le design reste dans botpanel ; les projets
  n'envoient que des données.
- **Générique et réutilisable** : chaque projet définit ses propres variables.
- **Cohérent** avec le moteur de templates existant (`{state:…}`, Jinja) : on
  ajoute juste `vars` au contexte de rendu.
- **Rétrocompatible** : pas de `vars` → emplacements vides, rien ne casse.

## Piste d'implémentation (FastAPI)
```python
# app/api/routes/ha_hook.py
class NotifyPayload(BaseModel):
    id: str
    vars: dict[str, str] | None = None      # valeurs dynamiques de l'appelant
    title: str | None = None                # (optionnel) raccourci d'override
    message: str | None = None              # (optionnel) raccourci d'override

@router.post("/notify")
async def notify(payload: NotifyPayload):
    message = await send_notification(
        payload.id,
        variables=payload.vars or {},
        overrides={"title": payload.title, "message": payload.message},
    )
    ...
```
```python
# app/bot/notifications.py — au rendu de l'embed, ajouter `vars` au contexte
# du moteur de templates (Jinja) :  render(text, vars=variables, state=…)
# puis appliquer overrides["title"] / overrides["message"] s'ils sont fournis.
```

### Raffinements utiles
- Variable manquante → vide (`{{ vars.x | default('') }}`).
- L'éditeur peut lister les variables détectées dans une notif (`{{ vars.* }}`).
- Logguer les `vars` reçues dans l'Historique pour déboguer.
- `/api/notify` reste public (route machine) ; `vars` ne remplit que du texte,
  ne change ni le salon ni le mode d'envoi.

## Variables envoyées par cinéthèque (à utiliser dans les templates)

cinéthèque appelle `/api/notify` avec trois slugs (configurés côté cinéthèque)
et ces `vars` :

| Événement (slug côté cinéthèque) | `vars` fournies |
|----------------------------------|-----------------|
| **nouvel épisode** | `serie`, `code` (ex. S05E14), `titre` (nom de l'épisode), `saison`, `episode` |
| **sortie ciné**    | `titre`, `canal` (= « cinéma ») |
| **sortie streaming** | `titre`, `plateformes` (ex. « Netflix, Disney+ ») |

cinéthèque envoie aussi `title` et `message` déjà rédigés (raccourci) : tu peux
soit utiliser les `vars` pour un rendu 100 % maîtrisé côté botpanel, soit
utiliser directement `{{ title }}` / `{{ message }}`.

Côté cinéthèque : **rien à changer** — elle envoie déjà `vars` + `title` +
`message`. Dès que botpanel les exploite, les notifs Discord afficheront le
contenu exact automatiquement.

Merci ! 🙏
