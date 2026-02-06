# -*- coding: utf-8 -*-
"""


Ce module regroupe les fonctions de correspondance entre :
- un raster (grille de pixels) défini par une géotransformée GDAL
- un maillage triangulé (points + triangles)

Deux approches de mapping sont proposées (on pourra en développer des plus performantes à l'avenir j'en ai testé deux pendant le projet):

1) Mapping par barycentre (rapide)
   Chaque triangle est affecté à un seul pixel : celui qui contient son barycentre XY.

2) Mapping "surface-based" +couteux 
   Chaque triangle est intersecté avec les pixels de la grille.
   On conserve, pour chaque pixel, la liste des triangles qui l'intersectent et l'aire
   d'intersection correspondante.

Le mapping "surface-based" est utilisé pour les conversions MH vers SM et SM vers MH,
car il est plus cohérent géométriquement.
"""

import numpy as np
from shapely.geometry import Polygon, box


def xy_vers_pixel(x, y, gt):
    """
    Convertit une coordonnée monde (x, y) en indices raster (ligne, colonne).

    La géotransformée GT est au format GDAL :
      gt = (x_min, dx, rx, y_max, ry, dy)

    Hypothèses utilisées ici (cas standard raster nord en haut) :
    - dx > 0
    - dy < 0
    - rx et ry sont généralement à 0 (pas de rotation)
      Si le raster est tourné, cette conversion n'est plus strictement correcte.

    Paramètres
    ----------
    x : float
        Coordonnée monde x.
    y : float
        Coordonnée monde y.
    gt : tuple
        Géotransformée GDAL.

    Retour
    ------
    tuple[int, int]
        (ligne, colonne) en indices entiers.
    """
    colonne = int((x - gt[0]) / gt[1])
    ligne = int((y - gt[3]) / gt[5])
    return ligne, colonne


def mapping_barycentre(points, triangles, gt, shape_raster):
    """
    Associe chaque triangle à un pixel en utilisant le barycentre XY du triangle.

    Cette méthode est rapide et utile pour des aperçus ou des projections simples.
    Elle ne tient pas compte de la surface réellement couverte par le triangle.

    Paramètres
    ----------
    points : np.ndarray
        Tableau (N, 3) des coordonnées xyz.
    triangles : np.ndarray
        Tableau (M, 3) des indices de sommets.
    gt : tuple
        Géotransformée GDAL du raster.
    shape_raster : tuple
        Forme du raster (nb_lignes, nb_colonnes).

    Retour
    ------
    dict
        Dictionnaire :
        mapping[(ligne, colonne)] = [id_triangle, id_triangle, ...]
        Un pixel peut contenir plusieurs triangles.
    """
    nb_lignes, nb_colonnes = shape_raster
    mapping = {}

    triangles_xy = points[triangles][:, :, :2]
    barycentres = triangles_xy.mean(axis=1)

    for id_tri, (x, y) in enumerate(barycentres):
        ligne, colonne = xy_vers_pixel(float(x), float(y), gt)

        if not (0 <= ligne < nb_lignes and 0 <= colonne < nb_colonnes):
            continue

        mapping.setdefault((ligne, colonne), []).append(int(id_tri))

    return mapping


