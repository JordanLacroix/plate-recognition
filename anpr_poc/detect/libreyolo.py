"""Wrapper détecteur torch (LibreYOLO MIT ou RF-DETR base/S Apache-2.0).

NOTE licence: LibreYOLO = MIT, RF-DETR base/S = Apache-2.0. Variantes RF-DETR
XL/2XL = licence PML -> INTERDITES. Ne jamais charger ces poids ici.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from anpr_poc.types import BBox, Detection


class TorchDetector:
    """Détecteur .pt via torch. Device MPS si dispo, sinon CPU."""

    def __init__(self, weights: str | Path, device: str | None = None) -> None:
        self.weights = Path(weights)
        self.device = device or self._pick_device()
        self._model = self._load()

    @staticmethod
    def _pick_device() -> str:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _load(self) -> object:
        # TODO: charger le modèle réel (LibreYOLO / RF-DETR).
        # Garder l'appel forward isolé pour l'export ONNX (voir export.py).
        raise NotImplementedError(
            "Brancher le chargement des poids LibreYOLO/RF-DETR fine-tunés plaque."
        )

    def detect(self, frame: np.ndarray, conf_min: float) -> list[Detection]:
        raise NotImplementedError("forward + post-process -> list[Detection]")

    @staticmethod
    def _to_detections(boxes_xyxy: np.ndarray, scores: np.ndarray, conf_min: float) -> list[Detection]:
        """Helper commun de post-process, réutilisable par le backend ONNX."""
        out: list[Detection] = []
        for (x1, y1, x2, y2), s in zip(boxes_xyxy, scores):
            if s >= conf_min:
                out.append(Detection(bbox=BBox(float(x1), float(y1), float(x2), float(y2)), confidence=float(s)))
        return out
