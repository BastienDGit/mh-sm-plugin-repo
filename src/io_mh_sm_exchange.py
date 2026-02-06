# -*- coding: utf-8 -*-
"""
src/io_mh_sm_exchange.py

Ce module regroupe les fonctions d'échange entre :
- MH : raster ASCII au format ESRI ASCII grid (.txt ou .asc)
- SM : fichier .val contenant une valeur par triangle, rangée par facette
- scene_triangle.cir : définition des triangles par facette et ordre officiel

Conventions utilisées dans ce projet
-----------------------------------
- La valeur NODATA est fixée à 9999 en entrée et en sortie.
- En interne, les zones NODATA sont converties en NaN pour faciliter les calculs.
- L'ordre des triangles est celui du fichier scene_triangle.cir.
  Il doit être respecté à la lecture et à l'écriture des fichiers .val.

Méthodes de projection
----------------------
- MH vers SM :
  on associe des pixels aux triangles (intersection géométrique) puis on calcule
  une moyenne de pixels pour obtenir une valeur par triangle.

- SM vers MH :
  on associe des triangles aux pixels (intersection géométrique) puis on calcule
  une moyenne de triangles pour obtenir une valeur par pixel.

La correspondance géométrique pixel triangle est obtenue via mapping_surface
dans le module mapping.
"""

import re
from collections import defaultdict

import numpy as np

from .mapping import mapping_surface


NODATA_MH = 9999.0


def _valeurs_ascii(lignes_donnees):
    """
    Transforme une liste de lignes ASCII contenant des nombres en liste de float.

    Paramètres
    ----------
    lignes_donnees : list[str]
        Lignes de valeurs issues d'un fichier ASCII grid.

    Retour
    ------
    list[float]
        Valeurs converties en float, dans l'ordre de lecture.
    """
    vals = []
    for lig in lignes_donnees:
        vals.extend([float(x) for x in lig.split()])
    return vals


def lire_mh_ascii(chemin):
    """
    Lit un raster MH au format ESRI ASCII grid (.txt ou .asc).

    Paramètres
    ----------
    chemin : str
        Chemin du fichier raster à lire.

    Retour
    ------
    tuple[np.ndarray, tuple, float]
        ras : np.ndarray float, forme (nb_lignes, nb_colonnes)
            Tableau du raster. Les pixels NODATA sont remplacés par NaN.
        gt : tuple[float, float, float, float, float, float]
            Geotransform compatible GDAL :
            (xllcorner, cellsize, 0, y_max, 0, -cellsize)
        nd : float
            Valeur NODATA de référence, toujours égale à 9999.0.

    Hypothèses
    ----------
    Le raster est écrit avec un en-tête ASCII grid standard contenant :
    ncols, nrows, xllcorner, yllcorner, cellsize, NODATA_value.

    Remarque
    --------
    Même si le fichier contient un autre code NODATA, il sera converti en NaN.
    La convention interne du projet reste NODATA_MH = 9999.
    """
    entete = {}
    lignes_donnees = []

    with open(chemin, "r", errors="ignore") as f:
        for lig in f:
            s = lig.strip()
            if not s:
                continue

            bas = s.lower()
            if len(entete) < 6 and (
                bas.startswith("ncols") or bas.startswith("nrows") or
                bas.startswith("xllcorner") or bas.startswith("yllcorner") or
                bas.startswith("cellsize") or bas.startswith("nodata_value")
            ):
                k, v = s.split()[:2]
                entete[k.lower()] = float(v)
            else:
                lignes_donnees.append(s)

    nb_colonnes = int(entete["ncols"])
    nb_lignes = int(entete["nrows"])
    xll = float(entete["xllcorner"])
    yll = float(entete["yllcorner"])
    pas = float(entete["cellsize"])

    nodata_fichier = float(entete.get("nodata_value", NODATA_MH))
    nodata = float(NODATA_MH)

    y_max = yll + nb_lignes * pas
    gt = (xll, pas, 0.0, y_max, 0.0, -pas)

    vals = _valeurs_ascii(lignes_donnees)
    ras = np.array(vals, dtype=float).reshape((nb_lignes, nb_colonnes))

    ras[ras == nodata_fichier] = np.nan
    ras[ras == nodata] = np.nan

    return ras, gt, nodata