def projette_triangles_vers_raster(valeurs, mapping, shape_raster, agg="mean", fill=np.nan):
    """
    Projette un champ défini sur les triangles vers une grille raster.

    Le mapping attendu est celui produit par mapping_barycentre :
    mapping[(ligne, colonne)] = liste d'indices de triangles.

    Si plusieurs triangles tombent dans le même pixel, une agrégation est appliquée.

    Paramètres
    ----------
    valeurs : array_like
        Tableau (n_tri,) contenant une valeur par triangle.
    mapping : dict
        Dictionnaire pixel -> liste d'indices de triangles.
    shape_raster : tuple
        Forme du raster (nb_lignes, nb_colonnes).
    agg : str
        Agrégation utilisée si plusieurs triangles sont dans un pixel.
        Valeurs possibles :
        mean, median, sum, min, max, first, count, mode
    fill : float
        Valeur par défaut utilisée pour initialiser le raster de sortie.

    Retour
    ------
    np.ndarray
        Raster 2D (nb_lignes, nb_colonnes) en float.
    """
    nb_lignes, nb_colonnes = shape_raster
    raster = np.full((nb_lignes, nb_colonnes), fill, dtype=float)

    valeurs = np.asarray(valeurs, dtype=float)

    for (ligne, colonne), ids_triangles in mapping.items():
        if not ids_triangles:
            continue

        if agg == "count":
            raster[ligne, colonne] = float(len(ids_triangles))
            continue

        v = valeurs[ids_triangles]

        if np.all(np.isnan(v)):
            continue

        if agg == "mean":
            raster[ligne, colonne] = float(np.nanmean(v))
        elif agg == "median":
            raster[ligne, colonne] = float(np.nanmedian(v))
        elif agg == "sum":
            raster[ligne, colonne] = float(np.nansum(v))
        elif agg == "min":
            raster[ligne, colonne] = float(np.nanmin(v))
        elif agg == "max":
            raster[ligne, colonne] = float(np.nanmax(v))
        elif agg == "first":
            for valeur in v:
                if not np.isnan(valeur):
                    raster[ligne, colonne] = float(valeur)
                    break
        elif agg == "mode":
            vv = v[~np.isnan(v)]
            if vv.size == 0:
                continue
            uniques, comptes = np.unique(vv, return_counts=True)
            raster[ligne, colonne] = float(uniques[int(np.argmax(comptes))])
        else:
            raise ValueError("Agrégateur inconnu " + str(agg))

    return raster


def projette_plusieurs_champs(champs_triangles, mapping, shape_raster, agg="mean", fill=np.nan):
    """
    Projette plusieurs champs triangles vers des rasters en une seule passe logique.

    Paramètres
    ----------
    champs_triangles : dict
        Dictionnaire {nom_champ: valeurs_triangles}, où valeurs_triangles a une taille (n_tri,).
    mapping : dict
        Dictionnaire pixel -> liste de triangles (mapping barycentre).
    shape_raster : tuple
        Forme du raster (nb_lignes, nb_colonnes).
    agg : str
        Agrégation à appliquer dans projette_triangles_vers_raster.
    fill : float
        Valeur par défaut du raster.

    Retour
    ------
    dict
        Dictionnaire {nom_champ: raster_2d}.
    """
    rasters = {}

    for nom, valeurs in champs_triangles.items():
        rasters[nom] = projette_triangles_vers_raster(
            valeurs=valeurs,
            mapping=mapping,
            shape_raster=shape_raster,
            agg=agg,
            fill=fill
        )

    return rasters


def inverse_mapping(mapping_pixel, nb_triangles):
    """
    Transforme un mapping pixel -> triangles en triangle -> pixel.

    Règle utilisée ici :
    - chaque triangle est associé au premier pixel rencontré dans le dictionnaire
      si jamais il apparaît dans plusieurs pixels (cas rare avec le barycentre).

    Paramètres
    ----------
    mapping_pixel : dict
        Dictionnaire pixel -> liste d'indices de triangles.
    nb_triangles : int
        Nombre total de triangles.

    Retour
    ------
    np.ndarray
        Tableau (nb_triangles, 2) contenant (ligne, colonne) pour chaque triangle.
        Si un triangle n'est pas mappé, on laisse (-1, -1).
    """
    tri_vers_pixel = np.full((int(nb_triangles), 2), -1, dtype=int)

    for (ligne, colonne), ids_triangles in mapping_pixel.items():
        for id_tri in ids_triangles:
            if tri_vers_pixel[int(id_tri), 0] == -1:
                tri_vers_pixel[int(id_tri), 0] = int(ligne)
                tri_vers_pixel[int(id_tri), 1] = int(colonne)

    return tri_vers_pixel


