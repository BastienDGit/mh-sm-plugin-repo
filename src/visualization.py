# -*- coding: utf-8 -*-
"""
src/visualization.py

Module de visualisation pour l'analyse et le debug.

Rôle du module
--------------
Ce module regroupe des fonctions de visualisation génériques utilisées
pendant le développement et la validation scientifique du projet MH vers SM.

Il permet :
- d'afficher des rasters 2D (MH, MH reconstruit, cartes d'erreur)
- d'afficher des maillages triangulés 3D
- de visualiser des champs scalaires associés aux triangles

Ce module n'est pas utilisé directement par le plugin QGIS.
La visualisation  du MED dans le plugin est déjà par dans  :
    visu_pyvista.py

Public visé
-----------
- développeurs
- personnes en charge de la reprise, de la validation ou de l'amélioration du code
- analyse de cohérence et débogage des résultats

Remarque importante
-------------------
Les fonctions de ce module n'écrivent aucun fichier et ne modifient aucune donnée.
Elles servent uniquement à l'inspection visuelle.
"""

import numpy as np
import matplotlib.pyplot as plt
import pyvista as pv


def affiche_raster(raster, nodata=None, titre="Raster"):
    """
    Affiche un raster 2D à l'aide de Matplotlib.

    Paramètres
    ----------
    raster : np.ndarray
        Tableau 2D représentant un raster.
    nodata : float ou None
        Valeur nodata à ignorer lors de l'affichage.
        Si None, aucune valeur n'est filtrée.
    titre : str
        Titre de la figure.

    Retour
    ------
    None

    Remarque
    --------
    Les valeurs nodata sont converties en NaN pour ne pas influencer
    l'échelle de couleurs.
    """
    data = raster.astype(float).copy()

    if nodata is not None:
        data[data == nodata] = np.nan

    plt.figure(figsize=(6, 5))
    image = plt.imshow(data, origin="upper")
    plt.colorbar(image, label="Valeur")
    plt.title(titre)
    plt.tight_layout()
    plt.show()


def affiche_mesh(points, triangles, titre="Maillage 3D", afficher_bords=True):
    """
    Affiche un maillage triangulé 3D avec PyVista.

    Paramètres
    ----------
    points : np.ndarray
        Tableau de forme (N, 3) contenant les coordonnées XYZ des sommets.
    triangles : np.ndarray
        Tableau de forme (M, 3) contenant les indices des triangles.
    titre : str
        Titre de la fenêtre PyVista.
    afficher_bords : bool
        Si True, affiche les arêtes des triangles.

    Retour
    ------
    None

    Remarque
    --------
    Cette fonction est destinée au contrôle visuel du maillage uniquement.
    """
    if triangles is None or len(triangles) == 0:
        raise ValueError("Aucun triangle à afficher")

    nombre_triangles = triangles.shape[0]

    faces = np.hstack([
        np.full((nombre_triangles, 1), 3, dtype=np.int64),
        triangles.astype(np.int64)
    ]).ravel()

    mesh = pv.PolyData(points, faces)

    plotter = pv.Plotter()
    plotter.add_mesh(mesh, show_edges=afficher_bords)
    plotter.add_axes()
    plotter.show_grid()
    plotter.add_title(titre)
    plotter.show()


def affiche_mesh_champ(
    points,
    triangles,
    champ,
    nom_champ="champ",
    titre="Maillage avec champ",
    afficher_bords=True
):
    """
    Affiche un maillage triangulé 3D coloré par un champ scalaire.

    Paramètres
    ----------
    points : np.ndarray
        Tableau (N, 3) des coordonnées XYZ.
    triangles : np.ndarray
        Tableau (M, 3) des indices de triangles.
    champ : array_like
        Tableau (M,) contenant une valeur par triangle.
    nom_champ : str
        Nom du champ affiché dans PyVista.
    titre : str
        Titre de la fenêtre PyVista.
    afficher_bords : bool
        Si True, affiche les arêtes des triangles.

    Retour
    ------
    None

    Remarque
    --------
    Le champ est associé aux cellules (triangles) et non aux sommets.
    """
    if triangles is None or len(triangles) == 0:
        raise ValueError("Aucun triangle à afficher")

    champ = np.asarray(champ)
    if champ.shape[0] != triangles.shape[0]:
        raise ValueError("La taille du champ doit correspondre au nombre de triangles")

    nombre_triangles = triangles.shape[0]

    faces = np.hstack([
        np.full((nombre_triangles, 1), 3, dtype=np.int64),
        triangles.astype(np.int64)
    ]).ravel()

    mesh = pv.PolyData(points, faces)

    mesh.cell_data[nom_champ] = champ

    plotter = pv.Plotter()
    plotter.add_mesh(mesh, scalars=nom_champ, show_edges=afficher_bords)
    plotter.add_axes()
    plotter.show_grid()
    plotter.add_title(titre)
    plotter.show()