def lire_scene_triangle_cir(chemin):
    """
    Lit un fichier scene_triangle.cir et reconstruit l'ordre des triangles.

    Paramètres
    ----------
    chemin : str
        Chemin du fichier scene_triangle.cir.

    Retour
    ------
    tuple[list[int], np.ndarray, np.ndarray]
        tailles_facettes : list[int]
            Nombre de triangles par facette, dans l'ordre des facettes.
        pts : np.ndarray float, forme (N, 3)
            Coordonnées des points. Les sommets sont volontairement dupliqués
            pour simplifier le parsing et assurer la robustesse.
        tri : np.ndarray int, forme (M, 3)
            Triangles. Chaque ligne contient les indices (i0, i1, i2) dans pts.

    Hypothèses
    ----------
    - Chaque facette commence par une ligne "fX N" indiquant N triangles.
    - Les triangles sont décrits par blocs commençant par "cY".
    - Un bloc contient un entier (souvent 4) suivi de N points.
      Les trois premiers points forment un triangle.
      Le quatrième point, s'il existe, sert généralement à fermer le contour.

    Remarque
    --------
    L'ordre de lecture correspond à l'ordre officiel à respecter pour les fichiers .val.
    """
    tailles_facettes = []
    pts = []
    tri = []

    dans_facette = False
    nb_attendu = None
    nb_lu = 0

    with open(chemin, "r", errors="ignore") as f:
        lignes = f.readlines()

    i = 0
    while i < len(lignes):
        s = lignes[i].strip()
        i += 1

        if not s:
            continue

        m = re.match(r"^f(\d+)\s+(\d+)", s)
        if m:
            nb_attendu = int(m.group(2))
            tailles_facettes.append(nb_attendu)
            dans_facette = True
            nb_lu = 0

            if i < len(lignes):
                peek = lignes[i].strip()
                if re.match(r"^-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s+-?\d+(\.\d+)?$", peek):
                    i += 1
            continue

        if dans_facette and s.startswith("c"):
            if i >= len(lignes):
                break

            try:
                nb_pts = int(lignes[i].strip())
            except ValueError:
                continue
            i += 1

            coords = []
            for _ in range(nb_pts):
                if i >= len(lignes):
                    break
                xyz = lignes[i].strip().split()
                i += 1
                if len(xyz) >= 3:
                    coords.append([float(xyz[0]), float(xyz[1]), float(xyz[2])])

            if len(coords) >= 3:
                i0 = len(pts)
                pts.append(coords[0])
                i1 = len(pts)
                pts.append(coords[1])
                i2 = len(pts)
                pts.append(coords[2])

                tri.append([i0, i1, i2])
                nb_lu += 1

            if nb_attendu is not None and nb_lu >= nb_attendu:
                dans_facette = False
                nb_attendu = None

    return np.asarray(tailles_facettes, dtype=int).tolist(), np.asarray(pts, dtype=float), np.asarray(tri, dtype=int)


def _bbox_xy(pts):
    """
    Calcule la boite englobante XY d'un tableau de points.

    Paramètres
    ----------
    pts : np.ndarray
        Tableau (N, 3) ou (N, 2).

    Retour
    ------
    tuple[float, float, float, float]
        (x_min, y_min, x_max, y_max)
    """
    x = pts[:, 0].astype(float)
    y = pts[:, 1].astype(float)
    return float(x.min()), float(y.min()), float(x.max()), float(y.max())


