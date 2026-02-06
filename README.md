# Plugin QGIS MH vers SM

## Contexte et enjeu

Le laboratoire HM and Co de l'Ecole Nationale Des Ponts et Chaussées utilises un couplage entre deux modèles numériques complémentaires :

- Multi Hydro MH : modèle hydrologique distribué 2D sur grille régulière, simulant notamment l infiltration, le ruissellement et l écoulement des eaux pluviales en milieu urbain
- Solène Microclimat SM : modèle microclimatique 3D sur maillage triangulé, dédié aux échanges radiatifs, thermiques et aérauliques au sein de la morphologie urbaine

Le couplage itératif vise à faire circuler des informations entre ces deux représentations. Par exemple, MH calcule des flux liés à l'évapotranspiration en fonction de l'état hydrique des surfaces, puis ces flux peuvent être réinjectés dans SM sous forme de chaleur latente pour ajuster le bilan énergétique.

L'enjeu opérationnel n'est plus de démontrer le couplage scientifique, mais de rendre les échanges reproductibles et robustes. En pratique, les deux modèles reposent sur des supports géométriques différents, grille 2D versus maillage 3D, ainsi que sur des formats de fichiers spécifiques. 

Ce plugin QGIS répond à ce besoin en fournissant une passerelle automatisée entre MH et SM :
- conversion d'un raster MH vers un fichier SM .val selon l'ordre du maillage décrit par le fichier .cir
- reconstruction d'un raster MH depuis un fichier .val SM
- outils de contrôle via comparaison raster, calcul de métriques et génération d'une carte d'erreur

L'objectif est de fiabiliser la chaîne de traitement, de réduire les manipulations manuelles et de faciliter la reprise du workflow par d'autres utilisateurs ou développeurs.

## Présentation

Ce projet est un plugin QGIS qui met en place un échange bidirectionnel entre deux représentations d'un même jeu de données :

- MH : raster au format .asc ou .txt
- SM : fichier .val contenant une valeur par triangle, ordonnée selon un fichier .cir

Le plugin permet :
- la conversion MH vers SM en produisant un fichier .val à partir d un fichier .txt ou .asc et d un fichier .cir associé.
- la conversion SM vers MH en reconstruisant un raster .asc à partir d un fichier .val
- la comparaison entre un raster MH de référence et le raster reconstruit depuis SM, avec calcul de métriques et génération d'une carte d'erreur
- une visualisation optionnelle de maillages MED via PyVista (aucun lien avec le plugin finalement)

Le plugin a été développé pour fournir une chaîne de traitement exploitable directement dans QGIS, avec une interface claire et des sorties reproductibles.

## Fonctionnalités

### Pipeline MH vers SM

Entrées :
- un raster MH au format .txt ou .asc
- un fichier scene_triangle.cir

Sortie :
- un fichier .val contenant les valeurs par triangle, dans l ordre officiel du .cir

Méthode :
- lecture du raster MH et conversion du NODATA en NaN en interne
- lecture du fichier .cir pour récupérer les triangles dans l'ordre attendu
- alignement géométrique simple du maillage sur l'emprise du raster par translation des centres de boîtes englobantes
- calcul d'un mapping surface based entre triangles et pixels par intersections géométriques
- agrégation des pixels associés à chaque triangle par moyenne
- écriture du fichier .val par facette et dans l'ordre du .cir

### Pipeline SM vers MH

Entrées :
- un fichier .val
- un raster MH de référence utilisé uniquement pour récupérer la grille et le géoréférencement
- un fichier scene_triangle.cir

Sortie :
- un fichier raster .asc écrit dans le dossier du .val, nommé nom_fichier2asc.asc

Méthode :
- lecture du raster MH de référence pour récupérer la grille
- lecture du maillage via le fichier .cir
- alignement identique à celui de la conversion aller
- calcul du mapping surface based pixel vers triangles
- pour chaque pixel, calcul d'une valeur à partir des triangles qui l'intersectent
- écriture du raster reconstruit au format asc grid

### Comparaison raster de référence et raster reconstruit

Entrées :
- raster MH de référence
- fichier .val
- fichier scene_triangle.cir

Sorties :
- un GeoTIFF de référence
- un GeoTIFF reconstruit
- un GeoTIFF d erreur reconstruit moins référence

Métriques :
- nombre de pixels valides
- MAE
- RMSE
- corrélation linéaire

