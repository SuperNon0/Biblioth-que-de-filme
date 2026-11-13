# Outils du design « encre »

Ces scripts refont la démo, le squelette, les captures et la page privée
« Design encre » à partir du dossier `design-encre/`, qui reste la source :
on corrige d'abord `encre.css`, `encre.js` ou `LISEZMOI.md` dans ce dossier,
puis on relance. (Ne pas repartir de la feuille de style de cinéthèque :
`encre.css` a reçu des corrections depuis.)

## Mise en place

Dans un dossier de travail `R` :

- copier `design-encre/` en `R/dossier-encre/` ;
- copier ce dossier en `R/outils/`.

Playwright doit être disponible (`require("playwright")`).

## Commandes

| But | Commande |
|---|---|
| Refaire `demo.html`, `modele.html` et `R/outils/demo-artifact.html` | `python3 -I R/outils/construire.py R` |
| Tester la démo (89 vérifications) | `node R/outils/tester.js R/dossier-encre/demo.html` |
| Tester le squelette | `node R/outils/tester-modele.js R/dossier-encre/modele.html` |
| Refaire les 14 captures | `node R/outils/captures.js R/dossier-encre/demo.html R/dossier-encre/captures 2` |
| Refaire le contenu de la page « Design encre » | `python3 -I R/outils/ds.py R` (écrit `R/ds/project/`) |
| Tester les 27 briques et la couverture | `node R/outils/tester-ds.js R/ds/project R/ds-test`, puis `node R/outils/interagir-ds.js R/ds-test` |

## Republier la page « Design encre »

Outil Artifact, action `publish` :

- `url` : https://claude.ai/artifact/1EJwFWYo5CDa9617N757fV (page privée de Noë) ;
- `root` : `R/ds` ;
- `file_path` : `R/ds/project/design-system.json` (toujours en dernier) ;
- `files` : les autres fichiers de `R/ds/project/` sous la forme
  `{"project/…": "project/…"}` ; seuls les fichiers modifiés suffisent.

Ne jamais publier `index.html`, `SKILL.md` ni `artifact-type/` : ce sont les
fichiers du type de page, pas les nôtres.
