"""Base de données SQLite de cinéthèque.

Une seule base de fichier (``library.db``) contient toute la bibliothèque :
titres (films/séries), visionnages, saisons/épisodes, listes et alertes.
Le schéma est créé/complété au démarrage (idempotent) et versionné via
``PRAGMA user_version`` pour de futures migrations douces.

Aucune dépendance externe : le module ``sqlite3`` est fourni avec Python.
"""
import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA_VERSION = 1

# --- schéma ---------------------------------------------------------------
SCHEMA = """
-- Fondation multi-comptes (socle « site-base », auth v2 §7) ------------------
CREATE TABLE IF NOT EXISTS comptes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE,                   -- e-mail Google (NULL: super-admin local seul)
    role          TEXT NOT NULL DEFAULT 'membre',-- super_admin | membre
    etat          TEXT NOT NULL DEFAULT 'pending',-- pending | actif | refused | bloque
    mdp_hash      TEXT,                          -- uniquement pour le login local
    cree          INTEGER,
    valide        INTEGER,
    bloque        INTEGER,
    derniere_cnx  INTEGER
);

CREATE TABLE IF NOT EXISTS audit (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      INTEGER NOT NULL,
    acteur  TEXT,                                -- e-mail / id de celui qui agit
    action  TEXT NOT NULL,
    cible   TEXT,                                -- e-mail / id concerné
    detail  TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
    cle     TEXT PRIMARY KEY,
    valeur  TEXT
);

CREATE TABLE IF NOT EXISTS titres (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    compte_id     INTEGER REFERENCES comptes(id) ON DELETE CASCADE,  -- propriétaire (cloisonnement)
    tmdb_id       INTEGER,                       -- NULL si ajout manuel
    type          TEXT NOT NULL,                 -- 'film' | 'serie'
    titre         TEXT NOT NULL,
    titre_vo      TEXT,
    annee         INTEGER,
    date_sortie   TEXT,
    resume        TEXT,
    genres        TEXT,                          -- JSON: ["Action", ...]
    duree         INTEGER,                       -- minutes (films)
    affiche       TEXT,                          -- chemin local (cache) ou URL
    affiche_url   TEXT,                          -- URL TMDB publique (notifs Discord)
    fond          TEXT,
    bande_annonce TEXT,                          -- clé/URL YouTube
    note_tmdb     REAL,
    pays          TEXT,
    plateformes   TEXT,                          -- JSON: [{"nom","logo"}]
    casting       TEXT,                          -- JSON: [{"id","nom","personnage","photo"}]
    equipe        TEXT,                          -- JSON: [{"id","nom","poste","photo"}]
    nb_saisons    INTEGER,                       -- séries : nombre de saisons TMDB
    statut        TEXT DEFAULT 'a_voir',         -- vu|a_voir|en_cours
    favori        INTEGER DEFAULT 0,
    ajout_manuel  INTEGER DEFAULT 0,
    date_ajout    INTEGER,
    maj           INTEGER,
    UNIQUE(compte_id, tmdb_id, type)
);

CREATE TABLE IF NOT EXISTS visionnages (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    titre_id INTEGER NOT NULL REFERENCES titres(id) ON DELETE CASCADE,
    date     TEXT,                               -- 'YYYY-MM-DD' (plusieurs par jour possibles)
    cree     INTEGER
);

CREATE TABLE IF NOT EXISTS episodes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    titre_id     INTEGER NOT NULL REFERENCES titres(id) ON DELETE CASCADE,
    saison       INTEGER NOT NULL,
    numero       INTEGER NOT NULL,
    nom          TEXT,
    resume       TEXT,
    image        TEXT,
    duree        INTEGER,                        -- minutes
    date_diff    TEXT,                           -- date de diffusion
    vu           INTEGER DEFAULT 0,
    nb_vues      INTEGER DEFAULT 0,              -- revisionnages
    derniere_vue TEXT,
    notifie      INTEGER DEFAULT 0,             -- notification « nouvel épisode » envoyée
    UNIQUE(titre_id, saison, numero)
);

CREATE TABLE IF NOT EXISTS listes (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    compte_id INTEGER REFERENCES comptes(id) ON DELETE CASCADE,  -- propriétaire (cloisonnement)
    nom       TEXT NOT NULL,
    systeme   TEXT,                              -- 'a_voir'|'favoris' si liste système
    cree      INTEGER,
    UNIQUE(compte_id, systeme)
);

CREATE TABLE IF NOT EXISTS liste_items (
    liste_id INTEGER NOT NULL REFERENCES listes(id) ON DELETE CASCADE,
    titre_id INTEGER NOT NULL REFERENCES titres(id) ON DELETE CASCADE,
    rang     INTEGER DEFAULT 0,
    ajoute   INTEGER,
    PRIMARY KEY (liste_id, titre_id)
);

CREATE TABLE IF NOT EXISTS alertes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    titre_id INTEGER NOT NULL REFERENCES titres(id) ON DELETE CASCADE,
    canal    TEXT DEFAULT 'cine',                -- 'cine' | 'streaming'
    vue      INTEGER DEFAULT 0,
    cree     INTEGER,
    UNIQUE(titre_id, canal)
);

CREATE TABLE IF NOT EXISTS journal (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    titre_id INTEGER NOT NULL REFERENCES titres(id) ON DELETE CASCADE,
    type     TEXT,                               -- 'film'|'serie'|'saison'|'episode'
    label    TEXT,                               -- nom d'épisode / « Saison 2 » / …
    cree     INTEGER                             -- horodatage (date + heure)
);

CREATE INDEX IF NOT EXISTS idx_titres_statut  ON titres(statut);
CREATE INDEX IF NOT EXISTS idx_titres_type    ON titres(type);
CREATE INDEX IF NOT EXISTS idx_episodes_titre ON episodes(titre_id);
CREATE INDEX IF NOT EXISTS idx_vision_titre   ON visionnages(titre_id);
CREATE INDEX IF NOT EXISTS idx_journal_cree   ON journal(cree);
"""

