"""Écriture des snapshots de preuve. RGPD: floute le fond, garde la plaque nette.

Minimisation: on ne conserve qu'une image par événement confirmé, avec tout
sauf la plaque flouté (anonymise visages / véhicules / environnement).
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from anpr_poc.types import BBox, Event


class SnapshotWriter:
    def __init__(self, out_dir: str | Path, blur_background: bool = True) -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.blur_background = blur_background

    def save(self, frame: np.ndarray, bbox: BBox, event: Event) -> str:
        """Écrit un JPEG (fond flouté si activé) et retourne son chemin."""
        img = frame.copy()
        if self.blur_background:
            img = self._blur_except(img, bbox)
        name = f"{event.tracker_id:06d}_{event.plate}_{int(event.timestamp * 1000):09d}.jpg"
        path = self.out_dir / name
        cv2.imwrite(str(path), img)
        return str(path)

    @staticmethod
    def _blur_except(img: np.ndarray, bbox: BBox) -> np.ndarray:
        """Floute toute l'image sauf la boîte plaque (laissée nette, lisible)."""
        h, w = img.shape[:2]
        blurred: np.ndarray = cv2.GaussianBlur(img, (31, 31), 0)
        x1 = max(0, int(bbox.x1))
        y1 = max(0, int(bbox.y1))
        x2 = min(w, int(bbox.x2))
        y2 = min(h, int(bbox.y2))
        if x2 > x1 and y2 > y1:
            blurred[y1:y2, x1:x2] = img[y1:y2, x1:x2]
        return blurred
