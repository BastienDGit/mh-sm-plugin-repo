# Manuel utilisateur
Plugin QGIS MH vers SM

## 1. Objectif

Ce plugin QGIS permet d’échanger des champs entre deux représentations géométriques et deux formats de fichiers utilisés dans le couplage MH–SM :

- MH : raster 2D au format ESRI ASCII grid (.asc ou .txt)
- SM : fichier .val contenant une valeur par triangle, ordonnée selon un fichier fichier.cir

Le plugin couvre trois usages principaux :

- Conversion MH vers SM : génération d’un fichier .val à partir d’un raster MH et d’un fichier .cir
- Conversion SM vers MH : reconstruction d’un raster .asc à partir d’un fichier .val, en réutilisant la grille d’un raster MH de référence
- Contrôle et validation : comparaison MH de référence vs MH reconstruit, calcul de métriques et génération d’une carte d’erreur

Une visualisation MED (maillage 3D) via PyVista peut être disponible de manière optionnelle selon l’installation.

## 2. Prérequis

### 2.1 Logiciels

- QGIS 3.x installé et opérationnel
- Plugin MH vers SM installé dans le répertoire des extensions QGIS

### 2.2 Données nécessaires

Selon les fonctionnalités utilisées, vous aurez besoin de :

- Un raster MH au format ESRI ASCII grid
  - Extension .asc ou .txt
  - En-tête ESRI ASCII standard : ncols, nrows, xllcorner, yllcorner, cellsize, NODATA_value
- Un fichier .cir qu'on retroue dans ../data/
  - Définit l’ordre officiel des triangles, structuré par facettes
- Un fichier SM .val
  - Contient une valeur par triangle
  - Écriture facette par facette, dans l’ordre exact du .cir

### 2.3 Convention NODATA

Convention imposée par le projet :

- NODATA en entrée MH : -9999
- NODATA en sortie MH : -9999

Le plugin convertit en interne les NODATA en NaN afin d’éviter toute pollution des moyennes et des métriques, puis réécrit -9999 lors des sorties raster.

## 3. Installation

### 3.1 Copie du plugin dans le dossier QGIS

Copier le dossier du plugin dans le répertoire des plugins QGIS de l’utilisateur.

Sous Linux, emplacement typique :
- ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/

Contenu minimal attendu dans le dossier du plugin :

- plugin_mh_sm.py
- plugin_mh_sm_dialog.py
- plugin_mh_sm_dialog_base.ui
- src/
- metadata.txt
- __init__.py

###3.2 Bibliothèques nécessaire pour le plugin 

Normalement déjà dans QGIS 
qgis / PyQt (API QGIS)
osgeo (gdal, osr)
numpy  

Bibliothèques supplémentaires pour la visualisation 3D : 

(Besoin de python 3.10) 

Pyvista : pip install Pyvista 

Meshio : pip install Meshio 

commandes pour installer les bibliothèques sous linux : 

/usr/bin/python3 -m pip install --user meshio

/usr/bin/python3 -m pip install --user pyvista --no-deps

sudo apt install python3-h5py




### 3.3 Activation dans QGIS

Dans QGIS :

1. Extensions
2. Installer et gérer les extensions
3. Onglet Installées
4. Activer Plugin MH vers SM

Une entrée de menu et une icône apparaissent après activation.

## 4. Lancement et interface

Le plugin se lance :

- via l’icône dans la barre d’outils
- ou via le menu Extensions

L’interface est structurée en blocs :

- Pipeline MH vers SM (.val)
- Pipeline SM vers MH (.asc)
- Outils
- MED (optionnel)

Recommandation : sélectionner d’abord MH et le fichier .cir associé, puis renseigner le .val selon l’action.

## 5. Pipeline MH vers SM

### 5.1 Objectif

Générer un fichier SM .val à partir d’un raster MH, en respectant strictement l’ordre officiel des triangles défini dans un fichier .cir.

### 5.2 Entrées

- Entrée MH (.txt ou .asc) : raster ESRI ASCII grid
- fichier.cir : ordre des triangles et découpage en facettes
- Sortie SM (.val) : fichier à créer

### 5.3 Procédure

1. Dans Pipeline MH vers SM, cliquer sur Parcourir et sélectionner le raster MH
2. Cliquer sur Parcourir et sélectionner fichier.cir
3. Cliquer sur Choisir et définir le fichier de sortie .val
4. Cliquer sur Lancer MH → SM (.val)

### 5.4 Résultat attendu

- Le fichier .val est écrit à l’emplacement choisi
- Un message de confirmation apparaît dans la barre de messages QGIS

### 5.5 Problèmes courants

Le raster MH est introuvable  
Vérifier le chemin et les droits de lecture.

Le fichier .cir est introuvable ou incorrect  
Vérifier que le fichier sélectionné est bien le fichier.cir associé au raster et au même site.

Le fichier de sortie .val est vide  
Vérifier que le chemin de sortie a été renseigné et que le dossier est accessible en écriture.

## 6. Pipeline SM vers MH

### 6.1 Objectif

Reconstruire un raster MH (ESRI ASCII grid) à partir d’un fichier SM .val, en réutilisant la grille et le géoréférencement d’un raster MH de référence.

