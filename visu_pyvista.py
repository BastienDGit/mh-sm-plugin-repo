# -*- coding: utf-8 -*-
"""
visu_pyvista.py

Ce module propose une visualisation 3D du maillage MED avec PyVista.

But
---
Afficher un sous-ensemble du maillage afin d'avoir un contrôle visuel rapide :
- suppression d'une bordure intérieure (filtre dans le plan XY)
- suppression des triangles situés trop haut (filtre sur la coordonnée Z)

Ce fichier n'intervient pas dans les calculs de projection MH <-> SM.
Il sert uniquement à l'inspection visuelle pendant le développement.
Peut etre qu'en fonction du fichier.med il faudra modifier percentile_z=98 en input de la fonction visualiser car j'avais fais des tests à taton pour avoir le maillage filtré.

Dépendances
----------
- numpy
- pyvista
- fonctions de lecture et de filtrage du projet
"""

import os
import numpy as np
import pyvista as pv

from .src.reader import lit_med_champs
from .src.preprocessing import filtre_interieur, filtre_z


def visualiser_med_pyvista(chemin_med, marge_interieure=0.10, percentile_z=98):
    """
    Ouvre une fenêtre PyVista pour visualiser le maillage MED après filtrage.

    Le filtrage appliqué est le suivant :
    1) filtre intérieur dans le plan XY afin d'enlever une bande au bord du maillage
    2) filtre sur Z afin de supprimer les triangles dont le barycentre est trop élevé

    Paramètres
    ----------
    chemin_med : str
        Chemin du fichier MED à visualiser.
    marge_interieure : float
        Marge relative utilisée par le filtre intérieur. Une valeur plus grande
        retire davantage de triangles sur les bords.
    percentile_z : float
        Percentile utilisé pour le seuil en Z. Par exemple 98 signifie que l'on
        coupe au niveau du 98e percentile des barycentres Z.

    Retour
    ------
    None

    Comportement
    -----------
    Cette fonction affiche une fenêtre interactive PyVista. Elle ne modifie
    aucun fichier et ne renvoie pas de résultat.
    """
    if not isinstance(chemin_med, str) or not chemin_med.strip():
        raise ValueError("Le chemin du fichier MED est vide")

    if not os.path.isfile(chemin_med):
        raise FileNotFoundError("Le fichier MED est introuvable")

    print("Lecture du fichier MED", chemin_med)

    points, triangles, champs_tri, champs_pts = lit_med_champs(chemin_med)

    if triangles is None or len(triangles) == 0:
        print("Aucun triangle trouvé dans le fichier MED")
        return

    # Filtre intérieur dans le plan XY
    tri_interieur, _ = filtre_interieur(
        points,
        triangles,
        marge=marge_interieure,
        mask=True
    )

    if tri_interieur is None or len(tri_interieur) == 0:
        print("Aucun triangle après filtre intérieur")
        return

    # Filtre Z sur la base des barycentres des triangles
    bary = points[tri_interieur].mean(axis=1)
    z_seuil = float(np.percentile(bary[:, 2], percentile_z))

    tri_filtre, _ = filtre_z(
        points,
        tri_interieur,
        z_max=z_seuil,
        mask=True
    )

    print("Nombre de triangles initial", int(triangles.shape[0]))
    print("Nombre de triangles après filtre intérieur", int(tri_interieur.shape[0]))
    print("Nombre de triangles après filtre Z", int(tri_filtre.shape[0]))

    if tri_filtre is None or len(tri_filtre) == 0:
        print("Aucun triangle à afficher après filtrage")
        return

    # PyVista attend un tableau "faces" au format :
    # [3, i0, i1, i2, 3, j0, j1, j2, ...]
    faces = np.hstack([
        np.full((len(tri_filtre), 1), 3, dtype=np.int64),
        tri_filtre.astype(np.int64)
    ]).ravel()

    maillage = pv.PolyData(points, faces)

    afficheur = pv.Plotter(title="Visualisation MED")
    afficheur.add_mesh(maillage, show_edges=True)
    afficheur.add_axes()
    afficheur.show_grid()
    afficheur.show()

