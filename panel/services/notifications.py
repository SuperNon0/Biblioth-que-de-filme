"""Envoi des notifications : Discord (via botpanel).

- **Discord** : on appelle l'API de botpanel `POST {url}/api/notify` avec un
  slug pré-configuré côté botpanel et des ``vars`` qui remplissent le modèle.
  Aucun jeton requis.

Toutes les fonctions lisent la configuration via ``settings_store`` : elles
doivent donc être appelées dans un contexte d'application Flask.
"""
import json
import logging
import urllib.error
import urllib.request

import settings_store

log = logging.getLogger("cinetheque.notifications")

# Slug botpanel à utiliser selon le type d'événement.
SLUG_KEYS = {
    "episode": "botpanel_slug_episode",
    "cine": "botpanel_slug_cine",
    "streaming": "botpanel_slug_streaming",
}

# Logo du site (PNG public, hébergé sur GitHub → joignable par Discord). Envoyé
# dans chaque notification comme variable {var:logo} : à mettre dans le champ
# « Thumbnail » de botpanel pour une petite icône cinéthèque dans l'embed.
LOGO_URL = ("https://raw.githubusercontent.com/SuperNon0/"
            "Biblioth-que-de-filme/main/panel/static/logo.png")


def _post(url, data=None, headers=None, timeout=8):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def send_discord(kind, variables=None):
    """Déclenche la notification botpanel correspondant au type d'événement.

    Contrat botpanel : ``POST {url}/api/notify`` avec ``{"id": slug, "vars": {…}}``.
    Le contenu du message est le template configuré côté botpanel ; les ``vars``
    remplissent ses emplacements ``{var:nom}``. Aucun jeton requis.
    """
    if not settings_store.get("notif_discord_enabled"):
        return False
    base = (settings_store.get("botpanel_url") or "").rstrip("/")
    slug = settings_store.get(SLUG_KEYS.get(kind, "")) or ""
    if not base or not slug:
        return False
    payload = json.dumps({"id": slug, "vars": variables or {}}).encode()
    try:
        _post(f"{base}/api/notify", data=payload,
              headers={"Content-Type": "application/json"})
        return True
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.warning("Envoi Discord (botpanel) échoué : %s", exc)
        return False


def notify(kind, title, message, variables=None):
    """Envoie l'événement sur Discord (si activé). Renvoie les canaux OK.

    ``title`` / ``message`` restent dans la signature pour la journalisation et
    d'éventuels futurs canaux ; Discord est piloté par ``kind`` + ``variables``
    (namespace ``vars`` côté botpanel). On ajoute automatiquement ``logo`` à
    toutes les notifications.
    """
    vars_ = dict(variables or {})
    vars_.setdefault("logo", LOGO_URL)
    ok = []
    if send_discord(kind, vars_):
        ok.append("discord")
    return ok


def test():
    """Envoie une notification de test sur les canaux activés.

    Pour Discord, on choisit le **premier slug configuré** (épisode, ciné ou
    streaming) : le test fonctionne quel que soit celui qu'on a rempli. Les
    variables couvrent tous les modèles pour que n'importe lequel s'affiche.
    """
    kind = next((k for k in ("episode", "cine", "streaming")
                 if settings_store.get(SLUG_KEYS[k])), "episode")
    return notify(
        kind, "cinéthèque — test",
        "🎬 Notification de test depuis cinéthèque. Tout fonctionne !",
        {"serie": "Série de test", "code": "S01E01",
         "titre": "Épisode pilote", "saison": "1", "episode": "1",
         "canal": "cinéma", "plateformes": "Netflix", "type": "test",
         # Affiche d'exemple (publique TMDB) pour tester l'image dans botpanel.
         "affiche": "https://image.tmdb.org/t/p/w500/qhb1qOilapbapxWQn9jtRCMwXJF.jpg",
         "image": "https://image.tmdb.org/t/p/w500/qhb1qOilapbapxWQn9jtRCMwXJF.jpg"})