### 6.2 Entrées

- MH de référence : sert à récupérer la grille, l’emprise et les métadonnées raster
- fichier.cir : ordre officiel des triangles
- Entrée SM (.val) : fichier existant

### 6.3 Sortie

- Un fichier .asc est écrit dans le même dossier que le .val
- Nom automatique : nom_du_val2asc.asc

Exemple : test5.val produit test52asc.asc

### 6.4 Procédure

1. Sélectionner le raster MH de référence dans Entrée MH
2. Sélectionner fichier.cir dans le champ correspondant
3. Dans Pipeline SM vers MH, cliquer sur Parcourir et sélectionner le fichier .val
4. Cliquer sur Lancer SM → MH (.asc)

### 6.5 Résultat attendu

- Le fichier .asc reconstruit est créé dans le dossier du .val
- Le raster reconstruit peut être ajouté automatiquement au projet QGIS selon la configuration du plugin

### 6.6 Problèmes courants

Le raster reconstruit n’apparaît pas dans QGIS  
Vérifier que le fichier .asc a bien été créé dans le dossier du .val et l’ajouter manuellement si nécessaire.

Résultats incohérents  
Vérifier que le .val et le .cir sont cohérents et appartiennent à la même scène. Vérifier également que le MH de référence correspond au même site (même emprise, même résolution).

## 7. Comparaison rasters

### 7.1 Objectif

Comparer le raster MH de référence avec le raster reconstruit depuis un .val, calculer des métriques et produire une carte d’erreur.

### 7.2 Entrées

- MH de référence
- fichier.cir
- fichier .val

### 7.3 Sorties

Trois GeoTIFF sont produits dans le dossier du .val :

- base_mh_ref.tif
- base_mh_reconstruit.tif
- base_mh_erreur.tif

base correspond au nom du .val sans extension.

### 7.4 Métriques calculées

Les métriques sont calculées uniquement sur les pixels valides :

- n_valid : nombre de pixels comparés
- mae : erreur absolue moyenne
- rmse : racine de l’erreur quadratique moyenne
- corr : corrélation linéaire

### 7.5 Procédure

1. Sélectionner le MH de référence
2. Sélectionner fichier.cir
3. Sélectionner le fichier .val
4. Cliquer sur Comparer MH vs reconstruit (métriques + erreur)

### 7.6 Où lire les résultats

Les métriques sont écrites dans le journal QGIS du plugin.

Pour afficher le journal :

1. Vue
2. Panneaux
3. Journal des messages
4. Filtrer sur mh_sm_plugin

Selon l’environnement, des informations peuvent également apparaître dans la console Python QGIS, mais le journal est le support de référence.

### 7.7 Résultat attendu

- Les métriques apparaissent dans le journal QGIS
- La carte d’erreur est disponible pour analyser spatialement les écarts

## 8. Outils

### 8.1 Afficher MH dans QGIS

Cette action charge dans QGIS le raster MH sélectionné, sans transformation, pour contrôle visuel.

Procédure :

1. Sélectionner un raster MH
2. Cliquer sur Afficher MH dans QGIS

## 9. Visualisation MED (optionnelle)

Cette fonctionnalité ouvre une fenêtre PyVista pour visualiser un maillage 3D.

### 9.1 Entrée

- un fichier .med

### 9.2 Fonctionnement

- lecture du fichier MED
- filtrage intérieur en XY
- filtrage en Z selon un percentile
- affichage du maillage triangulé

### 9.3 Dépendances

- pyvista
- meshio

Si ces bibliothèques ne sont pas disponibles, il est recommandé de désactiver la visualisation MED ou d’installer les dépendances dans l’environnement Python de QGIS.

## 10. Workflow recommandé

Pour un nouveau jeu de données :

1. Charger le MH de référence dans QGIS pour vérifier emprise et valeurs
2. Lancer MH → SM afin de produire un .val
3. Lancer SM → MH afin de reconstruire un .asc
4. Lancer la comparaison
5. Interpréter :
   - les métriques (n_valid, MAE, RMSE, corr)
   - la carte d’erreur
   - la cohérence visuelle des couches

## 11. Diagnostic et dépannage

### 11.1 Une action ne produit aucun résultat visible

Consulter le journal QGIS et vérifier la présence d’une erreur Python ou d’un message d’arrêt. Vérifier également que tous les chemins requis sont renseignés.

### 11.2 Erreurs de permission ou d’accès aux fichiers

Vérifier les droits de lecture et d’écriture sur les fichiers et dossiers. Vérifier que le fichier n’est pas verrouillé par un autre logiciel et que QGIS a accès au dossier de sortie.

### 11.3 Léger écart entre en-têtes ASCII

De petites différences numériques peuvent apparaître dans les en-têtes ASCII à cause de l’écriture en flottants. Cela ne correspond pas forcément à un décalage réel des données. Comparer xllcorner, yllcorner et cellsize et valider visuellement dans QGIS.

### 11.4 Aucun pixel valide lors de la comparaison

Vérifier que le MH de référence et le MH reconstruit partagent la même convention NODATA et que le reconstruit contient des valeurs finies. Vérifier également la cohérence du triplet MH, .cir, .val.



