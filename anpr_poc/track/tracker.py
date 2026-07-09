"""Wrapper supervision: ByteTrack pour un tracker_id/camion + LineZone franchissement.

Un tracker_id agrège plusieurs lectures de la MÊME plaque -> base du vote consensus.
"""

from __future__ import annotations

import numpy as np

from anpr_poc.config import Roi
from anpr_poc.types import BBox, Detection


class PlateTracker:
    def __init__(self, roi: Roi, frame_rate: int = 30) -> None:
        import supervision as sv

        self._sv = sv
        self._tracker = sv.ByteTrack(frame_rate=frame_rate)
        self._line = sv.LineZone(
            start=sv.Point(*roi.line_start),
            end=sv.Point(*roi.line_end),
        )
        self._polygon = np.array(roi.polygon, dtype=np.int32)

    def update(self, detections: list[Detection]) -> list[tuple[int, BBox, bool]]:
        """Associe détections -> tracks. Retourne (tracker_id, bbox, crossed_line)."""
        sv = self._sv
        if detections:
            xyxy = np.array([d.bbox.xyxy for d in detections], dtype=np.float32)
            conf = np.array([d.confidence for d in detections], dtype=np.float32)
            det = sv.Detections(xyxy=xyxy, confidence=conf)
        else:
            det = sv.Detections.empty()

        tracked = self._tracker.update_with_detections(det)
        crossed_in, crossed_out = self._line.trigger(tracked)

        out: list[tuple[int, BBox, bool]] = []
        if tracked.tracker_id is None:
            return out
        for i, tid in enumerate(tracked.tracker_id):
            x1, y1, x2, y2 = tracked.xyxy[i]
            crossed = bool(crossed_in[i] or crossed_out[i])
            out.append((int(tid), BBox(float(x1), float(y1), float(x2), float(y2)), crossed))
        return out

    def in_roi(self, bbox: BBox) -> bool:
        """Centre bbox dans le polygone ROI."""
        import cv2

        cx = (bbox.x1 + bbox.x2) / 2
        cy = (bbox.y1 + bbox.y2) / 2
        return bool(cv2.pointPolygonTest(self._polygon, (cx, cy), False) >= 0)
