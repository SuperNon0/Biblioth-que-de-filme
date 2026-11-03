"""« Annuler » pendant quelques secondes après une action.

Une écriture annulable (marquer vu, à voir, épisode, saison, retirer un titre…)
note dans un ``Lot`` ce qu'il faudra rejouer pour revenir en arrière : valeurs
d'avant de quelques colonnes, lignes ajoutées à supprimer, lignes supprimées à
remettre. ``enregistrer`` range le lot en mémoire et renvoie un jeton, que
l'interface rend à ``POST /api/undo`` si l'on touche « Annuler ».

Les jetons sont gardés en mémoire (perdus au redémarrage), liés au compte qui a
agi, et expirent au bout d'une minute : l'interface ne propose « Annuler » que
pendant 5 secondes.
"""
import secrets
import threading
import time

import db

DUREE = 60
_MAX = 200  # garde-fou mémoire
_STORE = {}
_LOCK = threading.Lock()

# Seules ces tables peuvent être touchées par une annulation.
_TABLES = {"titres", "episodes", "visionnages", "journal", "liste_items", "alertes"}


class Lot:
    """Opérations inverses d'une action, rejouées de la dernière à la première."""

    def __init__(self):
        self.ops = []

    def colonnes(self, table, row_id, cols):
        """Retient la valeur actuelle de ``cols`` (à remettre en cas d'annulation)."""
        row = db.q1(f"SELECT {', '.join(cols)} FROM {table} WHERE id = ?", (row_id,))
        if row:
            self.ops.append(("update", table, row_id, row))

    def episodes(self, titre_id, ids=None):
        """Retient l'état vu / nombre de vues des épisodes d'une série."""
        rows = db.q("SELECT id, vu, nb_vues, derniere_vue FROM episodes WHERE titre_id = ?",
                    (titre_id,))
        for r in rows:
            if ids is None or r["id"] in ids:
                rid = r.pop("id")
                self.ops.append(("update", "episodes", rid, r))

    def ajoute(self, table, row_id):
        """Une ligne ajoutée par l'action : l'annulation la supprime."""
        if row_id:
            self.ops.append(("delete", table, row_id, None))

    def supprime(self, table, rows):
        """Des lignes que l'action va supprimer : l'annulation les remet."""
        for r in rows:
            self.ops.append(("insert", table, None, dict(r)))

    def retire_item(self, liste_id, titre_id):
        """Un titre ajouté à une liste : l'annulation l'en retire."""
        self.ops.append(("delete_item", "liste_items", None,
                         {"liste_id": liste_id, "titre_id": titre_id}))

    def titre_complet(self, titre_id):
        """Photo complète d'un titre et de tout ce qui en dépend (avant suppression).

        Le titre est noté en dernier : rejoué en premier, il existe déjà quand
        ses épisodes, visionnages… sont remis (clés étrangères)."""
        for table in ("liste_items", "journal", "alertes", "visionnages", "episodes"):
            self.supprime(table, db.q(f"SELECT * FROM {table} WHERE titre_id = ?",
                                      (titre_id,)))
        self.supprime("titres", db.q("SELECT * FROM titres WHERE id = ?", (titre_id,)))


def enregistrer(lot, compte_id):
    """Range le lot et renvoie son jeton (None si rien à annuler)."""
    if not lot.ops:
        return None
    jeton = secrets.token_urlsafe(12)
    now = time.time()
    with _LOCK:
        for k in [k for k, v in _STORE.items() if v[1] < now]:
            del _STORE[k]
        while len(_STORE) >= _MAX:
            _STORE.pop(next(iter(_STORE)))
        _STORE[jeton] = (compte_id, now + DUREE, lot.ops)
    return jeton


def annuler(jeton, compte_id):
    """Rejoue le lot à l'envers. Renvoie False si le jeton est inconnu, expiré
    ou appartient à un autre compte."""
    with _LOCK:
        entree = _STORE.get(jeton)
        if not entree or entree[1] < time.time() or entree[0] != compte_id:
            return False
        del _STORE[jeton]
    conn = db.connect()
    try:
        for op, table, row_id, data in reversed(entree[2]):
            if table not in _TABLES:
                continue
            if op == "update":
                cols = list(data)
                conn.execute(f"UPDATE {table} SET {', '.join(c + ' = ?' for c in cols)} "
                             f"WHERE id = ?", [data[c] for c in cols] + [row_id])
            elif op == "delete":
                conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
            elif op == "insert":
                cols = list(data)
                conn.execute(f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) "
                             f"VALUES ({', '.join('?' * len(cols))})", [data[c] for c in cols])
            elif op == "delete_item":
                conn.execute("DELETE FROM liste_items WHERE liste_id = ? AND titre_id = ?",
                             (data["liste_id"], data["titre_id"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return True
