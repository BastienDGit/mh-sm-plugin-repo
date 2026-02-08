# Manuel développeur
Plugin QGIS MH vers SM

## 1. Objectif de ce manuel

Ce document décrit l’architecture, les modules, les conventions, les points d’attention et les procédures de développement du plugin QGIS MH vers SM. Il est destiné à permettre :

- la reprise rapide du code par un nouveau développeur
- l’extension des fonctionnalités sans casser les pipelines existants
- le débogage et la validation reproductible des conversions MH ↔ SM

Le plugin implémente un échange bidirectionnel entre :

- MH : raster 2D ESRI ASCII grid (.asc / .txt)
- SM : fichier .val (une valeur par triangle), ordonné strictement selon scene_triangle.cir

## 2. Environnement d’exécution

### 2.1 Versions cibles

- QGIS : 3.x (testé sous QGIS 3.34)
- Python : celui embarqué par QGIS (par exemple 3.12 sous QGIS récent)

Le plugin doit fonctionner dans l’environnement Python de QGIS. Il ne doit pas supposer un Python système.

### 2.2 Dépendances

Partie cœur (conversion + comparaison), généralement déjà fournies par QGIS :

- qgis / PyQt (API QGIS)
- osgeo.gdal, osgeo.osr
- numpy

Optionnel (visualisation MED) :

- meshio
- pyvista

Bonne pratique : isoler les imports PyVista/meshio dans visu_pyvista.py et ne pas rendre le plugin inutilisable si ces dépendances ne sont pas installées.

## 3. Installation pour développement

### 3.1 Emplacement du plugin

Sous Linux (profil par défaut) :

~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/plugin_mh_sm/

Le dossier du plugin doit contenir au minimum :

- __init__.py
- metadata.txt
- plugin_mh_sm.py
- plugin_mh_sm_dialog.py
- plugin_mh_sm_dialog_base.ui
- src/

### 3.2 Recharge rapide pendant le développement

Dans QGIS :

- Extensions → Installer/Gérer → onglet Installées → désactiver / réactiver le plugin

Après modification du .ui, recharger le plugin afin de recharger la classe générée par uic.loadUiType.

## 4. Architecture générale

Le plugin est séparé en deux couches :

1) Interface QGIS : gestion fenêtre, actions, messages, interaction utilisateur  
2) Logique métier : lecture/écriture fichiers, mapping, calculs, métriques

Cette séparation permet :

- de réduire le couplage au framework QGIS
- de permettre des tests hors QGIS sur la logique métier
- d’isoler les dépendances optionnelles (MED)

## 5. Organisation des fichiers

### 5.1 Interface et orchestration QGIS

- plugin_mh_sm.py  
  - classe MhSmPlugin  
  - connecte les boutons de l’UI aux actions  
  - gère les try/except et l’affichage des erreurs  
  - écrit dans le journal QGIS et dans la barre de messages  
  - centralise les actions : export, reconstruction, comparaison, visualisation

- plugin_mh_sm_dialog.py  
  - classe MhSmDialog  
  - charge plugin_mh_sm_dialog_base.ui  
  - fournit des méthodes d’accès : chemin_mh(), chemin_cir(), chemin_val_sortie(), chemin_val_entree(), chemin_med()  
  - gère les QFileDialog de sélection

- plugin_mh_sm_dialog_base.ui  
  - interface Qt Designer  
  - les noms d’objets (line_mh, btn_export, etc.) sont contractuels

### 5.2 Logique métier

- src/io_mh_sm_exchange.py  
  - lecture raster ASCII MH  
  - lecture scene_triangle.cir (points + triangles + tailles facettes)  
  - alignement par bbox  
  - écriture raster ASCII MH  
  - pipeline MH → SM (écriture .val)  
  - conventions NODATA

- src/mapping.py  
  - conversion XY → indices pixel  
  - mapping barycentre (rapide)  
  - mapping surface-based (fidèle)  
  - projections triangles → raster si nécessaire

### 5.3 Visualisation optionnelle

- visu_pyvista.py  
  - lecture MED (via meshio)  
  - filtres simples (intérieur XY, percentile Z)  
  - rendu PyVista

Cette partie ne doit jamais casser l’exécution du plugin si elle est absente ou si PyVista n’est pas installé.

## 6. Flux fonctionnels (pipelines)

### 6.1 Pipeline MH → SM (export)

Entrées :

- raster MH (.asc / .txt)
- scene_triangle.cir
- chemin sortie .val

Étapes clés :

1. lecture MH (raster, geotransform, nodata)
2. lecture CIR (ordre facettes + triangles)
3. alignement simple par bbox (translation)
4. mapping surface-based triangle ↔ pixels (intersection géométrique)
5. agrégation pixel → triangle (moyenne simple ou pondérée)
6. écriture .val strictement facette par facette

Sortie :

- .val conforme à l’ordre du .cir

### 6.2 Pipeline SM → MH (reconstruction)

Entrées :

- raster MH de référence (grille)
- scene_triangle.cir
- .val

Étapes clés :

1. lecture raster MH ref (grille / géo)
2. lecture CIR + alignement identique
3. reconstruction raster :
   - pour chaque pixel, récupérer triangles qui intersectent ce pixel
   - moyenne des valeurs de triangles valides