_local = threading.local()
_DB_PATH = None


def init(db_path):
    """Prépare le chemin de la base et crée le schéma si besoin."""
    global _DB_PATH
    _DB_PATH = Path(db_path)
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    conn.executescript(SCHEMA)
    _migrate(conn)
    # Les listes système (« À voir »/« Favoris ») sont désormais créées PAR
    # compte (cloisonnement) via ensure_system_lists(), plus de seeding global.
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


SYSTEM_LISTS = (("a_voir", "À voir"), ("favoris", "Favoris"))


def ensure_system_lists(compte_id):
    """Crée les listes système (« À voir », « Favoris ») d'un compte si absentes."""
    conn = connect()
    now = int(time.time())
    for systeme, nom in SYSTEM_LISTS:
        conn.execute(
            "INSERT OR IGNORE INTO listes (compte_id, nom, systeme, cree) "
            "VALUES (?, ?, ?, ?)", (compte_id, nom, systeme, now))
    conn.commit()


def audit(action, acteur=None, cible=None, detail=None):
    """Journalise une action sensible (validation, blocage, impersonation…)."""
    run("INSERT INTO audit (ts, acteur, action, cible, detail) VALUES (?,?,?,?,?)",
        (int(time.time()), acteur, action, cible, detail))


def _backup_once(suffix="avant-comptes"):
    """Copie la base une seule fois avant la migration cloisonnement (sécurité)."""
    if _DB_PATH is None:
        return
    bak = _DB_PATH.with_name(_DB_PATH.name + f".bak-{suffix}")
    if _DB_PATH.exists() and not bak.exists():
        import shutil
        shutil.copy2(_DB_PATH, bak)


