# -*- coding: utf-8 -*-
"""


Ce module sert à vérifier la cohérence d'un fichier SM au format .val
par rapport au fichier scene_triangle.cir.

Objectifs de la vérification

1) Vérifier que le découpage en facettes est identique
   - même nombre de facettes
   - mêmes tailles de facettes dans le même ordre

2) Vérifier que le nombre total de triangles correspond au nombre de valeurs

3) Donner des statistiques simples sur les valeurs
   - nombre de valeurs
   - min, max, moyenne
   - pourcentage de zéros

Ce module ne fait aucun calcul géométrique. Il vérifie uniquement la structure
et la cohérence globale des fichiers cir et val afin de ne pas lancer de pipeline avec deux fichiers qui ne correspondent pas. 
"""

import re
import numpy as np


def lire_tailles_cir(chemin_cir):
    """
    Lit uniquement le découpage en facettes du fichier scene_triangle.cir.

    Le fichier contient des lignes du type :
    f1 68
    f2 12
    etc.

    Paramètres
    ----------
    chemin_cir : str
        Chemin du fichier scene_triangle.cir.

    Retour
    ------
    list[int]
        Liste des tailles de facettes, dans l'ordre de lecture.
        Chaque élément correspond au nombre de triangles de la facette.
    """
    tailles = []

    with open(chemin_cir, "r", errors="ignore") as fichier:
        for ligne in fichier:
            texte = ligne.strip()
            if not texte:
                continue

            match = re.match(r"^f(\d+)\s+(\d+)", texte)
            if match:
                tailles.append(int(match.group(2)))

    return tailles


def lire_val(chemin_val):
    """
    Lit un fichier .val et extrait :
    - la taille de chaque facette
    - la liste des valeurs par triangle

    Hypothèses
    ----------
    - La première ligne est un en-tête et est ignorée
    - Les facettes sont décrites par des lignes du type : f1 68
    - Les valeurs suivent sur les lignes suivantes, une valeur par ligne

    Paramètres
    ----------
    chemin_val : str
        Chemin du fichier .val.

    Retour
    ------
    tuple[list[int], np.ndarray]
        tailles_facettes : tailles des facettes dans l'ordre
        valeurs : tableau numpy des valeurs par triangle
    """
    tailles_facettes = []
    valeurs = []

    with open(chemin_val, "r", errors="ignore") as fichier:
        lignes = [l.strip() for l in fichier if l.strip()]

    if len(lignes) == 0:
        return [], np.asarray([], dtype=float)

    index = 1
    while index < len(lignes):
        texte = lignes[index]

        if texte.startswith("f"):
            morceaux = texte.split()
            if len(morceaux) < 2:
                index += 1
                continue

            nb = int(morceaux[1])
            tailles_facettes.append(nb)
            index += 1

            for _ in range(nb):
                if index >= len(lignes):
                    break

                val_txt = lignes[index].replace("\t", " ").split()
                if len(val_txt) > 0:
                    valeurs.append(float(val_txt[0]))

                index += 1
        else:
            index += 1

    return tailles_facettes, np.asarray(valeurs, dtype=float)


def stats_valeurs(valeurs):
    """
    Calcule des statistiques simples sur un tableau de valeurs.

    Paramètres
    ----------
    valeurs : np.ndarray
        Tableau des valeurs par triangle.

    Retour
    ------
    dict
        n : nombre de valeurs
        min : minimum
        max : maximum
        moyenne : moyenne
        pct_zeros : pourcentage de valeurs égales à zéro
    """
    if valeurs.size == 0:
        return {
            "n": 0,
            "min": float("nan"),
            "max": float("nan"),
            "moyenne": float("nan"),
            "pct_zeros": float("nan"),
        }

    n = int(valeurs.size)
    vmin = float(np.min(valeurs))
    vmax = float(np.max(valeurs))
    moy = float(np.mean(valeurs))
    pct_zeros = float(np.mean(valeurs == 0.0) * 100.0)

    return {
        "n": n,
        "min": vmin,
        "max": vmax,
        "moyenne": moy,
        "pct_zeros": pct_zeros,
    }


def verifier_cir_val(chemin_cir, chemin_val, afficher=True):
    """
    Vérifie la cohérence d'un fichier .val par rapport à un fichier .cir.

    Vérifications effectuées
    ------------------------
    1) Nombre de facettes
    2) Tailles des facettes (ordre strict)
    3) Nombre total de triangles contre nombre de valeurs
    4) Statistiques sur les valeurs

    Paramètres
    ----------
    chemin_cir : str
        Chemin vers scene_triangle.cir.
    chemin_val : str
        Chemin vers le fichier .val.
    afficher : bool
        Si True, affiche un résumé dans la console.

    Retour
    ------
    dict
        ok_facettes : bool
        ok_nb_valeurs : bool
        nb_facettes_cir : int
        nb_facettes_val : int
        nb_triangles_cir : int
        nb_valeurs_val : int
        stats : dict
    """
    tailles_cir = lire_tailles_cir(chemin_cir)
    tailles_val, valeurs = lire_val(chemin_val)

    nb_facettes_cir = int(len(tailles_cir))
    nb_facettes_val = int(len(tailles_val))
    nb_triangles_cir = int(sum(tailles_cir))
    nb_valeurs_val = int(valeurs.size)

    ok_facettes = (tailles_cir == tailles_val)
    ok_nb_valeurs = (nb_triangles_cir == nb_valeurs_val)

    stats = stats_valeurs(valeurs)

    if afficher:
        print("Nombre de facettes cir", nb_facettes_cir, "nombre de facettes val", nb_facettes_val)
        print("Nombre de triangles cir", nb_triangles_cir, "nombre de valeurs val", nb_valeurs_val)

        if ok_facettes:
            print("Découpage facettes identique")
        else:
            print("Découpage facettes différent")

        if ok_nb_valeurs:
            print("Nombre de valeurs cohérent")
        else:
            print("Nombre de valeurs non cohérent")

        print("Nombre de valeurs", stats["n"])
        print("Minimum", stats["min"], "maximum", stats["max"])
        print("Moyenne", stats["moyenne"])
        print("Pourcentage de zeros", stats["pct_zeros"])

    return {
        "ok_facettes": ok_facettes,
        "ok_nb_valeurs": ok_nb_valeurs,
        "nb_facettes_cir": nb_facettes_cir,
        "nb_facettes_val": nb_facettes_val,
        "nb_triangles_cir": nb_triangles_cir,
        "nb_valeurs_val": nb_valeurs_val,
        "stats": stats,
    }

