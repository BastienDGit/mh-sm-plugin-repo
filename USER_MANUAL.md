# Manuel utilisateur
Plugin QGIS MH vers SM

## 1. Objectif du plugin

Le plugin permet de réaliser des échanges de données entre deux modèles :

- MH : données raster 2D au format .asc ou .txt
- SM : données par triangle au format .val, ordonnées selon un fichier scene_triangle.cir

Le plugin fournit trois usages principaux :

- Conversion MH vers SM : produire un fichier .val à partir d'un raster MH
- Conversion SM vers MH : reconstruire un raster .asc à partir d'un fichier .val
- Contrôle et validation : comparer le raster MH d'origine avec le raster reconstruit, calculer des métriques et générer une carte d'erreur

Une visualisation MED via PyVista peut être présente de manière optionnelle.

## 2. Prérequis

### 2.1 Logiciels

- QGIS 3.x installé et fonctionnel
- Plugin installé dans le dossier des extensions QGIS

### 2.2 Données nécessaires

Pour utiliser toutes les fonctionnalités, il faut :

- Un raster MH au format ESRI ASCII grid
  - Extension .asc ou .txt
  - En-tête ESRI ASCII standard : ncols nrows xllcorner yllcorner cellsize NODATA_value
- Un fichier scene_triangle.cir
  - Contient l ordre officiel des triangles, organisé par facettes
- Un fichier SM .val
  - Contient une valeur par triangle
  - Les valeurs sont écrites facette par facette, dans l'ordre du .cir

### 2.3 Convention nodata

Le plugin impose la convention suivante :

- NODATA en entrée MH : 9999
- NODATA en sortie MH : 9999

En interne, le plugin convertit les nodata en NaN afin de sécuriser les moyennes et les métriques.

## 3. Installation du plugin

### 3.1 Copie dans le dossier QGIS

Copier le dossier du plugin dans le répertoire des plugins QGIS.


Le dossier doit contenir au minimum :

- plugin_mh_sm.py
- plugin_mh_sm_dialog.py
- plugin_mh_sm_dialog_base.ui
- src
- metadata.txt
- __init__.py

### 3.2 Activation dans QGIS

Dans QGIS :

- Extensions
- Installer et gérer les extensions
- Onglet Installées
- Activer le plugin MH vers SM

Après activation, une entrée de menu et une icône apparaissent.

## 4. Démarrage et interface

Ouvrir le plugin :

- via l'icône dans la barre d'outils
- ou via le menu Extensions

La fenêtre du plugin est structurée en blocs :

- Pipeline MH vers SM
- Pipeline SM vers MH
- Outils
- MED optionnel si présent

## 5. Pipeline MH vers SM

### 5.1 But

Produire un fichier .val SM à partir d un raster MH, en respectant l ordre des triangles du fichier .cir.

### 5.2 Entrées

- Entrée MH .txt ou .asc : raster ESRI ASCII grid
- fichier.cir : structure des facettes et ordre des triangles


### 5.3 Procédure

1. Dans Pipeline MH vers SM, cliquer sur Parcourir pour sélectionner le fichier MH
2. Cliquer sur Parcourir pour sélectionner le fichier .cir
3. Cliquer sur Choisir pour sélectionner le chemin de sortie .val
4. Cliquer sur Lancer MH vers SM

### 5.4 Résultat attendu

- Le fichier .val est écrit à l'emplacement choisi
- Un message de confirmation apparaît dans la barre de messages QGIS

### 5.5 Problèmes fréquents

Fichier MH introuvable
- Vérifier que le chemin est correct et que le fichier existe

Fichier CIR introuvable
- Vérifier que le fichier sélectionné est bien un .cir valide et qu'il s'agit bien du fichier .cir associé au raster

Sortie .val vide
- Vérifier que le champ sortie a été rempli

## 6. Pipeline SM vers MH

### 6.1 But

Reconstruire un raster MH au format ESRI ASCII grid à partir d un fichier .val SM.

### 6.2 Entrées

- Entrée SM .val : fichier existant
- MH de référence : sert uniquement à récupérer la grille et le géoréférencement
- scene_triangle.cir : ordre officiel des triangles

### 6.3 Sortie

- Un fichier .asc est écrit dans le dossier du .val
- Nom automatique : nom2asc.asc
  - Exemple : test5.val produit test52asc.asc

### 6.4 Procédure

1. Sélectionner le raster MH de référence dans Entrée MH
2. Sélectionner scene_triangle.cir dans le champ correspondant
3. Dans Pipeline SM vers MH, cliquer Parcourir et choisir le fichier .val
4. Cliquer sur Lancer SM vers MH

### 6.5 Résultat attendu

