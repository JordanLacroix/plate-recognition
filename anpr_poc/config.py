"""Chargement config. Injectée dans le pipeline; aucun seuil en dur ailleurs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class Thresholds(BaseModel):
    conf_min: float = Field(0.6, description="Gate qualité: min char confidence par lecture.")
    k_consensus: int = Field(3, description="Lectures concordantes requises avant émission.")
    det_conf_min: float = Field(0.4, description="Seuil confiance détecteur plaque.")
    euroband_strip_frac: float = Field(0.11, description="Fraction gauche croppée (euroband).")
    dedup_window_sec: float = Field(
        5.0,
        description="Fenêtre anti-doublon: même plaque ré-émise sur un autre tracker_id là-dedans -> supprimée.",
    )
    dedup_edit_distance: int = Field(
        1,
        description="Distance d'édition max pour considérer 2 plaques comme doublon (0 = chaîne exacte).",
    )
    require_line_crossing: bool = Field(
        False, description="Si True, n'émet que pour un track ayant franchi la ligne (LineZone)."
    )


class Roi(BaseModel):
    """Zone d'intérêt + ligne de franchissement (coords pixel)."""

    polygon: list[tuple[int, int]]
    line_start: tuple[int, int]
    line_end: tuple[int, int]

    @field_validator("polygon")
    @classmethod
    def _polygon_min_points(cls, v: list[tuple[int, int]]) -> list[tuple[int, int]]:
        if len(v) < 3:
            raise ValueError(f"ROI polygon: au moins 3 points requis, reçu {len(v)}")
        return v

    @model_validator(mode="after")
    def _line_not_degenerate(self) -> Roi:
        if self.line_start == self.line_end:
            raise ValueError("ROI: line_start et line_end identiques (ligne dégénérée)")
        return self


# Défauts miroir de config/formats.yaml. Les plaques sont CANONIQUES: alphanumérique
# uniquement (séparateurs -, ·, espaces retirés au normalize). Les regex n'ont donc
# PAS de séparateur -> robuste au bruit OCR sur les tirets. Voir ocr.paddle_reco._normalize.
_DEFAULT_REGEX_BY_COUNTRY: dict[str, str] = {
    "FR": r"^[A-Z]{2}\d{3}[A-Z]{2}$",  # SIV: AA123AA (affiché AA-123-AA)
    "DE": r"^[A-Z]{1,3}[A-Z]{1,2}\d{1,4}$",
    "ES": r"^\d{4}[A-Z]{3}$",
    "IT": r"^[A-Z]{2}\d{3}[A-Z]{2}$",
    "NL": r"^[A-Z0-9]{6}$",
    "BE": r"^[12][A-Z]{3}\d{3}$",
    "PL": r"^[A-Z]{2,3}[A-Z0-9]{4,5}$",
    "GB": r"^[A-Z]{2}\d{2}[A-Z]{3}$",  # style courant 2001+: AA00AAA
}


class FormatsConfig(BaseModel):
    default_country: str = "FR"
    # Fallback structurel souple (plaques canoniques alphanumériques, 5 à 10 chars).
    fallback_regex: str = r"^[A-Z0-9]{5,10}$"
    regex_by_country: dict[str, str] = Field(
        default_factory=lambda: dict(_DEFAULT_REGEX_BY_COUNTRY)
    )
    # True: pays connu (regex définie) -> STRICT, pas de fallback. Fallback seulement
    # pour pays inconnu. Rejette les lectures partielles type "GX-521-E".
    strict_when_known: bool = True


class AppConfig(BaseModel):
    thresholds: Thresholds
    roi: Roi
    formats: FormatsConfig
    # Homographie 3x3 pré-calibrée (vue fixe). None = pas de redressement.
    homography: list[list[float]] | None = None
    # Snapshots de preuve. dir None -> désactivé. Fond flouté pour RGPD.
    snapshot_dir: str | None = None
    snapshot_blur_background: bool = True

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def _homography_valid(self) -> AppConfig:
        """Fail-fast: homographie doit être 3x3 et inversible (det != 0)."""
        if self.homography is None:
            return self
        m = np.asarray(self.homography, dtype=np.float64)
        if m.shape != (3, 3):
            raise ValueError(f"homographie: matrice 3x3 attendue, reçu {m.shape}")
        if abs(float(np.linalg.det(m))) < 1e-9:
            raise ValueError("homographie: matrice singulière (non inversible)")
        return self

    @property
    def homography_matrix(self) -> np.ndarray | None:
        if self.homography is None:
            return None
        return np.asarray(self.homography, dtype=np.float64)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def load_config(config_dir: str | Path) -> AppConfig:
    """Assemble AppConfig depuis config/. Fichiers manquants -> défauts."""
    d = Path(config_dir)
    thresholds = (
        Thresholds(**_load_yaml(d / "thresholds.yaml"))
        if (d / "thresholds.yaml").exists()
        else Thresholds()
    )
    formats = (
        FormatsConfig(**_load_yaml(d / "formats.yaml"))
        if (d / "formats.yaml").exists()
        else FormatsConfig()
    )
    roi = Roi(**_load_json(d / "roi.json"))
    homography = None
    hpath = d / "homographie.json"
    if hpath.exists():
        homography = _load_json(hpath).get("matrix")
    return AppConfig(thresholds=thresholds, roi=roi, formats=formats, homography=homography)
