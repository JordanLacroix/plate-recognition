"""PP-OCRv5 reco seule. Confiances par caractère requises pour le vote consensus.

Reco seule (pas de détection texte générique): un camion a du texte partout, la
bbox plaque vient du détecteur dédié.
"""

from __future__ import annotations

import numpy as np

from anpr_poc.types import Read


class PaddleReco:
    def __init__(self, lang: str = "en", use_gpu: bool = False) -> None:
        from paddleocr import PaddleOCR

        # rec seule: det=False. lang 'en' = jeu latin majuscules/chiffres.
        self._ocr = PaddleOCR(det=False, rec=True, use_angle_cls=False, lang=lang, use_gpu=use_gpu)

    def read(self, crop: np.ndarray, frame_idx: int = -1, country: str | None = None) -> Read | None:
        """OCR un crop plaque déjà redressé/strippé. Retourne None si vide."""
        result = self._ocr.ocr(crop, det=False, rec=True, cls=False)
        text, char_confs = self._extract(result)
        if not text:
            return None
        return Read(
            text=self._normalize(text),
            char_confidences=char_confs,
            country=country,
            frame_idx=frame_idx,
        )

    @staticmethod
    def _extract(result: object) -> tuple[str, tuple[float, ...]]:
        """Extrait (texte, confiances par char) de la sortie PaddleOCR.

        PaddleOCR reco rend un score par ligne, pas par char. On réplique le score
        ligne sur chaque char (approx POC). Pour du vrai par-char: exporter le modèle
        reco en ONNX et lire les logits CTC.
        """
        try:
            line = result[0][0] if result and result[0] else None
        except (IndexError, TypeError):
            line = None
        if not line:
            return "", ()
        text, score = line[0], float(line[1])
        return text, tuple(score for _ in text)

    @staticmethod
    def _normalize(text: str) -> str:
        return "".join(text.split()).upper()
