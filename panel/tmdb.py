"""Client de l'API TMDB (The Movie Database).

Encapsule tous les appels à TMDB derrière une petite classe. Utilise
``urllib`` (bibliothèque standard) : aucune dépendance à installer.

Attribution obligatoire (affichée en pied de page du site) :
« This product uses the TMDb API but is not endorsed or certified by TMDb. »
"""
import json
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p"


class TMDBError(RuntimeError):
    """Erreur d'appel TMDB (réseau, clé invalide, quota…)."""


class TMDB:
    def __init__(self, api_key, language="fr-FR", region="FR", timeout=8):
        self.api_key = api_key
        self.language = language
        self.region = region
        self.timeout = timeout

    # -- bas niveau --------------------------------------------------------
    def _get(self, path, **params):
        if not self.api_key:
            raise TMDBError("Clé API TMDB manquante (à renseigner dans Paramètres).")
        params.setdefault("api_key", self.api_key)
        params.setdefault("language", self.language)
        url = f"{API_BASE}{path}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise TMDBError("Clé API TMDB invalide.") from exc
            raise TMDBError(f"TMDB a répondu HTTP {exc.code}.") from exc
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
            raise TMDBError(f"TMDB injoignable : {exc}") from exc

    # -- images ------------------------------------------------------------
    @staticmethod
    def image_url(path, size="w500"):
        return f"{IMG_BASE}/{size}{path}" if path else None

    # -- recherche ---------------------------------------------------------
    def search(self, query, page=1):
        """Recherche multi (films + séries), filtrée sur ces deux types."""
        data = self._get("/search/multi", query=query, page=page,
                          include_adult="false")
        results = [r for r in data.get("results", [])
                   if r.get("media_type") in ("movie", "tv")]
        return [self._brief(r) for r in results]

    # -- listes de découverte ---------------------------------------------
    def trending(self, media="all", window="week", page=1):
        data = self._get(f"/trending/{media}/{window}", page=page)
        return [self._brief(r) for r in data.get("results", [])
                if r.get("media_type") in ("movie", "tv") or media != "all"]

    def popular(self, media="movie", page=1):
        data = self._get(f"/{media}/popular", page=page, region=self.region)
        return [self._brief(r, media) for r in data.get("results", [])]

    def top_rated(self, media="movie", page=1):
        data = self._get(f"/{media}/top_rated", page=page)
        return [self._brief(r, media) for r in data.get("results", [])]

    def now_playing(self, page=1):
        """Films actuellement au cinéma (l'esprit « box-office »)."""
        data = self._get("/movie/now_playing", page=page, region=self.region)
        return [self._brief(r, "movie") for r in data.get("results", [])]

    def upcoming(self, page=1):
        data = self._get("/movie/upcoming", page=page, region=self.region)
        return [self._brief(r, "movie") for r in data.get("results", [])]

    def recommendations(self, media, tmdb_id, page=1):
        data = self._get(f"/{media}/{tmdb_id}/recommendations", page=page)
        return [self._brief(r, media) for r in data.get("results", [])]

    def discover(self, media="movie", page=1, sort_by="popularity.desc",
                 genre=None, year=None, country=None):
        """Catalogue filtrable pour l'onglet Découverte."""
        params = {"page": page, "sort_by": sort_by, "include_adult": "false"}
        if genre:
            params["with_genres"] = genre
        if country:
            params["with_origin_country"] = country
        if year:
            params["primary_release_year" if media == "movie"
                   else "first_air_date_year"] = year
        data = self._get(f"/discover/{media}", **params)
        return {
            "results": [self._brief(r, media) for r in data.get("results", [])],
            "page": data.get("page", 1),
            "total_pages": min(data.get("total_pages", 1), 500),
        }

    def genres(self, media="movie"):
        data = self._get(f"/genre/{media}/list")
        return data.get("genres", [])

    # -- fiches détaillées -------------------------------------------------
    def movie(self, tmdb_id):
        d = self._get(f"/movie/{tmdb_id}",
                      append_to_response="videos,watch/providers,credits")
        return self._movie_detail(d)

    def tv(self, tmdb_id):
        d = self._get(f"/tv/{tmdb_id}",
                      append_to_response="videos,watch/providers,credits")
        return self._tv_detail(d)

    def season(self, tmdb_id, season_number):
        d = self._get(f"/tv/{tmdb_id}/season/{season_number}")
        return [self._episode(e) for e in d.get("episodes", [])]

    # -- normalisation -----------------------------------------------------
    def _brief(self, r, media=None):
        media = media or r.get("media_type") or "movie"
        typ = "serie" if media == "tv" else "film"
        titre = r.get("title") or r.get("name") or "Sans titre"
        date = r.get("release_date") or r.get("first_air_date") or ""
        return {
            "tmdb_id": r.get("id"),
            "type": typ,
            "titre": titre,
            "annee": int(date[:4]) if date[:4].isdigit() else None,
            "date_sortie": date or None,
            "resume": r.get("overview") or "",
            "affiche": self.image_url(r.get("poster_path")),
            "fond": self.image_url(r.get("backdrop_path"), "w780"),
            "note_tmdb": round(r.get("vote_average", 0), 1),
        }

    def _providers(self, d):
        block = (d.get("watch/providers", {}).get("results", {})
                 .get(self.region, {}))
        seen, out = set(), []
        for key in ("flatrate", "free", "ads", "rent", "buy"):
            for p in block.get(key, []):
                name = p.get("provider_name")
                if name and name not in seen:
                    seen.add(name)
                    out.append({"nom": name,
                                "logo": self.image_url(p.get("logo_path"), "w92")})
        return out

    @staticmethod
    def _trailer(d):
        for v in d.get("videos", {}).get("results", []):
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                return v.get("key")
        return None

    @staticmethod
    def _director(d):
        for c in d.get("credits", {}).get("crew", []):
            if c.get("job") == "Director":
                return c.get("name")
        return None

    def _cast(self, d, limit=15):
        return [{"id": c.get("id"), "nom": c.get("name"),
                 "personnage": c.get("character"),
                 "photo": self.image_url(c.get("profile_path"), "w185")}
                for c in d.get("credits", {}).get("cast", [])[:limit]]

    def person(self, person_id):
        """Fiche d'une personne : infos + filmographie (films et séries)."""
        d = self._get(f"/person/{person_id}",
                      append_to_response="combined_credits")
        seen, films = set(), []
        for c in d.get("combined_credits", {}).get("cast", []):
            media = c.get("media_type")
            if media not in ("movie", "tv"):
                continue
            key = (c.get("id"), media)
            if key in seen:
                continue
            seen.add(key)
            brief = self._brief(c, media)
            brief["personnage"] = c.get("character")
            films.append(brief)
        films.sort(key=lambda x: (x.get("annee") or 0), reverse=True)
        return {
            "id": d.get("id"),
            "nom": d.get("name"),
            "bio": d.get("biography") or "",
            "naissance": d.get("birthday"),
            "lieu": d.get("place_of_birth"),
            "metier": d.get("known_for_department"),
            "photo": self.image_url(d.get("profile_path"), "w185"),
            "films": films[:40],
        }

    def _movie_detail(self, d):
        brief = self._brief(d, "movie")
        brief.update({
            "duree": d.get("runtime"),
            "genres": [g["name"] for g in d.get("genres", [])],
            "pays": (d.get("origin_country") or [None])[0],
            "note_tmdb": round(d.get("vote_average", 0), 1),
            "revenue": d.get("revenue"),
            "bande_annonce": self._trailer(d),
            "plateformes": self._providers(d),
            "realisateur": self._director(d),
            "casting": self._cast(d),
        })
        return brief

    def _tv_detail(self, d):
        brief = self._brief(d, "tv")
        saisons = [{"numero": s.get("season_number"),
                    "nom": s.get("name"),
                    "nb_episodes": s.get("episode_count"),
                    "affiche": self.image_url(s.get("poster_path"))}
                   for s in d.get("seasons", [])
                   if s.get("season_number", 0) >= 1]
        brief.update({
            "genres": [g["name"] for g in d.get("genres", [])],
            "pays": (d.get("origin_country") or [None])[0],
            "note_tmdb": round(d.get("vote_average", 0), 1),
            "duree": (d.get("episode_run_time") or [None])[0],
            "nb_saisons": d.get("number_of_seasons"),
            "nb_episodes": d.get("number_of_episodes"),
            "en_cours": d.get("in_production"),
            "prochain_episode": d.get("next_episode_to_air"),
            "bande_annonce": self._trailer(d),
            "plateformes": self._providers(d),
            "casting": self._cast(d),
            "saisons": saisons,
        })
        return brief

    def _episode(self, e):
        return {
            "saison": e.get("season_number"),
            "numero": e.get("episode_number"),
            "nom": e.get("name"),
            "resume": e.get("overview") or "",
            "image": self.image_url(e.get("still_path"), "w300"),
            "duree": e.get("runtime"),
            "date_diff": e.get("air_date"),
        }
