"""Détecteur ONNX Runtime. CoreML EP sur M1, CUDA/TensorRT EP sur Jetson.

Même graphe ONNX des deux côtés -> portabilité garantie.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from anpr_poc.detect.libreyolo import TorchDetector
from anpr_poc.types import Detection


class OnnxDetector:
    def __init__(self, weights: str | Path, providers: list[str] | None = None) -> None:
        import onnxruntime as ort

        self.weights = Path(weights)
        # M1: CoreML puis CPU. Jetson: substituer TensorrtExecutionProvider/CUDA.
        self.providers = providers or ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        self._sess = ort.InferenceSession(str(self.weights), providers=self.providers)
        self._input = self._sess.get_inputs()[0].name

    def detect(self, frame: np.ndarray, conf_min: float) -> list[Detection]:
        blob = self._preprocess(frame)
        outputs = self._sess.run(None, {self._input: blob})
        boxes, scores = self._postprocess(outputs, frame.shape[:2])
        return TorchDetector._to_detections(boxes, scores, conf_min)

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        raise NotImplementedError("resize/letterbox + normalize + NCHW selon le modèle exporté.")

    def _postprocess(self, outputs: list[np.ndarray], hw: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError("decode + NMS -> (boxes_xyxy px, scores).")
