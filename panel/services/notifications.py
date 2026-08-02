"""Envoi des notifications : Discord (via botpanel) et ntfy (push mobile).

- **Discord** : on appelle l'API de botpanel `POST {url}/api/notify` avec un
  slug pré-configuré côté botpanel. On envoie aussi ``title`` et ``message`` :
  le botpanel actuel les ignore (déclenchement par slug), une future version
  pourra les utiliser pour un contenu dynamique. Aucun jeton requis.
- **ntfy** : push direct sur le téléphone avec le **texte complet** (titre
  exact du film/épisode) — contenu dynamique.

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


def _post(url, data=None, headers=None, timeout=8):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def send_discord(kind, title, message):
    """Déclenche la notification botpanel correspondant au type d'événement."""
    if not settings_store.get("notif_discord_enabled"):
        return False
    base = (settings_store.get("botpanel_url") or "").rstrip("/")
    slug = settings_store.get(SLUG_KEYS.get(kind, "")) or ""
    if not base or not slug:
        return False
    payload = json.dumps({"id": slug, "title": title, "message": message}).encode()
    try:
        _post(f"{base}/api/notify", data=payload,
              headers={"Content-Type": "application/json"})
        return True
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.warning("Envoi Discord (botpanel) échoué : %s", exc)
        return False


def send_ntfy(title, message):
    """Envoie un push ntfy avec le contenu dynamique complet."""
    if not settings_store.get("notif_ntfy_enabled"):
        return False
    base = (settings_store.get("ntfy_url") or "https://ntfy.sh").rstrip("/")
    topic = (settings_store.get("ntfy_topic") or "").strip()
    if not topic:
        return False
    headers = {"Content-Type": "text/plain; charset=utf-8"}
    # L'en-tête HTTP ne supporte que le latin-1 : si le titre a des accents,
    # on le laisse dans le corps et on met un titre ASCII de repli.
    try:
        title.encode("latin-1")
        headers["Title"] = title
    except (UnicodeEncodeError, AttributeError):
        headers["Title"] = "cinetheque"
        message = f"{title}\n{message}"
    try:
        _post(f"{base}/{topic}", data=message.encode("utf-8"), headers=headers)
        return True
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.warning("Envoi ntfy échoué : %s", exc)
        return False


def notify(kind, title, message):
    """Envoie l'événement sur tous les canaux activés. Renvoie les canaux OK."""
    ok = []
    if send_discord(kind, title, message):
        ok.append("discord")
    if send_ntfy(title, message):
        ok.append("ntfy")
    return ok


def test():
    """Envoie une notification de test sur les canaux activés."""
    return notify("episode", "cinéthèque — test",
                  "🎬 Notification de test depuis cinéthèque. Tout fonctionne !")
