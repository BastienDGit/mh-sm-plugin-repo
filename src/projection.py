# src/projection.py

"""
Projection de valeurs entre un raster MH et des triangles de maillage.

Ce module regroupe les méthodes pour projeter MH vers triangles.

Contexte

- Le raster MH est une grille régulière (tableau 2D).
- Le maillage est une liste de triangles définis par leurs sommets.
- La projection consiste à estimer une valeur pour chaque triangle à partir
  des valeurs du raster.

Méthodes disponibles
--------------------
1) mh_vers_triangles
   Projection la plus simple : chaque triangle récupère la valeur d un seul pixel.
   On utilise un tableau tri_pixel qui donne, pour chaque triangle, la ligne et
   la colonne du pixel associé.

2) mh_vers_tri_bilineaire
   Projection par interpolation bilinéaire : on échantillonne le raster à des
   coordonnées monde (x, y) associées aux triangles (souvent le barycentre).

3) mh_vers_tri_multisample
   Projection par multi échantillonnage :
   - on prend plusieurs points dans le triangle
   - on échantillonne le raster en bilinéaire
   - on fait la moyenne des valeurs valides
   
   On pourra par la suite développer d'autres méthodes de projection pour améliorer la correspondance pixel triangle sur des maillage plus fins. 

Conventions
-----------
- Si nodata est fourni, les valeurs égales à nodata sont ignorées.
- Les NaN sont ignorés.
- Si aucune valeur valide ne peut être obtenue, on retourne fill.
"""

import numpy as np


def mh_vers_triangles(raster, tri_pixel, nodata=None, fill=np.nan):
    """
    Projection MH vers triangles avec une association directe pixel triangle.

    Principe
    --------
    On suppose qu un pré traitement a fourni un tableau tri_pixel de taille
    (nb_triangles, 2), où chaque ligne contient (row, col) du pixel associé
    au triangle de même indice.

    Paramètres
    ----------
    raster : np.ndarray
        Raster 2D.
    tri_pixel : np.ndarray
        Tableau (nb_triangles, 2) contenant pour chaque triangle :
        - tri_pixel[i, 0] : ligne du pixel
        - tri_pixel[i, 1] : colonne du pixel
        Une valeur négative signifie triangle non mappé.
    nodata : float ou None
        Valeur nodata à ignorer si elle est présente dans le raster.
    fill : float
        Valeur renvoyée si un triangle ne peut pas recevoir de valeur.

    Retour
    ------
    np.ndarray
        Tableau 1D (nb_triangles,) contenant une valeur par triangle.
    """
    nb_triangles = tri_pixel.shape[0]
    nb_lignes, nb_colonnes = raster.shape

    valeurs_triangles = np.full(nb_triangles, fill, dtype=float)

    for id_triangle, (lig, col) in enumerate(tri_pixel):
        if lig < 0 or col < 0:
            continue

        if lig >= nb_lignes or col >= nb_colonnes:
            continue

        val = raster[lig, col]

        if nodata is not None and val == nodata:
            continue
        if np.isnan(val):
            continue

        valeurs_triangles[id_triangle] = float(val)

    return valeurs_triangles


def mh_vers_tri_bilineaire(raster, xy_tri, gt, nodata=None, fill=np.nan):
    """
    Projection MH vers triangles par interpolation bilinéaire.

    Principe
    --------
    On fournit, pour chaque triangle, une coordonnée monde (x, y)
    (souvent le barycentre du triangle).
    Le raster est ensuite échantillonné à cette position par interpolation
    bilinéaire.

    Paramètres
    ----------
    raster : np.ndarray
        Raster 2D.
    xy_tri : np.ndarray
        Tableau (nb_triangles, 2) contenant des coordonnées monde (x, y)
        associées à chaque triangle.
    gt : tuple
        Geotransform GDAL (x0, dx, 0, y0, 0, dy) où dy est généralement négatif.
    nodata : float ou None
        Valeur nodata à ignorer.
    fill : float
        Valeur de retour si hors raster ou si des valeurs nodata ou NaN
        empêchent l interpolation.

    Retour
    ------
    np.ndarray
        Tableau 1D (nb_triangles,) contenant une valeur par triangle.
    """
    nb_triangles = xy_tri.shape[0]
    valeurs_triangles = np.full(nb_triangles, fill, dtype=float)

    for id_triangle, (x, y) in enumerate(xy_tri):
        valeurs_triangles[id_triangle] = _echant_bilineaire(
            raster=raster,
            x=x,
            y=y,
            gt=gt,
            nodata=nodata,
            fill=fill
        )

    return valeurs_triangles


