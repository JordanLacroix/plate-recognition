"""Interface détecteur. Aucun code Mac-only ici — le backend est commutable."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np

from anpr_poc.types import Detection


@runtime_checkable
class Detector(Protocol):
    """Contrat détecteur plaque. Une implémentation par backend."""

    def detect(self, frame: np.ndarray, conf_min: float) -> list[Detection]:
        """Retourne les bboxes plaque au-dessus de conf_min pour une frame BGR."""
        ...


def load_detector(weights: str | Path, backend: str = "auto") -> Detector:
    """Fabrique. Choisit le backend selon l'extension ou `backend` explicite.

    backend: "auto" | "torch" | "onnx" | "tensorrt"
    - .pt   -> torch (MPS/CPU sur M1)
    - .onnx -> onnxruntime (CoreML EP sur M1)
    - .engine -> TensorRT (Jetson; pas implémenté sur Mac)
    """
    weights = Path(weights)
    if backend == "auto":
        backend = {".pt": "torch", ".onnx": "onnx", ".engine": "tensorrt"}.get(
            weights.suffix, "onnx"
        )

    if backend == "torch":
        from anpr_poc.detect.libreyolo import TorchDetector

        return TorchDetector(weights)
    if backend == "onnx":
        from anpr_poc.detect.onnx_detector import OnnxDetector

        return OnnxDetector(weights)
    if backend == "tensorrt":
        raise NotImplementedError("TensorRT backend: portage Jetson, pas sur Mac.")
    raise ValueError(f"Backend inconnu: {backend}")
