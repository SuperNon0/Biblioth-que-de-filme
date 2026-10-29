"""Statistiques du profil (temps passé, compteurs, genres, par année)."""
import re

from flask import Blueprint, jsonify, request

import auth
from services import statistics

bp = Blueprint("stats", __name__, url_prefix="/api")


@bp.get("/stats")
@auth.login_required
def stats():
    return jsonify(statistics.resume(auth.compte_courant_id()))


@bp.get("/journal")
@auth.login_required
def journal():
    """Historique de visionnage : chaque marquage (film / série / saison /
    épisode) avec son affiche et son horodatage (date + heure), du + récent.

    Chaque épisode porte sa saison, son numéro et sa durée, chaque film sa
    durée : le journal se regroupe en séances (« Silo · S1 · É1 → É4 ·
    4 épisodes · 3 h 49 »). ``avant`` (horodatage) donne la page suivante."""
    import db
    limite = min(max(request.args.get("limite", 300, type=int), 1), 1000)
    avant = request.args.get("avant", type=int)
    cond, params = "t.compte_id = ?", [auth.compte_courant_id()]
    if avant:
        cond += " AND j.cree < ?"
        params.append(avant)
    events = db.q(
        f"""SELECT j.id, j.type, j.label, j.cree,
                   t.id AS titre_id, t.titre, t.affiche, t.type AS media, t.duree AS duree_titre
            FROM journal j JOIN titres t ON t.id = j.titre_id
            WHERE {cond}
            ORDER BY j.cree DESC, j.id DESC LIMIT ?""",
        params + [limite + 1])
    suite = len(events) > limite
    events = events[:limite]
    series = sorted({e["titre_id"] for e in events if e["type"] == "episode"})
    durees = {}
    for i in range(0, len(series), 500):  # limite de variables SQLite
        lot = series[i:i + 500]
        for r in db.q(f"SELECT titre_id, saison, numero, duree FROM episodes "
                      f"WHERE titre_id IN ({','.join('?' * len(lot))})", lot):
            durees[(r["titre_id"], r["saison"], r["numero"])] = r["duree"]
    for e in events:
        duree_titre = e.pop("duree_titre")
        if e["type"] == "film":
            e["duree"] = duree_titre
        elif e["type"] == "episode":
            m = re.match(r"S(\d+)E(\d+)", e.get("label") or "")
            if m:
                e["saison"], e["numero"] = int(m.group(1)), int(m.group(2))
                e["duree"] = durees.get((e["titre_id"], e["saison"], e["numero"]))
    return jsonify(events=events, suite=suite)


@bp.delete("/journal/<int:event_id>")
@auth.login_required
def del_journal(event_id):
    """Supprime une entrée du journal (correction), sans toucher aux compteurs."""
    import db
    if not db.run_n("DELETE FROM journal WHERE id = ? AND titre_id IN "
                    "(SELECT id FROM titres WHERE compte_id = ?)",
                    (event_id, auth.compte_courant_id())):
        return jsonify(error="Entrée introuvable."), 404
    return jsonify(ok=True)
