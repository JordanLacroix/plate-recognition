"""Détecteur factice — fait tourner le pipeline end-to-end SANS modèle entraîné.

Deux usages:
1. Débloquer `anpr_poc.run` et les tests d'intégration tant que le vrai détecteur
   n'existe pas (cf. RISQUES R1).
2. Injecter des boîtes connues dans les tests.

⚠️ NE PAS utiliser en production: ne détecte rien, renvoie une boîte fixe.
"""

from __future__ import annotations

import numpy as np

from anpr_poc.types import BBox, Detection


class StubDetector:
    """Renvoie une boîte fixe (fraction centrale de l'image) à chaque frame.

    boxes: si fourni, liste de (x1,y1,x2,y2) renvoyée telle quelle (tests).
    Sinon, une boîte couvrant `frac` de la largeur/hauteur, centrée.
    """

    def __init__(
        self,
        boxes: list[tuple[float, float, float, float]] | None = None,
        frac: float = 0.5,
        confidence: float = 1.0,
    ) -> None:
        self._boxes = boxes
        self._frac = frac
        self._confidence = confidence

    def detect(self, frame: np.ndarray, conf_min: float) -> list[Detection]:
        if self._confidence < conf_min:
            return []
        if self._boxes is not None:
            return [Detection(BBox(*b), self._confidence) for b in self._boxes]
        h, w = frame.shape[:2]
        fw, fh = w * self._frac, h * self._frac
        x1, y1 = (w - fw) / 2, (h - fh) / 2
        return [Detection(BBox(x1, y1, x1 + fw, y1 + fh), self._confidence)]
