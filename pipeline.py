# -*- coding: utf-8 -*-
"""


Ce module regroupe toutes kes fonctions utilitaires utilisées par le plugin QGIS.

Objectifs:

1) Export MH vers SM
   - Entrées : un raster MH au format ESRI ASCII grid (.txt ou .asc)
              un fichier scene_triangle.cir
   - Sortie  : un fichier .val (format SM)

2) Reconstruction MH depuis SM
   - Entrées : un fichier .val (format SM)
              un raster MH de référence (sert à récupérer la grille)
              un fichier scene_triangle.cir
   - Sortie  : un GeoTIFF (optionnel) ou un raster en mémoire

3) Outils optionnels de contrôle
   - Afficher un raster dans QGIS
   - Afficher un aperçu des triangles MED en couche mémoire
"""

import os

import numpy as np
from osgeo import gdal, osr

from qgis.core import (
    QgsMessageLog,
    Qgis,
    QgsRasterLayer,
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsFields,
    QgsField,
    QgsPointXY,
)
from qgis.PyQt.QtCore import QVariant

from .src.reader import lit_med_champs
from .src.io_mh_sm_exchange import mh_vers_sm_val, sm_vers_mh_raster, NODATA_MH


NODATA_TIF = float(NODATA_MH)


def journal(message, niveau=Qgis.Info):
    """
    Écrit un message dans le journal QGIS du plugin.

    Paramètres
    ----------
    message : str
        Texte à écrire.
    niveau : Qgis.MessageLevel
        Niveau du message.
    """
    try:
        QgsMessageLog.logMessage(str(message), "mh_sm_plugin", niveau)
    except Exception:
        pass


def afficher_raster_qgis(chemin):
    """
    Charge un raster et l'ajoute au projet QGIS courant.

    Cette fonction sert uniquement au contrôle visuel.

    Paramètres
    ----------
    chemin : str
        Chemin du fichier raster.

    Retour
    ------
    QgsRasterLayer ou None
        Couche QGIS si le raster est valide, sinon None.
    """
    couche = QgsRasterLayer(chemin, os.path.basename(chemin))
    if not couche.isValid():
        journal("Raster invalide " + str(chemin), Qgis.Critical)
        return None

    QgsProject.instance().addMapLayer(couche)
    journal("Raster ajouté " + str(chemin), Qgis.Info)
    return couche


def apercu_med_triangles_qgis(chemin_med, nom_couche="MED triangles preview"):
    """
    Crée une couche mémoire de polygones représentant les triangles d'un fichier MED.

    Cette fonction sert à vérifier rapidement :
    - que le maillage est lisible
    - que les triangles sont cohérents en XY
    - que la couche peut être affichée sans traitement 3D

    Paramètres
    ----------
    chemin_med : str
        Chemin du fichier MED.
    nom_couche : str
        Nom de la couche QGIS créée.

    Retour
    ------
    QgsVectorLayer
        Couche mémoire en polygones.
    """
    if not chemin_med or not os.path.isfile(chemin_med):
        raise RuntimeError("Chemin MED invalide")

    points, triangles, champs_tri, champs_pts = lit_med_champs(chemin_med)

    couche = QgsVectorLayer("Polygon", nom_couche, "memory")
    prov = couche.dataProvider()

    champs = QgsFields()
    champs.append(QgsField("id", QVariant.Int))
    prov.addAttributes(champs)
    couche.updateFields()

    entites = []
    for ident, tri in enumerate(triangles):
        ia, ib, ic = tri

        a = points[ia]
        b = points[ib]
        c = points[ic]

        anneau = [
            QgsPointXY(float(a[0]), float(a[1])),
            QgsPointXY(float(b[0]), float(b[1])),
            QgsPointXY(float(c[0]), float(c[1])),
            QgsPointXY(float(a[0]), float(a[1])),
        ]

        entite = QgsFeature(couche.fields())
        entite.setAttribute("id", int(ident))
        entite.setGeometry(QgsGeometry.fromPolygonXY([anneau]))
        entites.append(entite)

    prov.addFeatures(entites)
    couche.updateExtents()

    QgsProject.instance().addMapLayer(couche)
    journal("Aperçu MED ajouté " + str(chemin_med), Qgis.Info)
    return couche


