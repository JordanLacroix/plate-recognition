"""Détecteur factice + fabrique load_detector (backend stub). Pur numpy."""

from __future__ import annotations

import numpy as np
import pytest

from anpr_poc.detect.base import load_detector
from anpr_poc.detect.stub import StubDetector
from anpr_poc.types import Detection


def test_stub_returns_centered_box() -> None:
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    dets = StubDetector(frac=0.5).detect(frame, conf_min=0.4)
    assert len(dets) == 1
    d = dets[0]
    assert isinstance(d, Detection)
    # boîte centrée couvrant 50 % -> x de 50 à 150, y de 25 à 75
    assert d.bbox.x1 == 50 and d.bbox.x2 == 150
    assert d.bbox.y1 == 25 and d.bbox.y2 == 75


def test_stub_explicit_boxes() -> None:
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    dets = StubDetector(boxes=[(1, 2, 3, 4)]).detect(frame, conf_min=0.4)
    assert dets[0].bbox.xyxy == (1.0, 2.0, 3.0, 4.0)


def test_stub_respects_conf_min() -> None:
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    assert StubDetector(confidence=0.3).detect(frame, conf_min=0.5) == []


def test_load_detector_stub() -> None:
    assert isinstance(load_detector("ignored", backend="stub"), StubDetector)


def test_load_detector_unknown_backend() -> None:
    with pytest.raises(ValueError):
        load_detector("x.weights", backend="banana")


def test_load_detector_tensorrt_not_on_mac() -> None:
    with pytest.raises(NotImplementedError):
        load_detector("model.engine", backend="tensorrt")
