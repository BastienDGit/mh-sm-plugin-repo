# -*- coding: utf-8 -*-
"""
Module principal du plugin QGIS MH vers SM.

Fonctionnalités
---------------
1) Conversion MH vers SM
   - Entrées : un raster MH (.txt ou .asc) au format ESRI ASCII grid
              un fichier scene_triangle.cir
   - Sortie  : un fichier .val au format SM

2) Conversion SM vers MH
   - Entrées : un fichier .val au format SM
              un raster MH de référence (sert uniquement à récupérer la grille)
              un fichier scene_triangle.cir
   - Sortie  : un fichier MH (.asc) écrit dans le même dossier que le .val
              sous la forme nom2asc.asc

3) Comparaison rasters
   - Compare le raster MH de référence avec le raster reconstruit depuis le .val
   - Crée trois GeoTIFF dans le dossier du .val :
       - référence
       - reconstruit
       - erreur (reconstruit moins référence)
   - Calcule des métriques simples : nombre de pixels valides, MAE, RMSE, corr
   - Affiche les métriques dans une fenêtre (popup) et un résumé dans la barre QGIS

4) Visualisation MED (optionnel)
   - Ouvre une fenêtre PyVista avec un filtrage simple
"""

import os
import tempfile
import traceback

import numpy as np
from osgeo import gdal, osr

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import QgsMessageLog, Qgis, QgsRasterLayer, QgsProject

from .plugin_mh_sm_dialog import MhSmDialog
from .visu_pyvista import visualiser_med_pyvista

from .src.io_mh_sm_exchange import (
    mh_vers_sm_val,
    lire_mh_ascii,
    lire_scene_triangle_cir,
    aligner_par_bbox,
    ecrire_mh_ascii,
    NODATA_MH,
)
from .src.mapping import mapping_surface


NODATA_TIF = float(NODATA_MH)


def journal(message, niveau=Qgis.Info):
    """
    Écrit un message dans le journal QGIS du plugin.

    Paramètres
    ----------
    message : str
        Texte à afficher.
    niveau : Qgis.MessageLevel
        Niveau du message : Qgis.Info, Qgis.Warning, Qgis.Critical.
    """
    try:
        QgsMessageLog.logMessage(str(message), "mh_sm_plugin", niveau)
    except Exception:
        pass


def epsg_depuis_raster(chemin_raster):
    """
    Récupère l'EPSG d'un raster si possible, via GDAL.

    Paramètres
    ----------
    chemin_raster : str
        Chemin du raster.

    Retour
    ------
    int ou None
        Code EPSG si disponible, sinon None.
    """
    try:
        ds = gdal.Open(chemin_raster)
        if ds is None:
            return None

        wkt = ds.GetProjection()
        if not wkt:
            return None

        srs = osr.SpatialReference()
        srs.ImportFromWkt(wkt)

        code = srs.GetAuthorityCode(None)
        return int(code) if code else None
    except Exception:
        return None


def ecrire_geotiff(ras, gt, chemin_sortie, epsg=None, nodata=NODATA_TIF):
    """
    Écrit un raster GeoTIFF float32.

    Paramètres
    ----------
    ras : np.ndarray
        Tableau raster en float. Les valeurs NaN sont écrites en nodata.
    gt : tuple
        Geotransform GDAL.
    chemin_sortie : str
        Chemin du fichier de sortie.
    epsg : int ou None
        EPSG à écrire dans le GeoTIFF si disponible.
    nodata : float
        Valeur nodata écrite dans le fichier.

    Retour
    ------
    None
    """
    nb_lignes, nb_colonnes = ras.shape

    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(chemin_sortie, nb_colonnes, nb_lignes, 1, gdal.GDT_Float32)
    ds.SetGeoTransform(gt)

    if epsg is not None:
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(int(epsg))
        ds.SetProjection(srs.ExportToWkt())

    band = ds.GetRasterBand(1)
    band.SetNoDataValue(float(nodata))

    data = ras.astype(np.float32, copy=True)
    data[~np.isfinite(data)] = float(nodata)

    band.WriteArray(data)
    band.FlushCache()
    ds.FlushCache()
    ds = None


def ajouter_raster_qgis(chemin, nom):
    """
    Ajoute un raster dans le projet QGIS courant.

    Paramètres
    ----------
    chemin : str
        Chemin du raster à charger.
    nom : str
        Nom affiché dans QGIS.

    Retour
    ------
    QgsRasterLayer ou None
        Couche ajoutée si valide, sinon None.
    """
    couche = QgsRasterLayer(chemin, nom)
    if not couche.isValid():
        journal("Impossible de charger le raster " + str(chemin), Qgis.Critical)
        return None
    QgsProject.instance().addMapLayer(couche)
    return couche


