"""Listes toutes prêtes à importer (sagas connues).

Chaque preset est une liste ordonnée d'entrées ``{tmdb_id, type}``. À l'import,
chaque titre est récupéré depuis TMDB (donc validé) puis rangé dans une nouvelle
liste dans l'ordre fourni. Facile à compléter : ajoute une entrée au dict.
"""


def _films(ids):
    return [{"tmdb_id": i, "type": "film"} for i in ids]


PRESETS = {
    "marvel_films": {
        "nom": "Marvel (MCU) — films, ordre de sortie",
        "items": _films([
            1726, 1724, 10138, 10195, 1771, 24428, 68721, 76338, 100402,
            118340, 99861, 102899, 271110, 284052, 283995, 315635, 284053,
            284054, 299536, 363088, 299537, 299534, 429617,        # Infinity Saga
            566525, 524434, 634649, 453395, 616037, 505642, 640146,
            447365, 609681,                                        # Multiverse Saga
        ]),
    },
    "marvel_complet": {
        "nom": "Marvel (MCU) — films & séries, ordre de sortie",
        "items": _films([
            1726, 1724, 10138, 10195, 1771, 24428, 68721, 76338, 100402,
            118340, 99861, 102899, 271110, 284052, 283995, 315635, 284053,
            284054, 299536, 363088, 299537, 299534, 429617,
        ]) + [
            {"tmdb_id": 85271, "type": "serie"},   # WandaVision
            {"tmdb_id": 88396, "type": "serie"},   # Falcon & Winter Soldier
            {"tmdb_id": 84958, "type": "serie"},   # Loki
        ] + _films([566525, 524434, 634649]) + [
            {"tmdb_id": 88329, "type": "serie"},   # Hawkeye
            {"tmdb_id": 92749, "type": "serie"},   # Moon Knight
        ] + _films([453395, 616037]) + [
            {"tmdb_id": 92782, "type": "serie"},   # Ms. Marvel
            {"tmdb_id": 92783, "type": "serie"},   # She-Hulk
        ] + _films([505642, 640146, 447365, 609681]),
    },
    "starwars_sortie": {
        "nom": "Star Wars — ordre de sortie",
        "items": _films([11, 1891, 1892, 1893, 1894, 1895, 140607, 330459,
                         181808, 348350, 181812]),
    },
    "starwars_chrono": {
        "nom": "Star Wars — ordre chronologique",
        "items": _films([1893, 1894, 1895, 348350, 330459, 11, 1891, 1892,
                         140607, 181808, 181812]),
    },
    "harry_potter": {
        "nom": "Harry Potter — ordre chronologique",
        "items": _films([671, 672, 673, 674, 675, 767, 12444, 12445]),
    },
    "lotr": {
        "nom": "Terre du Milieu (Le Hobbit + Le Seigneur des Anneaux)",
        "items": _films([49051, 57158, 122917, 120, 121, 122]),
    },
}


def liste():
    """Résumé des presets disponibles (clé, nom, nombre de titres)."""
    return [{"cle": k, "nom": v["nom"], "nb": len(v["items"])}
            for k, v in PRESETS.items()]
