"""Détection plaque. Backend-agnostic: .pt (MPS) / .onnx (CoreML) / .engine (TensorRT)."""

from anpr_poc.detect.base import Detector, load_detector

__all__ = ["Detector", "load_detector"]