def ecrire_geotiff(raster, gt, chemin_sortie, epsg=None, nodata=NODATA_TIF):
    """
    Écrit un GeoTIFF float32 à partir d'un tableau numpy.

    Paramètres
    ----------
    raster : np.ndarray
        Raster en float. Les NaN sont convertis en nodata.
    gt : tuple
        Geotransform GDAL.
    chemin_sortie : str
        Chemin du fichier à écrire.
    epsg : int ou None
        EPSG à écrire dans le fichier si disponible.
    nodata : float
        Valeur nodata à écrire.

    Retour
    ------
    str
        Chemin du fichier écrit.
    """
    nb_lignes, nb_colonnes = raster.shape

    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(chemin_sortie, nb_colonnes, nb_lignes, 1, gdal.GDT_Float32)
    ds.SetGeoTransform(gt)

    if epsg is not None:
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(int(epsg))
        ds.SetProjection(srs.ExportToWkt())

    bande = ds.GetRasterBand(1)
    bande.SetNoDataValue(float(nodata))

    data = raster.astype(np.float32, copy=True)
    data[~np.isfinite(data)] = float(nodata)

    bande.WriteArray(data)
    bande.FlushCache()
    ds.FlushCache()
    ds = None

    return chemin_sortie


def export_mh_vers_sm_val(chemin_mh, chemin_cir, chemin_val, pondere=False):
    """
    Exécute la conversion MH vers SM.

    Étapes
    ------
    1) Lecture du raster MH (ASCII grid)
    2) Lecture du fichier scene_triangle.cir
    3) Calcul du mapping pixel vers triangle par intersection
    4) Calcul d'une valeur par triangle par moyenne
    5) Écriture du fichier .val

    Paramètres
    ----------
    chemin_mh : str
        Chemin du raster MH au format .txt ou .asc.
    chemin_cir : str
        Chemin du fichier scene_triangle.cir.
    chemin_val : str
        Chemin du fichier .val à écrire.
    pondere : bool
        Si True, moyenne pondérée par aire d'intersection.
        Si False, moyenne simple.

    Retour
    ------
    dict
        Dictionnaire résumé renvoyé par mh_vers_sm_val.
    """
    journal("Export MH vers SM", Qgis.Info)
    journal("MH " + str(chemin_mh), Qgis.Info)
    journal("CIR " + str(chemin_cir), Qgis.Info)
    journal("VAL " + str(chemin_val), Qgis.Info)

    resultat = mh_vers_sm_val(
        mh_txt=chemin_mh,
        cir=chemin_cir,
        val_sortie=chemin_val,
        pondere=pondere
    )

    journal("Export terminé " + str(resultat.get("val", "")), Qgis.Info)
    return resultat


def reconstruire_mh_depuis_sm(chemin_mh_ref, chemin_cir, chemin_val, chemin_tif, epsg=None, pondere=False):
    """
    Reconstruit un raster MH à partir d'un fichier .val et écrit un GeoTIFF.

    Étapes
    ------
    1) Lecture du raster MH de référence pour récupérer la grille
    2) Lecture du fichier scene_triangle.cir
    3) Lecture du fichier .val
    4) Calcul du mapping pixel vers triangle par intersection
    5) Calcul de la valeur du pixel par moyenne des triangles intersectants
    6) Écriture du GeoTIFF

    Paramètres
    ----------
    chemin_mh_ref : str
        Chemin du raster MH de référence.
    chemin_cir : str
        Chemin du fichier scene_triangle.cir.
    chemin_val : str
        Chemin du fichier .val à utiliser.
    chemin_tif : str
        Chemin du GeoTIFF à écrire.
    epsg : int ou None
        EPSG à écrire dans le GeoTIFF si disponible.
    pondere : bool
        Si True, moyenne pondérée par aire d'intersection.
        Si False, moyenne simple.

    Retour
    ------
    str
        Chemin du GeoTIFF écrit.
    """
    journal("Reconstruction MH depuis SM", Qgis.Info)
    journal("MH ref " + str(chemin_mh_ref), Qgis.Info)
    journal("CIR " + str(chemin_cir), Qgis.Info)
    journal("VAL " + str(chemin_val), Qgis.Info)

    raster, gt, nodata = sm_vers_mh_raster(
        mh_txt_ref=chemin_mh_ref,
        cir=chemin_cir,
        val_path=chemin_val,
        pondere=pondere
    )

    ecrire_geotiff(raster, gt, chemin_tif, epsg=epsg, nodata=NODATA_TIF)

    journal("GeoTIFF écrit " + str(chemin_tif), Qgis.Info)
    return chemin_tif

