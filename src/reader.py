# src/reader.py

"""
Lecture des données d entrée pour le plugin MH vers SM.

Ce module fournit des fonctions utilitaires pour :
- lire des rasters via GDAL
- lire des fichiers MED via meshio
- extraire points triangles et champs associés
- afficher des résumés simples pour vérification

Ce module ne contient aucune logique de conversion MH vers SM.
"""

import os
import numpy as np
import meshio
from osgeo import gdal


def lit_raster(chemin):
    """
    Lit un raster avec GDAL.

    Paramètres
    ----------
    chemin : str
        Chemin du raster.

    Retour
    ------
    arr : np.ndarray
        Tableau raster 2D.
    gt : tuple
        Geotransform GDAL.
    nodata : float ou None
        Valeur nodata du raster.
    """
    ds = gdal.Open(chemin)
    if ds is None:
        raise FileNotFoundError("Raster introuvable " + str(chemin))

    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray()
    gt = ds.GetGeoTransform()
    nodata = band.GetNoDataValue()

    return arr, gt, nodata


def resume_raster(chemin):
    """
    Affiche un résumé simple d un raster.

    Paramètres
    ----------
    chemin : str
        Chemin du raster.
    """
    arr, gt, nodata = lit_raster(chemin)
    nrows, ncols = arr.shape

    print("Raster")
    print("chemin", chemin)
    print("taille lignes", nrows)
    print("taille colonnes", ncols)
    print("nodata", nodata)
    print("x origine", gt[0])
    print("y origine", gt[3])
    print("pas x", gt[1])
    print("pas y", gt[5])


def lit_med(chemin):
    """
    Lit un fichier MED et retourne uniquement la géométrie.

    Paramètres
    ----------
    chemin : str
        Chemin du fichier MED.

    Retour
    ------
    points : np.ndarray
        Coordonnées des points (N,3).
    triangles : np.ndarray
        Indices des triangles (M,3).
    """
    ext = os.path.splitext(chemin)[1].lower()
    if ext != ".med":
        raise ValueError("Extension attendue med")

    mesh = meshio.read(chemin)
    points = mesh.points

    if "triangle" in mesh.cells_dict:
        triangles = mesh.cells_dict["triangle"]
    else:
        cell_type = list(mesh.cells_dict.keys())[0]
        triangles = mesh.cells_dict[cell_type]

    return points, triangles


def lit_med_champs(chemin):
    """
    Lit un fichier MED et récupère la géométrie et les champs.

    Paramètres
    ----------
    chemin : str
        Chemin du fichier MED.

    Retour
    ------
    points : np.ndarray
        Coordonnées des points (N,3).
    triangles : np.ndarray
        Indices des triangles (M,3).
    champs_tri : dict
        Champs par triangle.
    champs_pts : dict
        Champs par point.
    """
    ext = os.path.splitext(chemin)[1].lower()
    if ext != ".med":
        raise ValueError("Extension attendue med")

    mesh = meshio.read(chemin)
    points = mesh.points

    triangles = None
    idx_tri = None
    for i, bloc in enumerate(mesh.cells):
        if bloc.type == "triangle":
            triangles = bloc.data
            idx_tri = i
            break

    if triangles is None:
        if "triangle" in mesh.cells_dict:
            triangles = mesh.cells_dict["triangle"]
        else:
            cell_type = list(mesh.cells_dict.keys())[0]
            triangles = mesh.cells_dict[cell_type]

    champs_tri = {}
    if hasattr(mesh, "cell_data") and idx_tri is not None:
        for nom, liste in mesh.cell_data.items():
            if idx_tri < len(liste):
                vals = np.asarray(liste[idx_tri])
                if len(vals) == len(triangles):
                    champs_tri[nom] = vals

    champs_pts = {}
    if hasattr(mesh, "point_data"):
        for nom, vals in mesh.point_data.items():
            champs_pts[nom] = np.asarray(vals)

    return points, triangles, champs_tri, champs_pts


def resume_med(chemin):
    """
    Affiche un résumé simple d un fichier MED.

    Paramètres
    ----------
    chemin : str
        Chemin du fichier MED.
    """
    points, triangles, champs_tri, champs_pts = lit_med_champs(chemin)

    print("MED")
    print("chemin", chemin)
    print("nombre de points", points.shape[0])
    print("nombre de triangles", triangles.shape[0])

    if champs_tri:
        print("champs triangles")
        for nom, vals in champs_tri.items():
            print("nom", nom, "taille", len(vals))
    else:
        print("aucun champ triangle")

    if champs_pts:
        print("champs points")
        for nom, vals in champs_pts.items():
            print("nom", nom, "taille", len(vals))
    else:
        print("aucun champ point")


if __name__ == "__main__":
    """
    Test manuel simple.

    Usage
    -----
    python -m src.reader chemin_du_fichier
    """
    import sys

    if len(sys.argv) < 2:
        print("Usage python -m src.reader chemin_fichier")
        raise SystemExit(0)

    chemin = sys.argv[1]
    ext = os.path.splitext(chemin)[1].lower()

    if ext in [".asc", ".tif", ".tiff"]:
        resume_raster(chemin)
    elif ext == ".med":
        resume_med(chemin)
    else:
        print("Extension non geree")

