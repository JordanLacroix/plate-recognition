"""PP-OCRv5/v6 reco. API PaddleOCR 3.x. Plaques normalisées CANONIQUES (alphanumérique).

Reco seule (pas de détection texte générique): un camion a du texte partout, la
bbox plaque vient du détecteur dédié.

NOTE confiances par caractère: PaddleOCR rend un score par LIGNE, pas par caractère.
On le réplique sur chaque caractère (approximation) -> le vote pondéré dégénère de
fait en vote majoritaire. Pour de vraies confiances par caractère il faut exporter
le modèle reco en ONNX et lire les logits CTC (cf. RISQUES R2 / ROADMAP Jalon 2).
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np

from anpr_poc.types import Read

_NON_ALNUM = re.compile(r"[^A-Z0-9]")


class PaddleReco:
    def __init__(self, lang: str = "en") -> None:
        from paddleocr import PaddleOCR

        # doc_unwarping/orientation OFF: sinon les coords reviennent dans l'espace
        # dé-warpé (cf. PROBLEMATIQUES P9). Reco latin (majuscules + chiffres).
        self._ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            lang=lang,
        )

    def read(self, crop: np.ndarray, frame_idx: int = -1, country: str | None = None) -> Read | None:
        """OCR un crop plaque déjà redressé/strippé. Retourne None si vide."""
        result = self._ocr.predict(crop)
        text, line_score = self._extract(result)
        canonical = self._normalize(text)
        if not canonical:
            return None
        # score-ligne répliqué par caractère (voir NOTE module)
        char_confidences = tuple(line_score for _ in canonical)
        return Read(
            text=canonical,
            char_confidences=char_confidences,
            country=country,
            frame_idx=frame_idx,
        )

    @staticmethod
    def _extract(result: Any) -> tuple[str, float]:
        """Extrait (meilleur texte, score) de la sortie predict() 3.x.

        predict() rend une liste de dict avec 'rec_texts' et 'rec_scores'. On prend
        la ligne au meilleur score (souvent une seule sur un crop plaque).
        """
        try:
            r = result[0]
            texts = r.get("rec_texts") or []
            scores = r.get("rec_scores") or []
        except (IndexError, KeyError, TypeError, AttributeError):
            return "", 0.0
        if not texts:
            return "", 0.0
        best = max(range(len(texts)), key=lambda i: float(scores[i]) if i < len(scores) else 0.0)
        return str(texts[best]), float(scores[best]) if best < len(scores) else 0.0

    @staticmethod
    def _normalize(text: str) -> str:
        """Forme canonique: majuscules, alphanumérique seul (retire - · . espaces)."""
        return _NON_ALNUM.sub("", text.upper())