def bootstrap_accounts(superadmin_email="", superadmin_hash=None):
    """Amorce le super-admin et cloisonne le contenu existant (idempotent).

    - crée le super-admin de base (login local via ``superadmin_hash`` + e-mail) ;
    - ajoute ``compte_id`` sur ``titres``/``listes`` si absent ;
    - remplace l'ancienne unicité globale par une unicité PAR compte ;
    - rattache TOUT le contenu orphelin (compte_id NULL) au super-admin de base.
    Aucune donnée n'est supprimée. Une sauvegarde ``.bak-avant-comptes`` est
    posée avant la première migration.
    """
    conn = connect()
    email = (superadmin_email or "").strip().lower() or None

    # Super-admin de base : s'il n'existe aucun super-admin, on l'amorce.
    row = conn.execute(
        "SELECT id, email FROM comptes WHERE role='super_admin' ORDER BY id LIMIT 1"
    ).fetchone()
    if row is None:
        now = int(time.time())
        cur = conn.execute(
            "INSERT INTO comptes (email, role, etat, mdp_hash, cree, valide) "
            "VALUES (?, 'super_admin', 'actif', ?, ?, ?)",
            (email, superadmin_hash, now, now))
        conn.commit()
        base_id = cur.lastrowid
    else:
        base_id = row["id"]
        # Rattache l'e-mail au super-admin de base s'il n'en a pas encore.
        if email and not row["email"] and not conn.execute(
                "SELECT 1 FROM comptes WHERE email=?", (email,)).fetchone():
            conn.execute("UPDATE comptes SET email=? WHERE id=?", (email, row["id"]))
            conn.commit()

    _cloisonner_existant(conn, base_id)
    # Recrée les éventuels index perdus lors d'une reconstruction de table.
    conn.executescript(SCHEMA)
    conn.commit()
    ensure_system_lists(base_id)


def _cloisonner_existant(conn, base_id):
    """Ajoute compte_id (si absent) et rattache le contenu orphelin au base_id."""
    tcols = {r[1] for r in conn.execute("PRAGMA table_info(titres)")}
    lcols = {r[1] for r in conn.execute("PRAGMA table_info(listes)")}
    if "compte_id" in tcols and "compte_id" in lcols:
        # Colonnes déjà là : il reste juste à rattacher d'éventuels orphelins.
        conn.execute("UPDATE titres SET compte_id=? WHERE compte_id IS NULL", (base_id,))
        conn.execute("UPDATE listes SET compte_id=? WHERE compte_id IS NULL", (base_id,))
        conn.commit()
        return

    _backup_once()  # sauvegarde de la base avant de toucher au schéma existant
    conn.executescript("PRAGMA foreign_keys=OFF;")
    if "compte_id" not in tcols:
        conn.execute("ALTER TABLE titres ADD COLUMN compte_id INTEGER REFERENCES comptes(id)")
    if "compte_id" not in lcols:
        conn.execute("ALTER TABLE listes ADD COLUMN compte_id INTEGER REFERENCES comptes(id)")
    conn.execute("UPDATE titres SET compte_id=? WHERE compte_id IS NULL", (base_id,))
    conn.execute("UPDATE listes SET compte_id=? WHERE compte_id IS NULL", (base_id,))
    # Remplace l'ancienne unicité globale par une unicité par compte.
    _rebuild_unique(conn, "titres", "UNIQUE(compte_id, tmdb_id, type)")
    _rebuild_unique(conn, "listes", "UNIQUE(compte_id, systeme)")
    conn.executescript("PRAGMA foreign_keys=ON;")
    conn.commit()


def _rebuild_unique(conn, table, new_unique):
    """Recrée `table` en remplaçant sa contrainte UNIQUE, ids et données préservés.

    Ne recrée QUE si l'unicité voulue n'est pas déjà en place (idempotent).
    """
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not sql or new_unique in (sql[0] or ""):
        return
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    collist = ", ".join(cols)
    # Reconstruit la définition en repartant du CREATE existant (colonnes déjà
    # présentes, y compris compte_id ajouté juste avant), en réécrivant l'UNIQUE.
    body = _replace_unique_clause(sql[0], new_unique)
    tmp = f"{table}__new"
    body = body.replace(f"TABLE IF NOT EXISTS {table}", f"TABLE {tmp}") \
               .replace(f"TABLE {table}", f"TABLE {tmp}", 1)
    conn.executescript(body)
    conn.execute(f"INSERT INTO {tmp} ({collist}) SELECT {collist} FROM {table}")
    conn.execute(f"DROP TABLE {table}")
    conn.execute(f"ALTER TABLE {tmp} RENAME TO {table}")