def aligner_par_bbox(pts, gt, forme_ras):
    """
    Applique une translation XY pour aligner le centre du maillage sur le centre du raster.

    Paramètres
    ----------
    pts : np.ndarray
        Points du maillage (N, 3).
    gt : tuple
        Geotransform du raster.
    forme_ras : tuple[int, int]
        Forme du raster (nb_lignes, nb_colonnes).

    Retour
    ------
    tuple[np.ndarray, tuple[float, float]]
        pts2 : points translatés (copie)
        (tx, ty) : translation appliquée

    Remarque
    --------
    Cette méthode est simple et rapide, mais elle ne corrige ni rotation ni échelle.
    """
    nb_lignes, nb_colonnes = forme_ras
    x0, pas_x, _, y0, _, pas_y = gt

    x_min = float(x0)
    x_max = float(x0 + nb_colonnes * pas_x)
    y_max = float(y0)
    y_min = float(y0 + nb_lignes * pas_y)

    cx_r = 0.5 * (x_min + x_max)
    cy_r = 0.5 * (y_min + y_max)

    x_min_m, y_min_m, x_max_m, y_max_m = _bbox_xy(pts)
    cx_m = 0.5 * (x_min_m + x_max_m)
    cy_m = 0.5 * (y_min_m + y_max_m)

    tx = cx_r - cx_m
    ty = cy_r - cy_m

    pts2 = np.array(pts, dtype=float, copy=True)
    pts2[:, 0] += tx
    pts2[:, 1] += ty

    return pts2, (float(tx), float(ty))


def inverser_mapping(map_px, nb_triangles):
    """
    Convertit un mapping pixel vers triangles en mapping triangle vers pixels.

    Paramètres
    ----------
    map_px : dict[tuple[int, int], list[tuple[int, float]]]
        Dictionnaire renvoyé par mapping_surface :
        clé : (ligne, colonne)
        valeur : liste de (id_triangle, aire_intersection)
    nb_triangles : int
        Nombre total de triangles.

    Retour
    ------
    dict[int, list[tuple[int, int, float]]]
        Dictionnaire :
        clé : id_triangle
        valeur : liste de (ligne, colonne, aire_intersection)

    Remarque
    --------
    Ce dictionnaire correspond à la notion "Triangles_pixels" discutée en réunion.
    """
    tri_px = defaultdict(list)

    for (lig, col), lst in map_px.items():
        for id_tri, aire in lst:
            tri_px[int(id_tri)].append((int(lig), int(col), float(aire)))

    for id_tri in range(int(nb_triangles)):
        tri_px[id_tri] = tri_px.get(id_tri, [])

    return tri_px


def moyenne_pixels_par_triangle(ras, tri_px, pondere=False, rempl=np.nan):
    """
    Calcule une valeur par triangle à partir des pixels qui lui sont associés.

    Paramètres
    ----------
    ras : np.ndarray
        Raster MH (NaN sur les zones nodata).
    tri_px : dict[int, list[tuple[int, int, float]]]
        Mapping triangle vers pixels, obtenu via inverser_mapping.
    pondere : bool
        Si True, la moyenne est pondérée par l'aire d'intersection pixel triangle.
        Si False, moyenne simple.
    rempl : float
        Valeur utilisée si un triangle ne reçoit aucune valeur.

    Retour
    ------
    np.ndarray
        Tableau (nb_triangles,) des valeurs par triangle.
    """
    nb_tri = len(tri_px)
    val_tri = np.full((nb_tri,), float(rempl), dtype=float)

    for id_tri, pixels in tri_px.items():
        if not pixels:
            continue

        vals = []
        poids = []

        for lig, col, aire in pixels:
            v = ras[lig, col]
            if not np.isfinite(v):
                continue
            vals.append(float(v))
            poids.append(float(aire))

        if not vals:
            continue

        if pondere:
            w = np.asarray(poids, dtype=float)
            if float(np.sum(w)) > 0.0:
                val_tri[int(id_tri)] = float(np.sum(np.asarray(vals, dtype=float) * w) / np.sum(w))
        else:
            val_tri[int(id_tri)] = float(np.mean(np.asarray(vals, dtype=float)))

    return val_tri


