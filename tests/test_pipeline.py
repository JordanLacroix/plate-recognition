"""Test d'intégration: câblage complet frame -> événement de pipeline.py.

Détecteur / tracker / OCR / source factices (numpy pur, aucun modèle). Vérifie que
l'orchestration relie bien détection -> tracking -> OCR -> confirmation -> sink.
Nécessite opencv (importé par ocr.preprocess). Le cœur pur est dans test_confirm.py.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from anpr_poc.config import load_config
from anpr_poc.pipeline import Pipeline
from anpr_poc.types import BBox, Detection, Event, Read

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class FakeDetector:
    def detect(self, frame: np.ndarray, conf_min: float) -> list[Detection]:
        return [Detection(BBox(10, 10, 190, 90), 0.99)]


class FakeTracker:
    """Renvoie toujours le même tracker_id, dans la ROI, sans franchissement."""

    def update(self, detections):
        return [(1, BBox(10, 10, 190, 90), False)]

    def in_roi(self, bbox: BBox) -> bool:
        return True


class FakeOCR:
    def __init__(self, plate: str) -> None:
        self.plate = plate

    def read(self, crop, frame_idx: int = -1, country=None) -> Read:
        return Read(text=self.plate, char_confidences=tuple(0.95 for _ in self.plate), country="FR")


class ListSink:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        self.events.append(event)


class FakeSource:
    def __init__(self, n_frames: int) -> None:
        self._n = n_frames

    @property
    def fps(self) -> float:
        return 25.0

    def frames(self):
        for i in range(self._n):
            yield i, np.zeros((100, 200, 3), dtype=np.uint8)


def _pipeline(plate: str, sink: ListSink) -> Pipeline:
    cfg = load_config(CONFIG_DIR)
    return Pipeline(
        config=cfg,
        detector=FakeDetector(),
        tracker=FakeTracker(),
        ocr=FakeOCR(plate),
        sink=sink,
    )


def test_pipeline_emits_one_event_after_consensus() -> None:
    sink = ListSink()
    events = _pipeline("AB123CD", sink).run(FakeSource(n_frames=5))
    # k_consensus=3 par défaut -> exactement 1 événement malgré 5 frames
    assert len(events) == 1
    assert events[0].plate == "AB123CD"
    assert events[0].tracker_id == 1
    assert sink.events == events  # le sink a bien reçu l'événement


def test_pipeline_no_event_when_below_consensus() -> None:
    sink = ListSink()
    events = _pipeline("AB123CD", sink).run(FakeSource(n_frames=2))  # < k_consensus
    assert events == []
    assert sink.events == []


def test_pipeline_rejects_invalid_format() -> None:
    sink = ListSink()
    events = _pipeline("!!!", sink).run(FakeSource(n_frames=5))  # format invalide
    assert events == []