Affichage :
- les fichiers sont ajoutés au projet QGIS pour contrôle visuel
- les métriques sont affichées dans le journal QGIS et dans la console Python de QGIS

### Visualisation MED optionnelle

Cette fonctionnalité ouvre une visualisation PyVista d un maillage MED avec un filtrage simple :
- filtrage intérieur en XY
- filtrage en Z selon un percentile

Cette partie est optionnelle et peut être désactivée si PyVista ou meshio ne sont pas disponibles.

## Convention NODATA

Conventions imposées dans ce projet :
- NODATA en entrée MH : 9999
- NODATA en sortie MH : 9999

En interne, les rasters sont manipulés en float et le NODATA est représenté par NaN afin de sécuriser les calculs de moyenne et de métriques.

## Méthode de reconstruction de SM vers MH

La reconstruction SM vers MH ne repose pas sur une interpolation continue au sens classique. Elle utilise une projection par recouvrement :
- un pixel reçoit les valeurs des triangles qui intersectent sa surface
- la valeur du pixel est calculée comme moyenne des valeurs des triangles intersectants

Le mapping est basé sur l'intersection géométrique triangle pixel en XY. Cette méthode est robuste et cohérente avec la définition des valeurs portées par le maillage.

## Organisation du dépôt

- plugin_mh_sm.py : module principal du plugin, gestion de l'interface et des actions
- plugin_mh_sm_dialog.py : gestion de la fenêtre, sélection des fichiers et accès aux chemins
- plugin_mh_sm_dialog_base.ui : interface Qt
- src : coeur métier
  - io_mh_sm_exchange.py : lecture et écriture MH et SM, pipelines principaux
  - mapping.py : mapping barycentre et mapping surface based triangle pixel
  - alignment.py : alignement simple du maillage sur la grille raster
  - reader.py : lecture MED et fonctions utilitaires associées
  - preprocessing.py : filtres simples utilisés pour la visualisation MED
- visu_pyvista.py : visualisation MED optionnel
- scripts : scripts utilitaires éventuels
- test : données ou tests selon le contenu du dépôt

## Installation

Copier le dossier du plugin dans le répertoire des plugins QGIS de l utilisateur.



Puis dans QGIS :
- Extensions
- Installer et gérer les extensions
- Activer le plugin

## Dépendances

Dépendances principales :
- QGIS 3.x
- Python (3.10) utilisé par QGIS
- numpy
- gdal osgeoccf

Dépendances optionnelles pour la visualisation MED :
- pyvista
- meshio

La partie conversion MH SM et comparaison ne dépend pas de PyVista.

## Utilisation

1. Renseigner les chemins dans le bloc Pipeline MH vers SM
2. Lancer MH vers SM pour générer le fichier .val
3. Renseigner le fichier .val dans le bloc Pipeline SM vers MH
4. Lancer SM vers MH pour reconstruire un raster .asc
5. Utiliser le bouton de comparaison pour obtenir les métriques et les cartes GeoTIFF

## Sorties générées

- fichier .val pour la conversion MH vers SM
- fichier .asc reconstruit pour la conversion SM vers MH
- GeoTIFF de référence, reconstruit et erreur lors de la comparaison

Tous les fichiers de comparaison sont générés dans le dossier du fichier .val sélectionné.

## Points connus et limites

- L'alignement maillage raster est un alignement rigide simple par translation des centres de boîtes englobantes. Il est adapté lorsque le maillage et la grille sont déjà dans le même système et proches spatialement.
- La conversion inverse peut produire une emprise quasi identique mais avec des différences de précision flottante dans les métadonnées. Ces différences proviennent de l écriture des en têtes en double précision et ne correspondent pas nécessairement à un décalage réel des données.
- La qualité de reconstruction dépend directement de la cohérence entre le fichier .cir et le raster de référence, ainsi que de la correspondance géométrique entre la scène SM et la grille MH.

## Reprise et maintenance

Le code est organisé en modules simples avec une séparation nette :
- interface QGIS dans les fichiers plugin_mh_sm.py et plugin_mh_sm_dialog.py
- logique métier dans le dossier src

Les fonctions principales sont documentées par des docstrings complètes afin de faciliter la reprise, la compréhension et l'amélioration.

## Auteur

Projet réalisé dans le cadre d un développement de plugin QGIS pour conversion et validation MH SM.

Encadrement :
Pierre Antoine Versini, Directeur de Recherche de l'ENPC,