def _echant_bilineaire(raster, x, y, gt, nodata=None, fill=np.nan):
    """
    Échantillonne un raster en coordonnées monde (x, y) avec interpolation bilinéaire.

    Détails
    -------
    1) Conversion (x, y) en indices pixel flottants (row_f, col_f) via gt
    2) Récupération des 4 voisins (r0,c0) (r0,c1) (r1,c0) (r1,c1)
    3) Interpolation bilinéaire si les 4 valeurs sont valides

    Paramètres
    ----------
    raster : np.ndarray
        Raster 2D.
    x : float
        Coordonnée monde X.
    y : float
        Coordonnée monde Y.
    gt : tuple
        Geotransform GDAL.
    nodata : float ou None
        Valeur nodata à ignorer.
    fill : float
        Valeur retournée si hors raster ou si interpolation impossible.

    Retour
    ------
    float
        Valeur interpolée ou fill.
    """
    x0, dx, _, y0, _, dy = gt
    nb_lignes, nb_colonnes = raster.shape

    col_f = (x - x0) / dx

    # dy est souvent négatif, donc la division fonctionne tant que dy est non nul
    row_f = (y - y0) / dy

    c0 = int(np.floor(col_f))
    r0 = int(np.floor(row_f))
    c1 = c0 + 1
    r1 = r0 + 1

    if r0 < 0 or c0 < 0 or r1 >= nb_lignes or c1 >= nb_colonnes:
        return fill

    poids_col = col_f - c0
    poids_lig = row_f - r0

    v00 = float(raster[r0, c0])
    v01 = float(raster[r0, c1])
    v10 = float(raster[r1, c0])
    v11 = float(raster[r1, c1])

    vals = np.array([v00, v01, v10, v11], dtype=float)

    if nodata is not None and np.any(vals == float(nodata)):
        return fill
    if np.any(np.isnan(vals)):
        return fill

    val = (
        v00 * (1.0 - poids_col) * (1.0 - poids_lig)
        + v01 * poids_col * (1.0 - poids_lig)
        + v10 * (1.0 - poids_col) * poids_lig
        + v11 * poids_col * poids_lig
    )

    return float(val)


def mh_vers_tri_multisample(raster, points, triangles, gt, nodata=None, fill=np.nan, plan="7pt"):
    """
    Projection MH vers triangles par multi échantillonnage.

    Principe
    --------
    Pour chaque triangle :
    - on choisit plusieurs points internes au triangle (définis en barycentriques)
    - on échantillonne le raster à chacun de ces points en bilinéaire
    - on calcule la moyenne des valeurs valides

    Cette méthode est plus stable qu un simple échantillon sur le barycentre,
    notamment lorsque le raster varie fortement ou lorsque des pixels nodata
    sont présents autour du triangle.

    Paramètres
    ----------
    raster : np.ndarray
        Raster 2D.
    points : np.ndarray
        Tableau (N,3) des sommets du maillage.
    triangles : np.ndarray
        Tableau (M,3) des triangles, indices dans points.
    gt : tuple
        Geotransform GDAL.
    nodata : float ou None
        Valeur nodata à ignorer lors de l échantillonnage bilinéaire.
    fill : float
        Valeur renvoyée si aucun échantillon valide n est disponible.
    plan : str
        Stratégie d échantillonnage :
        - "4pt" : barycentre et 3 points proches des sommets
        - "7pt" : "4pt" plus 3 milieux d arêtes

    Retour
    ------
    np.ndarray
        Tableau 1D (M,) contenant une valeur par triangle.
    """
    nb_triangles = len(triangles)
    valeurs_triangles = np.full(nb_triangles, fill, dtype=float)

    if plan == "4pt":
        poids = [
            (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
            (0.60, 0.20, 0.20),
            (0.20, 0.60, 0.20),
            (0.20, 0.20, 0.60),
        ]
    elif plan == "7pt":
        poids = [
            (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
            (0.60, 0.20, 0.20),
            (0.20, 0.60, 0.20),
            (0.20, 0.20, 0.60),
            (0.50, 0.50, 0.00),
            (0.50, 0.00, 0.50),
            (0.00, 0.50, 0.50),
        ]
    else:
        raise ValueError("Plan non reconnu")

    for id_triangle, tri in enumerate(triangles):
        ia, ib, ic = tri

        a = points[ia, :2]
        b = points[ib, :2]
        c = points[ic, :2]

        echantillons = []
        for wa, wb, wc in poids:
            p = wa * a + wb * b + wc * c
            val = _echant_bilineaire(
                raster=raster,
                x=float(p[0]),
                y=float(p[1]),
                gt=gt,
                nodata=nodata,
                fill=np.nan
            )
            echantillons.append(val)

        echantillons = np.asarray(echantillons, dtype=float)
        valides = echantillons[np.isfinite(echantillons)]

        if valides.size > 0:
            valeurs_triangles[id_triangle] = float(np.mean(valides))

    return valeurs_triangles