- Le fichier raster reconstruit est écrit dans le dossier du .val
- Le raster peut être ajouté automatiquement à QGIS selon la configuration du plugin

### 6.6 Problèmes fréquents

Le raster reconstruit n'apparaît pas
- Vérifier que le fichier .asc a bien été créé dans le dossier du .val
- Ajouter manuellement le raster dans QGIS si nécessaire

Reconstruction incohérente
- Vérifier que le .cir correspond bien au .val
- Vérifier que le MH de référence correspond bien au même site et à la même scène

## 7. Comparaison rasters

### 7.1 But

Comparer le raster MH de référence avec le raster reconstruit depuis le fichier .val, calculer des métriques et produire une carte d erreur.

### 7.2 Entrées

- MH de référence
- scene_triangle.cir
- .val SM

### 7.3 Sorties

Trois fichiers GeoTIFF sont produits dans le dossier du .val :

- base_mh_ref.tif
- base_mh_reconstruit.tif
- base_mh_erreur.tif

base correspond au nom du fichier .val sans extension.

### 7.4 Métriques calculées

Les métriques sont calculées sur les pixels valides uniquement :

- n_valid : nombre de pixels comparés
- mae : erreur absolue moyenne
- rmse : racine de l erreur quadratique moyenne
- corr : corrélation linéaire

### 7.5 Procédure

1. Sélectionner le MH de référence
2. Sélectionner le fichier .cir
3. Sélectionner le fichier .val d'entrée
4. Cliquer sur Comparer MH vs reconstruit

### 7.6 Où lire les résultats

Les métriques sont écrites :

- dans le journal QGIS du plugin
- dans la console Python de QGIS si la console est ouverte et si les impressions sont activées

Pour afficher le journal :

- Vue
- Panneaux
- Journal des messages
- Filtrer sur mh_sm_plugin

### 7.7 Résultat attendu

- Les trois GeoTIFF sont ajoutés au projet QGIS
- Les métriques apparaissent dans le journal
- La carte d'erreur permet une lecture spatiale des écarts

## 8. Outils

### 8.1 Afficher MH dans QGIS

Ce bouton charge le fichier MH sélectionné dans QGIS, sans transformation, pour contrôle visuel.

Procédure :
- sélectionner un raster MH
- cliquer sur Afficher MH dans QGIS

## 9. Visualisation MED optionnelle

Cette partie est optionnelle. Elle ouvre une fenêtre PyVista qui permet de visualiser un maillage 3D.

### 9.1 Entrée

- un fichier .med

### 9.2 Fonctionnement

- lecture du fichier MED
- filtrage intérieur en XY
- filtrage en Z sur un percentile
- affichage du maillage triangulé

### 9.3 Dépendances nécessaires

- pyvista
- meshio

Si ces bibliothèques ne sont pas installées, il est recommandé de désactiver cette fonctionnalité.

## 10. Recommandations de workflow

### Workflow conseillé pour un nouveau jeu de données

1. Charger MH de référence dans QGIS pour vérifier l emprise
2. Lancer MH vers SM pour produire un .val
3. Utiliser ce .val pour reconstruire un raster .asc
4. Lancer la comparaison rasters
5. Contrôler :
   - cohérence visuelle
   - métriques
   - carte d erreur

## 11. Diagnostic et dépannage

### 11.1 Le bouton ne fait rien

- Ouvrir le journal QGIS
- Vérifier si une erreur Python est affichée
- Vérifier que les chemins sont renseignés

### 11.2 Permission denied ou erreurs de lecture

- Vérifier les droits sur les fichiers
- Vérifier que les fichiers ne sont pas ouverts ailleurs
- Vérifier que QGIS a accès au dossier de sortie

### 11.3 Décalage léger entre rasters

Un très léger écart peut apparaître dans les en-têtes ASCII à cause de la précision flottante lors de l'écriture. Cela ne signifie pas nécessairement un décalage réel des données.

Pour diagnostiquer :
- comparer xllcorner yllcorner cellsize entre le MH d origine et le MH reconstruit
- comparer visuellement dans QGIS avec transparence

### 11.4 Aucun pixel valide en comparaison

- Vérifier que les deux rasters utilisent bien la même convention nodata 9999
- Vérifier que le raster reconstruit contient bien des valeurs et pas uniquement du nodata
- Vérifier que le raster de référence correspond bien au même site

## 12. Glossaire

- Raster MH : grille régulière 2D avec une valeur par cellule
- Triangle SM : élément du maillage 3D représentant une facette de surface
- Fichier .cir : décrit l ordre officiel des triangles par facette
- Fichier .val : une valeur par triangle, ordonnée comme dans le .cir
- Mapping surface based : association pixel triangle par intersection géométrique en XY
- NODATA : valeur indiquant une absence de donnée, ici 9999


