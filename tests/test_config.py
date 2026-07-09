"""Validation fail-fast de la config (pydantic). Pas de modèle requis."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anpr_poc.config import AppConfig, FormatsConfig, Roi, Thresholds

_VALID_ROI = {"polygon": [(0, 0), (1, 0), (1, 1)], "line_start": (0, 0), "line_end": (1, 1)}


def _appcfg(**kw: object) -> AppConfig:
    base: dict[str, object] = {
        "thresholds": Thresholds(),
        "roi": Roi(**_VALID_ROI),
        "formats": FormatsConfig(),
    }
    base.update(kw)
    return AppConfig(**base)  # type: ignore[arg-type]


def test_roi_polygon_needs_three_points() -> None:
    with pytest.raises(ValidationError):
        Roi(polygon=[(0, 0), (1, 1)], line_start=(0, 0), line_end=(1, 1))


def test_roi_line_not_degenerate() -> None:
    with pytest.raises(ValidationError):
        Roi(polygon=[(0, 0), (1, 0), (1, 1)], line_start=(5, 5), line_end=(5, 5))


def test_homography_must_be_3x3() -> None:
    with pytest.raises(ValidationError):
        _appcfg(homography=[[1, 0], [0, 1]])


def test_homography_singular_rejected() -> None:
    with pytest.raises(ValidationError):
        _appcfg(homography=[[1, 0, 0], [2, 0, 0], [0, 0, 1]])  # lignes dépendantes -> det 0


def test_valid_identity_homography_ok() -> None:
    cfg = _appcfg(homography=[[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    assert cfg.homography_matrix is not None
    assert cfg.homography_matrix.shape == (3, 3)