def _replace_unique_clause(create_sql, new_unique):
    """Remplace toute clause UNIQUE(...) d'un CREATE TABLE par `new_unique`."""
    import re
    if re.search(r"UNIQUE\s*\([^)]*\)", create_sql or ""):
        return re.sub(r"UNIQUE\s*\([^)]*\)", new_unique, create_sql, count=1)
    # Aucune UNIQUE existante : on l'insère avant la parenthèse finale.
    idx = create_sql.rstrip().rfind(")")
    return create_sql[:idx] + ",\n    " + new_unique + "\n" + create_sql[idx:]


def _migrate(conn):
    """Ajoute les colonnes manquantes sur une base déjà créée (migration douce)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(titres)")}
    if "casting" not in cols:
        conn.execute("ALTER TABLE titres ADD COLUMN casting TEXT")
    if "equipe" not in cols:
        conn.execute("ALTER TABLE titres ADD COLUMN equipe TEXT")
    if "nb_saisons" not in cols:
        conn.execute("ALTER TABLE titres ADD COLUMN nb_saisons INTEGER")
    if "affiche_url" not in cols:
        conn.execute("ALTER TABLE titres ADD COLUMN affiche_url TEXT")
    ep_cols = {r[1] for r in conn.execute("PRAGMA table_info(episodes)")}
    if "notifie" not in ep_cols:
        conn.execute("ALTER TABLE episodes ADD COLUMN notifie INTEGER DEFAULT 0")
    # Supprime l'ancienne contrainte UNIQUE(titre_id, date) sur visionnages,
    # pour autoriser plusieurs visionnages le même jour.
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='visionnages'"
    ).fetchone()
    if row and "UNIQUE" in (row[0] or ""):
        conn.executescript("""
            PRAGMA foreign_keys=OFF;
            CREATE TABLE visionnages_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titre_id INTEGER NOT NULL REFERENCES titres(id) ON DELETE CASCADE,
                date TEXT, cree INTEGER
            );
            INSERT INTO visionnages_new (id, titre_id, date, cree)
                SELECT id, titre_id, date, cree FROM visionnages;
            DROP TABLE visionnages;
            ALTER TABLE visionnages_new RENAME TO visionnages;
            PRAGMA foreign_keys=ON;
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vision_titre ON visionnages(titre_id)")
    # Amorce le journal des films depuis les visionnages existants (une fois),
    # pour que l'historique ne parte pas vide. Les épisodes/séries se logueront
    # à partir de maintenant (on n'avait pas leur horodatage précis avant).
    if not conn.execute("SELECT 1 FROM journal LIMIT 1").fetchone():
        conn.execute(
            "INSERT INTO journal (titre_id, type, label, cree) "
            "SELECT titre_id, 'film', '', cree FROM visionnages WHERE cree IS NOT NULL")
    conn.commit()


def connect():
    """Connexion SQLite propre à chaque thread (Flask est multi-thread)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(_DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        _local.conn = conn
    return conn


def q(sql, params=()):
    """Requête de lecture → liste de dicts."""
    cur = connect().execute(sql, params)
    return [dict(row) for row in cur.fetchall()]


def q1(sql, params=()):
    """Requête de lecture → un dict ou None."""
    cur = connect().execute(sql, params)
    row = cur.fetchone()
    return dict(row) if row else None


def run(sql, params=()):
    """Écriture → identifiant de la ligne insérée (lastrowid)."""
    conn = connect()
    cur = conn.execute(sql, params)
    conn.commit()
    return cur.lastrowid


def log_event(titre_id, type_, label=""):
    """Ajoute une entrée au journal de visionnage (date + heure = maintenant)."""
    run("INSERT INTO journal (titre_id, type, label, cree) VALUES (?,?,?,?)",
        (titre_id, type_, label, int(time.time())))


def jload(value, default):
    """Décode un champ JSON stocké en texte, avec valeur de repli."""
    if not value:
        return default
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default
