# -*- coding: utf-8 -*-
"""
src/alignment.py

Ce module contient des fonctions utilitaires pour aligner un maillage 3D
sur une grille raster 2D.

Le cas d'usage principal est l'échange MH (raster) <-> SM (maillage) :
les données n'étant pas forcément parfaitement superposées, on applique
un alignement simple (rigide) basé sur :
- une rotation dans le plan XY (optionnelle)
- une translation XY pour superposer les centres des boites englobantes

Important :
- L'alignement ici est volontairement simple ce qui a crée probablement un décalage d'emprise entre les deux rasters (pas de recalage fin).
- Les fonctions ne modifient jamais le tableau d'entrée, elles renvoient
  toujours une copie.
"""

from __future__ import annotations

import numpy as np


def bbox_raster(geo_transforme, forme_raster):
    """
    Calcule la boite englobante d'un raster en coordonnées monde.

    Paramètres
    ----------
    geo_transforme : tuple[float, float, float, float, float, float]
        Geotransform GDAL de la grille raster :
        (x_min, pas_x, rot1, y_max, rot2, pas_y)
        En pratique, rot1 et rot2 valent souvent 0.
        pas_y est généralement négatif car les lignes descendent vers le sud.
    forme_raster : tuple[int, int]
        Forme numpy du raster : (nb_lignes, nb_colonnes).

    Retour
    ------
    tuple[float, float, float, float]
        (x_min, x_max, y_min, y_max) en coordonnées monde.

    Notes
    -----
    La formule utilisée est cohérente avec le format ESRI ASCII grid :
    - x_min correspond au coin bas gauche (xllcorner)
    - y_max correspond au bord nord de la grille
    """
    nb_lignes, nb_colonnes = forme_raster

    x_min = float(geo_transforme[0])
    pas_x = float(geo_transforme[1])
    y_max = float(geo_transforme[3])
    pas_y = float(geo_transforme[5])

    x_max = x_min + pas_x * nb_colonnes
    y_min = y_max + pas_y * nb_lignes

    # On renvoie bien (xmin, xmax, ymin, ymax)
    return float(x_min), float(x_max), float(y_min), float(y_max)


def bbox_maillage(pts):
    """
    Calcule la boite englobante XY d'un maillage.

    Paramètres
    ----------
    pts : np.ndarray
        Tableau (N, 3) ou (N, 2). Les deux premières colonnes sont X et Y.

    Retour
    ------
    tuple[float, float, float, float]
        (x_min, x_max, y_min, y_max) en coordonnées monde.
    """
    pts = np.asarray(pts)
    if pts.ndim != 2 or pts.shape[1] < 2:
        raise ValueError("pts doit être un tableau de forme (N,2) ou (N,3)")

    x = pts[:, 0].astype(float)
    y = pts[:, 1].astype(float)

    return float(x.min()), float(x.max()), float(y.min()), float(y.max())


def translation_maillage(pts, geo_transforme, forme_raster):
    """
    Translater un maillage en XY pour aligner le centre de sa boite englobante
    sur le centre de la boite englobante du raster.

    Paramètres
    ----------
    pts : np.ndarray
        Tableau (N,3) (ou (N,2)) des points du maillage.
    geo_transforme : tuple
        Geotransform GDAL du raster.
    forme_raster : tuple[int, int]
        Forme (nb_lignes, nb_colonnes) du raster.

    Retour
    ------
    tuple[np.ndarray, tuple[float, float]]
        - pts_translates : copie des points avec translation appliquée
        - (tx, ty) : translation XY appliquée

    Notes
    -----
    Ce n'est pas un recalage précis, mais une translation globale.
    C'est utile quand le maillage et le raster sont dans le même repère
    mais avec un léger décalage de position.
    """
    x_min_r, x_max_r, y_min_r, y_max_r = bbox_raster(geo_transforme, forme_raster)
    x_min_m, x_max_m, y_min_m, y_max_m = bbox_maillage(pts)

    # Centre du raster
    cx_r = 0.5 * (x_min_r + x_max_r)
    cy_r = 0.5 * (y_min_r + y_max_r)

    # Centre du maillage
    cx_m = 0.5 * (x_min_m + x_max_m)
    cy_m = 0.5 * (y_min_m + y_max_m)

    tx = cx_r - cx_m
    ty = cy_r - cy_m

    pts2 = np.array(pts, dtype=float, copy=True)
    pts2[:, 0] += tx
    pts2[:, 1] += ty

    return pts2, (float(tx), float(ty))


