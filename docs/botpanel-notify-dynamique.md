# Demande d'évolution botpanel — contenu dynamique sur `/api/notify`

## Contexte
Une autre appli auto-hébergée (**cinéthèque**, bibliothèque de films/séries)
utilise botpanel pour envoyer ses notifications Discord. Elle appelle déjà :

```
POST http://<botpanel>:8080/api/notify
Content-Type: application/json

{ "id": "<slug>", "title": "…", "message": "…" }
```

Aujourd'hui, `/api/notify` ne lit que `id` (le slug) et déclenche la
notification **pré-configurée** : le contenu (`title`, `message`) envoyé par
cinéthèque est **ignoré**. Résultat : le message Discord est générique, il ne
contient pas le titre précis (ex. « Breaking Bad S05E14 »).

## Ce qui est demandé
Faire en sorte que `/api/notify` **accepte des champs optionnels** `title` et
`message` (voire `fields`) qui, s'ils sont présents, **remplacent** le titre et
la description de l'embed avant l'envoi. En leur absence, comportement inchangé
(100 % rétrocompatible).

## Piste d'implémentation (FastAPI)
```python
# app/api/routes/ha_hook.py
class NotifyPayload(BaseModel):
    id: str
    title: str | None = None      # optionnel : remplace le titre de l'embed
    message: str | None = None    # optionnel : remplace la description

@router.post("/notify")
async def notify(payload: NotifyPayload):
    message = await send_notification(
        payload.id,
        overrides={"title": payload.title, "message": payload.message},
    )
    ...
```
```python
# app/bot/notifications.py — send_notification(slug, overrides=None)
# après avoir chargé la notif par slug, avant de construire l'embed :
if overrides:
    if overrides.get("title"):
        notif.title = overrides["title"]
    if overrides.get("message"):
        notif.message = overrides["message"]
```

## Points importants
- **Rétrocompatibilité** : si `title`/`message` sont absents, ne rien changer
  (Home Assistant et les appels existants continuent de marcher).
- **Sécurité** : `/api/notify` reste public (route machine) ; les overrides ne
  font que remplir le texte de l'embed déjà configuré, ils ne changent pas le
  salon ni le mode d'envoi.
- Côté cinéthèque : **aucun changement à faire**, elle envoie déjà
  `title` + `message` dans le payload. Dès que botpanel les prend en compte,
  les notifs Discord afficheront le titre exact automatiquement.

Merci ! 🙏