def ecrire_val(chemin_sortie, tailles_facettes, val_tri):
    """
    Écrit un fichier .val au format SM.

    Paramètres
    ----------
    chemin_sortie : str
        Chemin du fichier .val à écrire.
    tailles_facettes : list[int]
        Nombre de triangles par facette (ordre du .cir).
    val_tri : np.ndarray
        Valeurs par triangle (ordre du .cir). La taille attendue est la somme
        des tailles de facettes.

    Retour
    ------
    None

    Remarque
    --------
    Par choix simple, les triangles sans valeur (NaN) sont écrits à 0.00.
    Ce choix peut être modifié si le commanditaire préfère un autre code.
    """
    nb_facettes = int(len(tailles_facettes))

    fini = val_tri[np.isfinite(val_tri)]
    vmin = float(np.min(fini)) if fini.size else 0.0
    vmax = float(np.max(fini)) if fini.size else 0.0

    with open(chemin_sortie, "w", encoding="utf-8") as f:
        f.write(f"{nb_facettes} {nb_facettes}\t {vmin:.2f} {vmax:.2f}\n")

        k = 0
        for i, nb_tri in enumerate(tailles_facettes, start=1):
            f.write(f"f{i} {int(nb_tri)}\n")
            for _ in range(int(nb_tri)):
                v = float(val_tri[k])
                if not np.isfinite(v):
                    v = 0.0
                f.write(f"\t{v:.2f}\n")
                k += 1


def mh_vers_sm_val(mh_txt, cir, val_sortie, pondere=False):
    """
    Convertit un raster MH (.txt ou .asc) en fichier SM (.val).

    Étapes
    ------
    1) Lecture du raster MH et conversion NODATA vers NaN
    2) Lecture du scene_triangle.cir pour obtenir l'ordre des triangles
    3) Alignement simple du maillage sur la grille du raster (translation bbox)
    4) Calcul du mapping pixel triangle (intersection géométrique)
    5) Agrégation des pixels vers une valeur par triangle
    6) Écriture du .val

    Paramètres
    ----------
    mh_txt : str
        Chemin du raster MH en entrée.
    cir : str
        Chemin du fichier scene_triangle.cir.
    val_sortie : str
        Chemin du fichier .val de sortie.
    pondere : bool
        Si True, moyenne pondérée par aire d'intersection.
        Si False, moyenne simple.

    Retour
    ------
    dict
        Dictionnaire contenant les informations utiles :
        val, nf, ntri, tx_ty, nodata
    """
    ras, gt, nodata = lire_mh_ascii(mh_txt)
    tailles, pts, tri = lire_scene_triangle_cir(cir)

    pts2, (tx, ty) = aligner_par_bbox(pts, gt, ras.shape)

    map_px = mapping_surface(pts2, tri, gt, ras.shape)
    tri_px = inverser_mapping(map_px, len(tri))

    val_tri = moyenne_pixels_par_triangle(ras, tri_px, pondere=pondere, rempl=np.nan)

    ecrire_val(val_sortie, tailles, val_tri)

    return {
        "val": val_sortie,
        "nf": int(len(tailles)),
        "ntri": int(len(tri)),
        "tx_ty": (float(tx), float(ty)),
        "nodata": float(nodata),
    }


def lire_val(chemin_val):
    """
    Lit un fichier .val et renvoie les valeurs dans l'ordre des triangles.

    Paramètres
    ----------
    chemin_val : str
        Chemin du fichier .val à lire.

    Retour
    ------
    np.ndarray
        Tableau (nb_triangles,) contenant les valeurs par triangle.

    Remarque
    --------
    Le fichier .val contient des blocs par facette. La lecture conserve l'ordre.
    """
    valeurs = []

    with open(chemin_val, "r", errors="ignore") as f:
        lignes = [l.strip() for l in f if l.strip()]

    if not lignes:
        return np.asarray([], dtype=float)

    i = 1
    while i < len(lignes):
        s = lignes[i]
        if s.startswith("f"):
            nb = int(s.split()[1])
            i += 1
            for _ in range(nb):
                v = float(lignes[i].replace("\t", " ").split()[0])
                valeurs.append(v)
                i += 1
        else:
            i += 1

    return np.asarray(valeurs, dtype=float)