4. écriture .asc dans le dossier du .val (nom2asc.asc)
5. ajout dans QGIS

Sortie :

- raster ASCII reconstruit

### 6.3 Comparaison et métriques

Entrées :

- raster MH de référence
- .val
- scene_triangle.cir

Sorties :

- *_mh_ref.tif
- *_mh_reconstruit.tif
- *_mh_erreur.tif

Métriques :

- n_valid
- mae
- rmse
- corr

Restitution :

- journal QGIS (obligatoire)
- messageBar (résumé optionnel)

## 7. Contrats de format et invariants

### 7.1 Raster MH (ESRI ASCII grid)

Contrat minimal :

- en-tête ESRI standard : ncols, nrows, xllcorner, yllcorner, cellsize, NODATA_value
- cohérence grille / géoréférencement

Conventions projet :

- NODATA fichier : 9999 (ou -9999 selon le jeu de données, mais il faut rester cohérent)
- en interne : conversion NODATA → NaN pour sécuriser les moyennes

Point critique : si NODATA change, l’ensemble des métriques et reconstructions sera impacté. Conserver une constante unique (ex. NODATA_MH) et l’utiliser partout.

### 7.2 Fichier .cir

Le .cir est la référence d’ordre. Le .val dépend entièrement de cet ordre.

Contrats :

- découpage facettes : lignes f i n
- n triangles attendus ensuite
- extraction des triangles dans l’ordre exact

### 7.3 Fichier .val

Contrat :

- une valeur par triangle
- valeurs écrites par facette
- le nombre de valeurs par facette doit correspondre au n annoncé dans le .cir

## 8. Gestion des performances

Le coût dominant est le mapping surface-based (intersection triangle/pixel).

Points de vigilance :

- plus le raster est fin et le maillage dense, plus le mapping est coûteux
- les intersections géométriques (shapely) sont robustes mais lourdes

Optimisations possibles :

- limiter les pixels testés à la bbox du triangle (déjà fait)
- mise en cache du mapping (clé = shape + geotransform + triangles après alignement)
- mode barycentre-based comme option rapide

## 9. Logs et erreurs

### 9.1 Logs

Le plugin doit écrire dans le journal QGIS via QgsMessageLog.

Bonne pratique :

- niveau Info pour les étapes principales
- niveau Warning pour les cas non bloquants
- niveau Critical pour les exceptions

Éviter de dépendre de print() : la console Python n’est pas toujours visible et les prints peuvent être perdus.

### 9.2 Erreurs

Chaque action UI doit être encapsulée dans un try/except :

- capturer traceback.format_exc()
- journaliser l’erreur
- afficher un QMessageBox.critical pour informer l’utilisateur

## 10. Interface UI : conventions et pièges

### 10.1 Noms d’objets Qt

Les noms doivent correspondre à ceux utilisés dans plugin_mh_sm_dialog.py. Exemple :

- line_mh, btn_mh
- line_cir, btn_cir
- line_val, btn_val
- btn_export
- line_val_in, btn_val_in, btn_reconstruire, btn_comparer
- line_med, btn_med, btn_visu_med

Si un nom change dans le .ui, il faut mettre à jour le code Python.

### 10.2 Résultats utilisateurs

Les métriques doivent apparaître dans le journal QGIS, pas uniquement dans une console.

Si tu ajoutes une zone de texte dédiée dans l’UI :

- ajouter un widget QPlainTextEdit (en lecture seule)
- écrire un résumé des métriques après comparaison

## 11. Procédure de validation développeur

### 11.1 Validation fonctionnelle minimale

1) Lancer MH → SM et vérifier :

- .val écrit
- nombre total de valeurs = nombre total de triangles

2) Lancer SM → MH :

- .asc créé (nom2asc.asc)
- raster chargeable dans QGIS

3) Lancer Comparaison :

- trois GeoTIFF générés
- métriques présentes dans le journal
- carte d’erreur cohérente

### 11.2 Vérification de cohérence .cir / .val

En cas de doute :

- compter les tailles de facettes dans .cir
- lire .val et vérifier les tailles de blocs
- vérifier total triangles = total valeurs

## 12. Extensions recommandées (perspectives techniques)

- choix utilisateur barycentre-based / surface-based
- mise en cache du mapping surface-based
- alignement rigide (rotation + translation) si jeux de données désalignés
- affichage des métriques directement dans l’UI
- export d’un rapport de comparaison (CSV + métadonnées)

## 13. Conventions de contribution

Recommandations :

- docstrings systématiques sur les fonctions exposées
- aucune logique métier dans MhSmDialog
- éviter les constantes “magiques” non centralisées (NODATA, chemins)
- protéger les imports optionnels (PyVista/meshio)
- conserver des noms de variables stables (éviter les renommages inutiles)

## 14. Débogage : erreurs fréquentes

### ImportError sur une fonction

Cause :

- une fonction a été supprimée ou renommée (ex. filtre_interieur)

Solution :

- vérifier les imports dans visu_pyvista.py
- vérifier le contenu réel de src/preprocessing.py
- éviter les doublons de modules et nettoyer les fichiers obsolètes

### Métriques non visibles

Cause :

- usage de print() uniquement

Solution :

- écrire via QgsMessageLog et éventuellement afficher un résumé via messageBar


