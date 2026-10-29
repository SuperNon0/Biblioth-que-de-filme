"""Genres regroupés, en français.

Pour les séries, TMDB utilise des genres doubles, parfois en anglais
(« Action & Adventure », « Science-Fiction & Fantastique », « War & Politics »…).
Ils faussaient le classement des genres préférés : chaque genre double compte
désormais dans chacun de ses deux genres, sous leur nom français.
"""

FUSION = {
    "Action & Adventure": ("Action", "Aventure"),
    "Science-Fiction & Fantastique": ("Science-Fiction", "Fantastique"),
    "Sci-Fi & Fantasy": ("Science-Fiction", "Fantastique"),
    "War & Politics": ("Guerre", "Politique"),
    "Guerre & Politique": ("Guerre", "Politique"),
    "Kids": ("Enfants",),
    "News": ("Actualités",),
    "Reality": ("Téléréalité",),
    "Soap": ("Feuilleton",),
    "Talk": ("Talk-show",),
}


def normaliser(noms):
    """Liste de genres TMDB → genres français dédoublonnés, dans l'ordre."""
    out = []
    for nom in noms or []:
        for g in FUSION.get(nom, (nom,)):
            if g and g not in out:
                out.append(g)
    return out


def variantes(nom):
    """Noms bruts (stockés tels que TMDB les donne) qui comptent pour ``nom``."""
    return [nom] + [brut for brut, cibles in FUSION.items() if nom in cibles]


# Genres doubles des séries, gardés entiers (filtre TMDB) mais en français.
LIBELLES = {
    "Action & Adventure": "Action & Aventure",
    "Sci-Fi & Fantasy": "Science-Fiction & Fantastique",
    "War & Politics": "Guerre & Politique",
    "Kids": "Enfants",
    "News": "Actualités",
    "Reality": "Téléréalité",
    "Soap": "Feuilleton",
    "Talk": "Talk-show",
}


def libelle(nom):
    """Nom affichable d'un genre TMDB (traduit s'il est resté en anglais)."""
    return LIBELLES.get(nom, nom)
