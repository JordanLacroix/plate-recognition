"""Snapshot de preuve: écriture + flou du fond (RGPD). Nécessite opencv."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from anpr_poc.io.snapshot import SnapshotWriter
from anpr_poc.types import BBox, Event


def test_snapshot_written(tmp_path: Path) -> None:
    frame = np.full((100, 200, 3), 127, dtype=np.uint8)
    event = Event(plate="AB123CD", tracker_id=7, timestamp=1.5, confidence=0.9)
    path = SnapshotWriter(tmp_path, blur_background=True).save(frame, BBox(50, 40, 150, 60), event)
    assert Path(path).exists()
    assert "AB123CD" in Path(path).name
    assert cv2.imread(path).shape == frame.shape


def test_snapshot_blur_keeps_plate_sharp(tmp_path: Path) -> None:
    # fond bruité, plaque = zone nette contrastée
    rng = np.zeros((100, 200, 3), dtype=np.uint8)
    rng[:, :] = 200
    plate = BBox(80, 45, 120, 55)
    frame = rng.copy()
    frame[45:55, 80:120] = 0  # motif net dans la plaque
    event = Event(plate="ZZ111ZZ", tracker_id=1, timestamp=0.0, confidence=0.9)
    path = SnapshotWriter(tmp_path, blur_background=True).save(frame, plate, event)
    out = cv2.imread(path)
    # JPEG lossy -> pas d'égalité exacte, mais la plaque reste nette/sombre (préservée)
    # tandis que le fond reste clair (flouté mais toujours ~200).
    assert out[46:54, 82:118].mean() < 60  # plaque préservée (motif sombre)
    assert out[10:20, 10:40].mean() > 150  # fond conservé/flouté, pas noirci
