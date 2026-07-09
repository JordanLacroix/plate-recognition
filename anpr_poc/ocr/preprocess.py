"""Pré-OCR: redressement homographie + strip euroband. Pas de dépendance modèle."""

from __future__ import annotations

import cv2
import numpy as np


def rectify(crop: np.ndarray, homography: np.ndarray | None) -> np.ndarray:
    """Warp le crop plaque en quasi fronto-parallèle via homographie pré-calibrée.

    homography None ou identité -> retourne le crop inchangé.
    """
    if homography is None:
        return crop
    if np.allclose(homography, np.eye(3)):
        return crop
    h, w = crop.shape[:2]
    warped: np.ndarray = cv2.warpPerspective(crop, homography, (w, h), flags=cv2.INTER_LINEAR)
    return warped


def euroband_strip(crop: np.ndarray, frac: float = 0.11) -> np.ndarray:
    """Crop ~10-12 % de gauche (bande bleue UE + lettre pays + étoiles).

    Évite que l'OCR lise 'F', 'D', 'NL'... comme des caractères plaque.
    """
    if not 0.0 <= frac < 0.5:
        raise ValueError(f"frac hors bornes: {frac}")
    w = crop.shape[1]
    cut = int(round(w * frac))
    return crop[:, cut:]


def read_country_letter(crop: np.ndarray, frac: float = 0.11) -> np.ndarray:
    """Retourne la sous-bande euroband (pour OCR optionnel de la lettre pays -> routage)."""
    w = crop.shape[1]
    cut = int(round(w * frac))
    return crop[:, :cut]
