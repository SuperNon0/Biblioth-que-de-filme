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
CREATE TABLE IF NOT EXISTS titres (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
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
    UNIQUE(tmdb_id, type)
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
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nom      TEXT NOT NULL,
    systeme  TEXT,                               -- 'a_voir'|'favoris' si liste système
    cree     INTEGER,
    UNIQUE(systeme)
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

CREATE INDEX IF NOT EXISTS idx_titres_statut  ON titres(statut);
CREATE INDEX IF NOT EXISTS idx_titres_type    ON titres(type);
CREATE INDEX IF NOT EXISTS idx_episodes_titre ON episodes(titre_id);
CREATE INDEX IF NOT EXISTS idx_vision_titre   ON visionnages(titre_id);
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
    # Listes système présentes par défaut : « À voir » et « Favoris ».
    now = int(time.time())
    for systeme, nom in (("a_voir", "À voir"), ("favoris", "Favoris")):
        conn.execute(
            "INSERT OR IGNORE INTO listes (nom, systeme, cree) VALUES (?, ?, ?)",
            (nom, systeme, now),
        )
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


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


def jload(value, default):
    """Décode un champ JSON stocké en texte, avec valeur de repli."""
    if not value:
        return default
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default