def lire_val(chemin_val):
    """
    Lit un fichier .val et renvoie les valeurs des triangles dans l'ordre.

    Paramètres
    ----------
    chemin_val : str
        Chemin du fichier .val.

    Retour
    ------
    np.ndarray
        Valeurs par triangle dans l'ordre du fichier scene_triangle.cir.
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


def sm_vers_mh_raster(mh_txt_ref, cir, val_path):
    """
    Reconstruit un raster MH à partir d'un fichier .val.

    Méthode
    -------
    - On récupère la grille à partir du raster MH de référence.
    - On calcule le mapping pixel triangle via intersection géométrique.
    - Pour chaque pixel, on calcule la moyenne des valeurs des triangles
      qui intersectent le pixel.

    Paramètres
    ----------
    mh_txt_ref : str
        Raster MH de référence. Utilisé uniquement pour la grille et le géoréférencement.
    cir : str
        Fichier scene_triangle.cir.
    val_path : str
        Fichier .val d'entrée.

    Retour
    ------
    tuple[np.ndarray, tuple, float]
        ras_rec : raster reconstruit, NaN sur les pixels non couverts
        gt : geotransform
        nodata : valeur nodata de référence
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

        vals = []
        for id_tri, aire in lst:
            idx = int(id_tri)
            if 0 <= idx < len(val_tri):
                vals.append(float(val_tri[idx]))

        if vals:
            ras_rec[lig, col] = float(np.mean(vals))

    return ras_rec, gt, float(nodata)


def carte_erreur(ras_ref, ras_pred):
    """
    Calcule la carte d'erreur pixel par pixel.

    Paramètres
    ----------
    ras_ref : np.ndarray
        Raster de référence.
    ras_pred : np.ndarray
        Raster reconstruit.

    Retour
    ------
    np.ndarray
        Raster d'erreur (reconstruit moins référence), NaN sur pixels non comparables.
    """
    err = np.full(ras_ref.shape, np.nan, dtype=float)
    ok = np.isfinite(ras_ref) & np.isfinite(ras_pred)
    err[ok] = ras_pred[ok] - ras_ref[ok]
    return err


def metriques(ras_ref, ras_pred):
    """
    Calcule des métriques simples sur les pixels valides.

    Paramètres
    ----------
    ras_ref : np.ndarray
        Raster de référence.
    ras_pred : np.ndarray
        Raster reconstruit.

    Retour
    ------
    dict
        n_valid : nombre de pixels comparés
        mae : erreur absolue moyenne
        rmse : racine de l'erreur quadratique moyenne
        corr : corrélation linéaire
    """
    ok = np.isfinite(ras_ref) & np.isfinite(ras_pred)
    n = int(ok.sum())
    if n == 0:
        return {"n_valid": 0}

    r = ras_ref[ok].astype(float)
    p = ras_pred[ok].astype(float)
    d = p - r

    mae = float(np.mean(np.abs(d)))
    rmse = float(np.sqrt(np.mean(d ** 2)))

    if r.size > 1 and np.std(r) > 0 and np.std(p) > 0:
        corr = float(np.corrcoef(r, p)[0, 1])
    else:
        corr = float("nan")

    return {"n_valid": n, "mae": mae, "rmse": rmse, "corr": corr}


