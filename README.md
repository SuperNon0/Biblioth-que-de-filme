# cinéthèque 🎬

Bibliothèque personnelle de **films et séries**, auto-hébergée : enregistre ce
que tu as vu, ce que tu veux voir, suis tes séries épisode par épisode, mesure
le temps passé et découvre de nouveaux films.

Site mono-utilisateur (compte `admin`), thème sombre doré, construit avec
**Python + Flask** et **SQLite**, alimenté par l'**API TMDB**.

## Fonctionnalités

- **Bibliothèque** : films et séries, statuts (Vu / À voir / En cours),
  progression des séries (« où j'en suis : S x E y »), tri par date, genre,
  année, note, alphabétique.
- **Fiches** : durée, résumé, plateformes de streaming, bande-annonce.
  - Films : dates de visionnage multiples + revisionnages.
  - Séries : saisons dépliables, épisodes (nom, image, résumé, durée), marquage
    Vu/Revu, « marquer la saison / la série », prochain épisode.
- **Suggestions** (accueil) : carrousels Tendances, Au cinéma, Populaires, Mieux
  notés, Recommandé pour toi.
- **Découverte** : catalogue filtrable (genre, année, note, pays) et paginé.
- **Futur** : films à venir + alertes de sortie (cinéma / streaming).
- **Listes** : « À voir » et « Favoris » par défaut, listes perso, import de
  listes toutes prêtes.
- **Profil** : temps total regardé (heures → mois/années), compteurs, genres les
  plus vus, temps par série.
- **Notifications** : Discord (via *botpanel*) et push mobile (*ntfy*) pour les
  nouveaux épisodes et les sorties ciné/streaming —
  guide complet : [`docs/notifications.md`](docs/notifications.md).
- **Sauvegarde** : export/import complet des données.

## Installation

### Proxmox — une seule commande (recommandé)

Sur l'hôte Proxmox :

```bash
bash -c "$(wget -qLO - https://raw.githubusercontent.com/SuperNon0/Biblioth-que-de-filme/main/proxmox/cinetheque-lxc.sh)"
```

Crée un conteneur LXC Ubuntu, installe et démarre le site automatiquement.

### Manuelle (VM ou machine Ubuntu)

```bash
git clone https://github.com/SuperNon0/Biblioth-que-de-filme.git /opt/cinetheque-src
sudo bash /opt/cinetheque-src/install.sh
```

Puis ouvre `http://<ip>:8080`, connecte-toi avec le mot de passe affiché, et
renseigne ta **clé API TMDB** (gratuite) dans **Paramètres**.

## Clé API TMDB

Gratuite pour un usage personnel, sans limite de durée : crée un compte sur
[themoviedb.org](https://www.themoviedb.org/), va dans Paramètres → API, copie
la clé, colle-la dans les Paramètres du site.

## Mot de passe oublié

```bash
sudo bash /opt/cinetheque/scripts/reset-admin-password.sh
```

## Développement local

```bash
cd panel
pip install flask          # ou apt install python3-flask
python3 app.py             # tourne sur http://127.0.0.1:8080 avec une base ./.data
```

## Licence & attribution

Ce produit utilise l'API TMDb mais n'est ni approuvé ni certifié par TMDb.
*(This product uses the TMDb API but is not endorsed or certified by TMDb.)*