def sm_vers_mh_raster(mh_txt_ref, cir, val_path, pondere=False):
    """
    Reconstruit un raster MH à partir d'un fichier .val.

    Étapes
    ------
    1) Lecture du raster MH de référence pour récupérer la grille (shape et gt)
    2) Lecture du scene_triangle.cir pour récupérer les triangles dans le même ordre
    3) Alignement simple du maillage sur la grille (translation bbox)
    4) Calcul du mapping pixel triangle (intersection géométrique)
    5) Lecture du .val pour obtenir une valeur par triangle
    6) Agrégation des triangles vers une valeur par pixel

    Paramètres
    ----------
    mh_txt_ref : str
        Chemin du raster MH de référence (utilisé uniquement pour la grille).
    cir : str
        Chemin du fichier scene_triangle.cir.
    val_path : str
        Chemin du fichier .val à projeter.
    pondere : bool
        Si True, moyenne pondérée par aire d'intersection.
        Si False, moyenne simple.

    Retour
    ------
    tuple[np.ndarray, tuple, float]
        ras_rec : np.ndarray float contenant NaN sur les pixels non couverts
        gt : geotransform du raster
        nd : NODATA de référence (9999)
    """
    ras_ref, gt, nodata = lire_mh_ascii(mh_txt_ref)
    _, pts, tri = lire_scene_triangle_cir(cir)

    pts2, _ = aligner_par_bbox(pts, gt, ras_ref.shape)
    map_px = mapping_surface(pts2, tri, gt, ras_ref.shape)

    val_tri = lire_val(val_path)

    nb_lignes, nb_colonnes = ras_ref.shape
    ras_rec = np.full((nb_lignes, nb_colonnes), np.nan, dtype=float)

    for (lig, col), lst in map_px.items():
        if not lst:
            continue

        if not pondere:
            vals = [float(val_tri[int(id_tri)]) for (id_tri, aire) in lst]
            if vals:
                ras_rec[lig, col] = float(np.mean(vals))
        else:
            num = 0.0
            den = 0.0
            for id_tri, aire in lst:
                a = float(aire)
                if a <= 0.0:
                    continue
                vt = float(val_tri[int(id_tri)])
                if not np.isfinite(vt):
                    continue
                num += vt * a
                den += a
            if den > 0.0:
                ras_rec[lig, col] = num / den

    return ras_rec, gt, float(nodata)


def ecrire_mh_ascii(chemin_sortie, ras, gt, nodata=NODATA_MH):
    """
    Écrit un raster ESRI ASCII grid (.asc ou .txt) avec NODATA fixé à 9999.

    Paramètres
    ----------
    chemin_sortie : str
        Chemin du fichier à écrire.
    ras : np.ndarray
        Raster à écrire. Les zones à ignorer doivent être à NaN.
    gt : tuple
        Geotransform : (xllcorner, cellsize, 0, y_max, 0, -cellsize)
    nodata : float
        Valeur à écrire dans l'en-tête et dans la grille pour les pixels manquants.

    Retour
    ------
    None

    Remarque
    --------
    Le format ASCII grid attend généralement les valeurs de la première ligne
    au nord. Le tableau numpy est écrit ligne par ligne tel quel.
    """
    nb_lignes, nb_colonnes = ras.shape

    xll = float(gt[0])
    pas = float(abs(gt[1]))
    y_max = float(gt[3])
    yll = y_max - nb_lignes * pas

    with open(chemin_sortie, "w", encoding="utf-8") as f:
        f.write(f"ncols         {nb_colonnes}\n")
        f.write(f"nrows         {nb_lignes}\n")
        f.write(f"xllcorner     {xll}\n")
        f.write(f"yllcorner     {yll}\n")
        f.write(f"cellsize      {pas}\n")
        f.write(f"NODATA_value  {float(nodata)}\n")

        data = ras.astype(float, copy=True)
        data[~np.isfinite(data)] = float(nodata)

        for lig in range(nb_lignes):
            f.write(" ".join(f"{v:.6g}" for v in data[lig, :]) + "\n")


def mh_txt_to_sm_val(mh_txt_path, cir_path, out_val_path, weighted_by_area=False):
    """
    Alias de compatibilité.

    Paramètres
    ----------
    mh_txt_path : str
        Chemin du raster MH.
    cir_path : str
        Chemin du scene_triangle.cir.
    out_val_path : str
        Chemin du .val à écrire.
    weighted_by_area : bool
        Si True, utilise la moyenne pondérée par aire.

    Retour
    ------
    dict
        Même retour que mh_vers_sm_val.
    """
    return mh_vers_sm_val(
        mh_txt=mh_txt_path,
        cir=cir_path,
        val_sortie=out_val_path,
        pondere=weighted_by_area,
    )

