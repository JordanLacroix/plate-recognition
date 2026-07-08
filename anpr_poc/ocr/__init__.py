"""OCR reco plaque. PP-OCRv5 reco seule (Apache-2.0). CPU ou ONNX+CoreML."""

from anpr_poc.ocr.paddle_reco import PaddleReco
from anpr_poc.ocr.preprocess import euroband_strip, rectify

__all__ = ["PaddleReco", "euroband_strip", "rectify"]
