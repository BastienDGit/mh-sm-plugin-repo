# -*- coding: utf-8 -*-
"""
src/preprocessing.py

Ce module regroupe des fonctions simples de prétraitement utilisées dans le projet.

Contenu
-------
1) Nettoyage raster
   - nodata_nan : remplace la valeur nodata par NaN
   - filtre_sigma : filtre simple de valeurs aberrantes (k-sigma)

2) Filtrage géométrique sur un maillage triangulé (MED)
   - filtre_z : garde les triangles dont le barycentre respecte une contrainte en Z
   - filtre_interieur : garde les triangles dont le barycentre est dans une zone intérieure XY

Remarques importantes
---------------------
- Les fonctions de filtrage triangles travaillent à partir du barycentre des triangles.
- Ces filtres sont surtout utilisés pour une visualisation, pas pour la conversion MH SM.
- Aucune impression écran n'est faite ici, ce module ne fait que retourner des résultats.
"""

import numpy as np


def nodata_nan(arr, nodata):
    """
    Remplace la valeur NODATA par NaN dans un raster.

    Cette fonction est utile pour travailler ensuite avec numpy en ignorant
    naturellement les pixels nodata via np.isfinite ou np.nanmean.

    Paramètres
    ----------
    arr : np.ndarray
        Tableau raster (souvent 2D). Il peut être en int ou float.
    nodata : float ou int ou None
        Valeur nodata à remplacer. Si None, le raster est simplement converti en float.

    Retour
    ------
    np.ndarray
        Copie du raster en float, avec NaN à la place du nodata.
    """
    data = np.asarray(arr).astype(float, copy=True)

    if nodata is not None:
        data[data == float(nodata)] = np.nan

    return data


def filtre_sigma(data, k=3.0):
    """
    Filtre simple de valeurs aberrantes par méthode k-sigma.

    Principe :
    - on calcule moyenne et écart-type sur les valeurs valides
    - on remplace par NaN les valeurs en dehors de l'intervalle :
      [moyenne - k*std, moyenne + k*std]

    Paramètres
    ----------
    data : np.ndarray
        Raster float avec NaN sur les pixels invalides.
    k : float
        Facteur sigma, typiquement 2 à 4.

    Retour
    ------
    tuple[np.ndarray, tuple]
        data_filtre : np.ndarray
            Copie de data avec les valeurs aberrantes mises à NaN.
        stats : tuple
            (moyenne, std, borne_basse, borne_haute)
            Peut contenir NaN si aucune valeur valide.
    """
    d = np.asarray(data).astype(float, copy=False)
    valid = d[np.isfinite(d)]

    if valid.size == 0:
        return d.copy(), (np.nan, np.nan, np.nan, np.nan)

    moyenne = float(np.mean(valid))
    std = float(np.std(valid))

    borne_basse = moyenne - float(k) * std
    borne_haute = moyenne + float(k) * std

    out = d.copy()
    masque_outliers = (out < borne_basse) | (out > borne_haute)
    out[masque_outliers] = np.nan

    return out, (moyenne, std, borne_basse, borne_haute)


def filtre_z(points, triangles, z_min=None, z_max=None, mask=False):
    """
    Filtre des triangles selon l'altitude Z de leur barycentre.

    Le barycentre est calculé sur les 3 sommets du triangle :
    barycentre = moyenne des coordonnées des 3 points.

    Paramètres
    ----------
    points : np.ndarray
        Coordonnées des points, tableau (N, 3).
    triangles : np.ndarray
        Indices des triangles, tableau (M, 3).
    z_min : float ou None
        Si défini, on conserve uniquement les triangles dont le barycentre vérifie z >= z_min.
    z_max : float ou None
        Si défini, on conserve uniquement les triangles dont le barycentre vérifie z <= z_max.
    mask : bool
        Si True, retourne aussi le masque booléen des triangles conservés.

    Retour
    ------
    np.ndarray ou tuple[np.ndarray, np.ndarray]
        triangles_filtrés
        ou (triangles_filtrés, masque)
    """
    pts = np.asarray(points)
    tri = np.asarray(triangles)

    if tri.size == 0:
        masque = np.zeros((0,), dtype=bool)
        return (tri, masque) if mask else tri

    bary = pts[tri].mean(axis=1)
    z = bary[:, 2]

    keep = np.ones((tri.shape[0],), dtype=bool)

    if z_min is not None:
        keep &= (z >= float(z_min))

    if z_max is not None:
        keep &= (z <= float(z_max))

    if mask:
        return tri[keep], keep

    return tri[keep]


def filtre_interieur(points, triangles, marge=0.1, mask=False):
    """
    Filtre des triangles dont le barycentre est à l'intérieur d'une zone XY.

    L'objectif est d'exclure les triangles proches des bords du modèle.
    On construit une bbox XY globale basée sur les barycentres, puis on retire
    une marge relative sur chaque côté.

    Exemple :
    - marge = 0.10 retire 10 pourcent de la largeur à gauche et à droite,
      et 10 pourcent de la hauteur en bas et en haut.

    Paramètres
    ----------
    points : np.ndarray
        Coordonnées des points, tableau (N, 3).
    triangles : np.ndarray
        Indices des triangles, tableau (M, 3).
    marge : float
        Marge relative (0 à 0.49 recommandé). Si 0, aucun filtrage intérieur.
    mask : bool
        Si True, retourne aussi le masque booléen des triangles conservés.

    Retour
    ------
    np.ndarray ou tuple[np.ndarray, np.ndarray]
        triangles_filtrés
        ou (triangles_filtrés, masque)
    """
    pts = np.asarray(points)
    tri = np.asarray(triangles)

    if tri.size == 0:
        masque = np.zeros((0,), dtype=bool)
        return (tri, masque) if mask else tri

    marge = float(marge)
    if marge < 0:
        marge = 0.0
    if marge >= 0.5:
        marge = 0.49

    bary = pts[tri].mean(axis=1)
    x = bary[:, 0]
    y = bary[:, 1]

    xmin = float(np.min(x))
    xmax = float(np.max(x))
    ymin = float(np.min(y))
    ymax = float(np.max(y))

    dx = xmax - xmin
    dy = ymax - ymin

    if dx <= 0 or dy <= 0:
        keep = np.ones((tri.shape[0],), dtype=bool)
        return (tri[keep], keep) if mask else tri[keep]

    xmin_i = xmin + marge * dx
    xmax_i = xmax - marge * dx
    ymin_i = ymin + marge * dy
    ymax_i = ymax - marge * dy

    keep = (x >= xmin_i) & (x <= xmax_i) & (y >= ymin_i) & (y <= ymax_i)

    if mask:
        return tri[keep], keep

    return tri[keep]