def rotation_xy(pts, angle_deg, centre_xy=None):
    """
    Applique une rotation dans le plan XY autour d'un centre.

    Paramètres
    ----------
    pts : np.ndarray
        Tableau (N,3) ou (N,2). Les colonnes 0 et 1 représentent X et Y.
    angle_deg : float
        Angle de rotation en degrés. Sens trigonométrique.
    centre_xy : tuple[float, float] ou None
        Centre de rotation (cx, cy).
        Si None, le centre est la moyenne des XY du maillage.

    Retour
    ------
    np.ndarray
        Copie des points avec rotation appliquée sur X et Y.
        La coordonnée Z, si présente, est conservée telle quelle.
    """
    pts = np.asarray(pts)
    if pts.ndim != 2 or pts.shape[1] < 2:
        raise ValueError("pts doit être un tableau de forme (N,2) ou (N,3)")

    theta = float(np.deg2rad(angle_deg))

    if centre_xy is None:
        centre_xy = pts[:, :2].astype(float).mean(axis=0)

    cx = float(centre_xy[0])
    cy = float(centre_xy[1])

    cos_t = float(np.cos(theta))
    sin_t = float(np.sin(theta))

    # Matrice de rotation 2D
    rot = np.array([[cos_t, -sin_t],
                    [sin_t,  cos_t]], dtype=float)

    pts2 = np.array(pts, dtype=float, copy=True)

    # On recentre sur le centre choisi, on tourne, puis on remet dans le repère initial
    xy = pts2[:, :2] - np.array([cx, cy], dtype=float)
    xy_rot = xy @ rot.T
    pts2[:, 0] = xy_rot[:, 0] + cx
    pts2[:, 1] = xy_rot[:, 1] + cy

    return pts2


def alignement_rigide(pts, geo_transforme, forme_raster, angle_deg=0.0):
    """
    Alignement rigide d'un maillage sur un raster.

    Étapes
    ------
    1) Rotation dans le plan XY autour du centre du maillage (optionnelle)
    2) Translation XY pour aligner le centre bbox maillage sur le centre bbox raster

    Paramètres
    ----------
    pts : np.ndarray
        Points du maillage (N,3) ou (N,2).
    geo_transforme : tuple
        Geotransform GDAL du raster.
    forme_raster : tuple[int, int]
        Forme (nb_lignes, nb_colonnes) du raster.
    angle_deg : float
        Angle de rotation à appliquer avant la translation.
        Par défaut 0.0 (pas de rotation).

    Retour
    ------
    tuple[np.ndarray, tuple[float, float, float]]
        - pts_alignes : copie des points alignés
        - (angle_deg, tx, ty) : paramètres appliqués

    Notes
    -----
    Cet alignement est simple et rapide.
    Il ne corrige pas une différence d'échelle ou une rotation inconnue.
    """
    pts = np.asarray(pts)
    if pts.ndim != 2 or pts.shape[1] < 2:
        raise ValueError("pts doit être un tableau de forme (N,2) ou (N,3)")

    # Centre du maillage pour la rotation
    centre = pts[:, :2].astype(float).mean(axis=0)

    pts_rot = rotation_xy(pts, angle_deg, centre_xy=(float(centre[0]), float(centre[1])))
    pts_ok, (tx, ty) = translation_maillage(pts_rot, geo_transforme, forme_raster)

    return pts_ok, (float(angle_deg), float(tx), float(ty))