def mapping_surface(points, triangles, gt, shape_raster):
    """
    Mapping surface-based (intersection triangle / pixel).

    Pour chaque pixel intersecté par un triangle, on stocke :
      (id_triangle, aire_intersection)

    C'est plus fidèle qu'un barycentre, mais plus coûteux car on fait beaucoup
    d'intersections géométriques.

    Paramètres
    ----------
    points : np.ndarray
        Tableau (N, 3) des coordonnées xyz.
    triangles : np.ndarray
        Tableau (M, 3) des indices de sommets.
    gt : tuple
        Géotransformée GDAL du raster.
    shape_raster : tuple
        Forme du raster (nb_lignes, nb_colonnes).

    Retour
    ------
    dict
        Dictionnaire :
        mapping[(ligne, colonne)] = [(id_tri, aire), ...]
    """
    nb_lignes, nb_colonnes = shape_raster
    x0, dx, _, y0, _, dy = gt

    mapping = {}

    for id_tri, tri in enumerate(triangles):
        pts = points[tri]

        poly_tri = Polygon([
            (float(pts[0, 0]), float(pts[0, 1])),
            (float(pts[1, 0]), float(pts[1, 1])),
            (float(pts[2, 0]), float(pts[2, 1])),
        ])

        if poly_tri.is_empty or poly_tri.area <= 0:
            continue

        minx, miny, maxx, maxy = poly_tri.bounds

        col_min = int(np.floor((minx - x0) / dx))
        col_max = int(np.floor((maxx - x0) / dx))

        lig_min = int(np.floor((maxy - y0) / dy))
        lig_max = int(np.floor((miny - y0) / dy))

        col_min = max(col_min, 0)
        lig_min = max(lig_min, 0)
        col_max = min(col_max, nb_colonnes - 1)
        lig_max = min(lig_max, nb_lignes - 1)

        for ligne in range(lig_min, lig_max + 1):
            for colonne in range(col_min, col_max + 1):

                px_min = x0 + colonne * dx
                px_max = x0 + (colonne + 1) * dx

                py_max = y0 + ligne * dy
                py_min = y0 + (ligne + 1) * dy

                poly_pixel = box(float(px_min), float(py_min), float(px_max), float(py_max))

                inter = poly_tri.intersection(poly_pixel)
                if inter.is_empty:
                    continue

                aire = float(inter.area)
                if aire <= 0:
                    continue

                mapping.setdefault((ligne, colonne), []).append((int(id_tri), aire))

    return mapping


def projette_triangles_surface(valeurs, mapping_surface, shape_raster, fill=np.nan):
    """
    Projection triangles -> raster en utilisant un mapping surface-based.

    Pour un pixel donné, si plusieurs triangles l'intersectent, la valeur du pixel
    est une moyenne pondérée par les aires d'intersection :

    valeur_pixel = somme(valeur_triangle * aire) / somme(aire)

    Paramètres
    ----------
    valeurs : array_like
        Tableau (n_tri,) contenant une valeur par triangle.
    mapping_surface : dict
        Dictionnaire pixel -> liste (id_triangle, aire_intersection).
    shape_raster : tuple
        Forme du raster (nb_lignes, nb_colonnes).
    fill : float
        Valeur par défaut pour initialiser le raster.

    Retour
    ------
    np.ndarray
        Raster 2D en float.
    """
    nb_lignes, nb_colonnes = shape_raster
    raster = np.full((nb_lignes, nb_colonnes), fill, dtype=float)

    valeurs = np.asarray(valeurs, dtype=float)

    for (ligne, colonne), liste in mapping_surface.items():
        num = 0.0
        den = 0.0

        for id_tri, aire in liste:
            v = valeurs[int(id_tri)]
            if np.isnan(v):
                continue
            a = float(aire)
            num += float(v) * a
            den += a

        if den > 0:
            raster[ligne, colonne] = num / den

    return raster

