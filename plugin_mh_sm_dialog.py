# -*- coding: utf-8 -*-
"""


Ce module contient la classe de dialogue du plugin QGIS MH vers SM.

Rôle de cette classe
--------------------
- Charger l'interface définie dans le fichier .ui
- Connecter les boutons de sélection de fichiers
- Fournir des méthodes simples pour récupérer les chemins saisis

Ce module ne doit contenir aucune logique de calcul MH vers SM.
La logique de traitement est gérée dans le module principal du plugin.
"""

import os
import traceback

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
from qgis.core import QgsMessageLog, Qgis


CHEMIN_UI = os.path.join(os.path.dirname(__file__), "plugin_mh_sm_dialog_base.ui")
CLASSE_UI, _ = uic.loadUiType(CHEMIN_UI)


class MhSmDialog(QDialog, CLASSE_UI):
    """
    Fenêtre principale du plugin.

    Éléments attendus dans le fichier .ui
    ------------------------------------
    Bloc MH vers SM :
    - line_mh, btn_mh
    - line_cir, btn_cir
    - line_val, btn_val
    - btn_export

    Bloc SM vers MH :
    - line_val_in, btn_val_in
    - btn_reconstruire

    Outils :
    - btn_visu_mh
    - btn_comparer

    Optionnel :
    - line_med, btn_med, btn_visu_med

    Remarque
    --------
    Certains boutons peuvent être absents selon la version du .ui.
    Dans ce cas, la classe vérifie leur existence avant de connecter les signaux.
    """

    def __init__(self, parent=None):
        """
        Initialise la fenêtre, charge l'UI et connecte les boutons de navigation.

        Paramètres
        ----------
        parent : QWidget ou None
            Fenêtre parente QGIS, généralement iface.mainWindow().
        """
        super().__init__(parent)
        self.setupUi(self)

        self._journal("Dialogue initialisé", Qgis.Info)

        self._connecter_boutons()

    def _connecter_boutons(self):
        """
        Connecte les boutons de sélection de fichiers à leurs handlers.

        Cette méthode est isolée pour faciliter la lecture et éviter de mélanger
        l'initialisation UI avec la logique des signaux.
        """
        if hasattr(self, "btn_mh"):
            self.btn_mh.clicked.connect(self._choisir_mh)

        if hasattr(self, "btn_cir"):
            self.btn_cir.clicked.connect(self._choisir_cir)

        if hasattr(self, "btn_val"):
            self.btn_val.clicked.connect(self._choisir_val_sortie)

        if hasattr(self, "btn_val_in"):
            self.btn_val_in.clicked.connect(self._choisir_val_entree)

        if hasattr(self, "btn_med"):
            self.btn_med.clicked.connect(self._choisir_med)

    def _journal(self, message, niveau=Qgis.Info):
        """
        Écrit un message dans le journal QGIS.

        Paramètres
        ----------
        message : str
            Message à enregistrer.
        niveau : Qgis.MessageLevel
            Niveau de gravité : Qgis.Info, Qgis.Warning, Qgis.Critical.
        """
        try:
            QgsMessageLog.logMessage(str(message), "mh_sm_plugin", niveau)
        except Exception:
            pass

    def _afficher_erreur(self, titre, details):
        """
        Affiche une erreur sous forme de fenêtre et écrit dans le journal QGIS.

        Paramètres
        ----------
        titre : str
            Titre de la fenêtre d'erreur.
        details : str
            Détails à afficher et à enregistrer dans le journal.
        """
        texte = details if isinstance(details, str) else str(details)
        self._journal(texte, Qgis.Critical)
        QMessageBox.critical(self, titre, texte)

    def _choisir_mh(self):
        """
        Ouvre une boîte de dialogue pour choisir le fichier MH d'entrée.

        Formats attendus : .txt ou .asc (ESRI ASCII grid).
        """
        try:
            chemin, _ = QFileDialog.getOpenFileName(
                self,
                "Choisir un raster MH",
                "",
                "MH (*.txt *.asc);;Tous les fichiers (*.*)"
            )
            if chemin and hasattr(self, "line_mh"):
                self.line_mh.setText(chemin)
        except Exception:
            self._afficher_erreur("Erreur sélection MH", traceback.format_exc())

    def _choisir_cir(self):
        """
        Ouvre une boîte de dialogue pour choisir le fichier scene_triangle.cir.
        """
        try:
            chemin, _ = QFileDialog.getOpenFileName(
                self,
                "Choisir scene_triangle.cir",
                "",
                "CIR (*.cir);;Tous les fichiers (*.*)"
            )
            if chemin and hasattr(self, "line_cir"):
                self.line_cir.setText(chemin)
        except Exception:
            self._afficher_erreur("Erreur sélection CIR", traceback.format_exc())

    def _choisir_val_sortie(self):
        """
        Ouvre une boîte de dialogue pour choisir le fichier .val de sortie
        de la conversion MH vers SM.
        """
        try:
            chemin, _ = QFileDialog.getSaveFileName(
                self,
                "Choisir le fichier val de sortie",
                "",
                "VAL (*.val)"
            )
            if not chemin:
                return

            if not chemin.lower().endswith(".val"):
                chemin += ".val"

            if hasattr(self, "line_val"):
                self.line_val.setText(chemin)
        except Exception:
            self._afficher_erreur("Erreur sélection sortie val", traceback.format_exc())

    def _choisir_val_entree(self):
        """
        Ouvre une boîte de dialogue pour choisir un fichier .val existant
        pour la conversion SM vers MH.
        """
        try:
            chemin, _ = QFileDialog.getOpenFileName(
                self,
                "Choisir un fichier val",
                "",
                "VAL (*.val);;Tous les fichiers (*.*)"
            )
            if chemin and hasattr(self, "line_val_in"):
                self.line_val_in.setText(chemin)
        except Exception:
            self._afficher_erreur("Erreur sélection entrée val", traceback.format_exc())

    def _choisir_med(self):
        """
        Ouvre une boîte de dialogue pour choisir un fichier MED (optionnel).
        """
        try:
            chemin, _ = QFileDialog.getOpenFileName(
                self,
                "Choisir un fichier MED",
                "",
                "MED (*.med);;Tous les fichiers (*.*)"
            )
            if chemin and hasattr(self, "line_med"):
                self.line_med.setText(chemin)
        except Exception:
            self._afficher_erreur("Erreur sélection MED", traceback.format_exc())

    def chemin_mh(self):
        """
        Retourne le chemin du raster MH d'entrée.

        Retour
        ------
        str
            Chemin ou chaîne vide si le widget n'existe pas.
        """
        return self.line_mh.text().strip() if hasattr(self, "line_mh") else ""

    def chemin_cir(self):
        """
        Retourne le chemin du fichier scene_triangle.cir.

        Retour
        ------
        str
            Chemin ou chaîne vide si le widget n'existe pas.
        """
        return self.line_cir.text().strip() if hasattr(self, "line_cir") else ""

    def chemin_val_sortie(self):
        """
        Retourne le chemin du fichier .val de sortie (MH vers SM).

        Retour
        ------
        str
            Chemin ou chaîne vide si le widget n'existe pas.
        """
        return self.line_val.text().strip() if hasattr(self, "line_val") else ""

    def chemin_val_entree(self):
        """
        Retourne le chemin du fichier .val d'entrée (SM vers MH).

        Retour
        ------
        str
            Chemin ou chaîne vide si le widget n'existe pas.
        """
        return self.line_val_in.text().strip() if hasattr(self, "line_val_in") else ""

    def chemin_med(self):
        """
        Retourne le chemin du fichier MED (optionnel).

        Retour
        ------
        str
            Chemin ou chaîne vide si le widget n'existe pas.
        """
        return self.line_med.text().strip() if hasattr(self, "line_med") else ""

