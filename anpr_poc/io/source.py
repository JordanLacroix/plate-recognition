"""Source vidéo: fichier ou RTSP. Itère (frame_idx, frame BGR)."""

from __future__ import annotations

from collections.abc import Iterator

import cv2
import numpy as np


class VideoSource:
    def __init__(self, uri: str) -> None:
        self.uri = uri

    def __enter__(self) -> VideoSource:
        self._cap = cv2.VideoCapture(self.uri)
        if not self._cap.isOpened():
            raise RuntimeError(f"Ouverture source échouée: {self.uri}")
        return self

    def __exit__(self, *exc: object) -> None:
        self._cap.release()

    @property
    def fps(self) -> float:
        return self._cap.get(cv2.CAP_PROP_FPS) or 30.0

    def frames(self) -> Iterator[tuple[int, np.ndarray]]:
        idx = 0
        while True:
            ok, frame = self._cap.read()
            if not ok:
                break
            yield idx, frame
            idx += 1