class MhSmPlugin:
    """
    Classe principale du plugin QGIS.

    Cette classe est instanciée par QGIS via classFactory dans __init__.py.
    Elle gère :
    - l'ajout du bouton dans l'interface QGIS
    - l'ouverture de la fenêtre
    - le raccordement des actions aux boutons
    """

    def __init__(self, iface):
        """
        Paramètres
        ----------
        iface : QgisInterface
            Interface QGIS fournie au chargement du plugin.
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.menu_nom = self.tr("MH SM Plugin")
        self.dialog = None

    def tr(self, message):
        """
        Traduction standard QGIS.

        Paramètres
        ----------
        message : str
            Texte à traduire.

        Retour
        ------
        str
            Texte traduit.
        """
        return QCoreApplication.translate("MhSmPlugin", message)

    def initGui(self):
        """
        Ajoute un bouton dans QGIS et une entrée de menu.
        """
        icone = os.path.join(self.plugin_dir, "icon.png")

        self.action = QAction(
            QIcon(icone),
            self.tr("MH SM Plugin"),
            self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)

        self.iface.addPluginToMenu(self.menu_nom, self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        """
        Retire le bouton et l'entrée de menu lors de la désactivation du plugin.
        """
        if self.action is not None:
            self.iface.removePluginMenu(self.menu_nom, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    def run(self):
        """
        Ouvre la fenêtre du plugin et connecte les boutons si nécessaire.
        """
        try:
            if self.dialog is None:
                self.dialog = MhSmDialog(self.iface.mainWindow())
                self._connecter_actions()

            self.dialog.show()
            self.dialog.raise_()
            self.dialog.activateWindow()

        except Exception:
            msg = traceback.format_exc()
            journal(msg, Qgis.Critical)
            QMessageBox.critical(self.iface.mainWindow(), "Erreur plugin", msg)

    def _connecter_actions(self):
        """
        Connecte les boutons de l'interface aux méthodes du plugin.
        """
        if hasattr(self.dialog, "btn_export"):
            self.dialog.btn_export.clicked.connect(self._export_mh_vers_sm)

        if hasattr(self.dialog, "btn_reconstruire"):
            self.dialog.btn_reconstruire.clicked.connect(self._reconstruire_mh)

        if hasattr(self.dialog, "btn_visu_mh"):
            self.dialog.btn_visu_mh.clicked.connect(self._visu_mh)

        if hasattr(self.dialog, "btn_comparer"):
            self.dialog.btn_comparer.clicked.connect(self._comparer_rasters)

        if hasattr(self.dialog, "btn_visu_med"):
            self.dialog.btn_visu_med.clicked.connect(self._visu_med)

    def _export_mh_vers_sm(self):
        """
        Convertit MH vers SM.

        Entrées
        -------
        - MH : chemin_mh()
        - CIR : chemin_cir()
        - Sortie VAL : chemin_val_sortie()

        Sortie
        ------
        Écrit le fichier .val sur disque.
        """
        try:
            mh = self.dialog.chemin_mh()
            cir = self.dialog.chemin_cir()
            val_out = self.dialog.chemin_val_sortie()

            if not mh or not os.path.isfile(mh):
                raise RuntimeError("Fichier MH introuvable")
            if not cir or not os.path.isfile(cir):
                raise RuntimeError("Fichier CIR introuvable")
            if not val_out:
                raise RuntimeError("Chemin de sortie val vide")

            mh_vers_sm_val(mh_txt=mh, cir=cir, val_sortie=val_out, pondere=False)

            self.iface.messageBar().pushMessage(
                "MH SM",
                "Export terminé",
                level=0,
                duration=5
            )

        except Exception:
            msg = traceback.format_exc()
            journal(msg, Qgis.Critical)
            QMessageBox.critical(self.iface.mainWindow(), "Erreur export", msg)

    def _visu_mh(self):
        """
        Affiche le fichier MH sélectionné dans QGIS.

        Cette fonction charge le raster tel quel, pour contrôle visuel.
        """
        try:
            mh = self.dialog.chemin_mh()
            if not mh:
                self.iface.messageBar().pushWarning("MH SM", "Aucun fichier MH sélectionné")
                return
            ajouter_raster_qgis(mh, "MH entrée")
        except Exception:
            msg = traceback.format_exc()
            journal(msg, Qgis.Critical)
            QMessageBox.critical(self.iface.mainWindow(), "Erreur affichage MH", msg)

    def _reconstruire_mh(self):
        """
        Convertit SM vers MH et écrit un fichier ASCII grid.

        Nom de sortie
        -------------
        Le fichier est écrit dans le dossier du .val d'entrée :
        nom2asc.asc
        """
        try:
            mh = self.dialog.chemin_mh()
            cir = self.dialog.chemin_cir()
            val_in = self.dialog.chemin_val_entree()

            if not mh or not os.path.isfile(mh):
                raise RuntimeError("Fichier MH de référence introuvable")
            if not cir or not os.path.isfile(cir):
                raise RuntimeError("Fichier CIR introuvable")
            if not val_in or not os.path.isfile(val_in):
                raise RuntimeError("Fichier val introuvable")

            dossier = os.path.dirname(val_in) or tempfile.gettempdir()
            base = os.path.splitext(os.path.basename(val_in))[0]
            asc_out = os.path.join(dossier, base + "2asc.asc")

            ras_rec, gt, _ = sm_vers_mh_raster(mh, cir, val_in)

            ecrire_mh_ascii(asc_out, ras_rec, gt, nodata=float(NODATA_MH))

            self.iface.messageBar().pushMessage(
                "MH SM",
                "Reconstruction terminée",
                level=0,
                duration=5
            )

            ajouter_raster_qgis(asc_out, "MH reconstruit " + base)

        except Exception:
            msg = traceback.format_exc()
            journal(msg, Qgis.Critical)
            QMessageBox.critical(self.iface.mainWindow(), "Erreur reconstruction", msg)

    def _comparer_rasters(self):
        """
        Compare le raster MH de référence avec le raster reconstruit depuis le .val.

        Sorties
        -------
        Trois GeoTIFF sont écrits dans le dossier du .val :
        - base_mh_ref.tif
        - base_mh_reconstruit.tif
        - base_mh_erreur.tif

        Affichage
        ---------
        - Un résumé des métriques est affiché dans la barre de message QGIS.
        - Les métriques détaillées sont affichées dans une fenêtre.
        """
        try:
            mh = self.dialog.chemin_mh()
            cir = self.dialog.chemin_cir()
            val_in = self.dialog.chemin_val_entree()

            if not mh or not os.path.isfile(mh):
                raise RuntimeError("Fichier MH introuvable")
            if not cir or not os.path.isfile(cir):
                raise RuntimeError("Fichier CIR introuvable")
            if not val_in or not os.path.isfile(val_in):
                raise RuntimeError("Fichier val introuvable")

            ras_ref, gt, _ = lire_mh_ascii(mh)
            ras_pred, _, _ = sm_vers_mh_raster(mh, cir, val_in)

            err = carte_erreur(ras_ref, ras_pred)
            stats = metriques(ras_ref, ras_pred)

            texte = (
                "Résultats comparaison\n\n"
                f"Pixels comparés : {int(stats.get('n_valid', 0))}\n"
                f"MAE : {float(stats.get('mae', float('nan'))):.6f}\n"
                f"RMSE : {float(stats.get('rmse', float('nan'))):.6f}\n"
                f"Corrélation : {float(stats.get('corr', float('nan'))):.6f}\n"
            )

            self.iface.messageBar().pushMessage(
                "MH SM",
                f"MAE={float(stats.get('mae', float('nan'))):.3f} "
                f"RMSE={float(stats.get('rmse', float('nan'))):.3f} "
                f"Corr={float(stats.get('corr', float('nan'))):.3f}",
                level=0,
                duration=8
            )

            QMessageBox.information(self.iface.mainWindow(), "Comparaison MH / reconstruit", texte)

            journal("Comparaison rasters", Qgis.Info)
            for k, v in stats.items():
                journal(str(k) + " " + str(v), Qgis.Info)

            epsg = epsg_depuis_raster(mh)
            dossier = os.path.dirname(val_in) or tempfile.gettempdir()
            base = os.path.splitext(os.path.basename(val_in))[0]

            tif_ref = os.path.join(dossier, base + "_mh_ref.tif")
            tif_pred = os.path.join(dossier, base + "_mh_reconstruit.tif")
            tif_err = os.path.join(dossier, base + "_mh_erreur.tif")

            ecrire_geotiff(ras_ref, gt, tif_ref, epsg=epsg, nodata=NODATA_TIF)
            ecrire_geotiff(ras_pred, gt, tif_pred, epsg=epsg, nodata=NODATA_TIF)
            ecrire_geotiff(err, gt, tif_err, epsg=epsg, nodata=NODATA_TIF)

            ajouter_raster_qgis(tif_ref, "MH référence " + base)
            ajouter_raster_qgis(tif_pred, "MH reconstruit " + base)
            ajouter_raster_qgis(tif_err, "Erreur " + base)

            self.iface.messageBar().pushMessage(
                "MH SM",
                "Comparaison terminée",
                level=0,
                duration=6
            )

        except Exception:
            msg = traceback.format_exc()
            journal(msg, Qgis.Critical)
            QMessageBox.critical(self.iface.mainWindow(), "Erreur comparaison", msg)

    def _visu_med(self):
        """
        Ouvre une visualisation PyVista du MED (optionnel).
        """
        try:
            med = self.dialog.chemin_med()
            if not med:
                self.iface.messageBar().pushWarning("MH SM", "Aucun fichier MED sélectionné")
                return
            if not os.path.isfile(med):
                raise RuntimeError("Fichier MED introuvable")

            visualiser_med_pyvista(
                chemin_med=med,
                marge_interieure=0.10,
                percentile_z=98
            )

        except Exception:
            msg = traceback.format_exc()
            journal(msg, Qgis.Critical)
            QMessageBox.critical(self.iface.mainWindow(), "Erreur visualisation MED", msg)

