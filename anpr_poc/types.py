"""Types partagés du pipeline. Sans état global; passés par valeur entre modules."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BBox:
    """Boîte plaque en pixels image, coin haut-gauche + coin bas-droite."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def xyxy(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)


@dataclass(frozen=True)
class Detection:
    """Une détection plaque sur une frame (avant tracking)."""

    bbox: BBox
    confidence: float


@dataclass(frozen=True)
class Read:
    """Une lecture OCR d'une plaque pour un tracker_id donné, sur une frame."""

    text: str
    char_confidences: tuple[float, ...]
    country: str | None = None
    frame_idx: int = -1

    @property
    def min_conf(self) -> float:
        return min(self.char_confidences) if self.char_confidences else 0.0


@dataclass(frozen=True)
class Event:
    """Sortie stable: 1 par tracker_id (camion)."""

    plate: str
    tracker_id: int
    timestamp: float
    confidence: float
    country: str | None = None
    snapshot_path: str | None = None


@dataclass
class TrackedRead:
    """Lecture rattachée à un tracker après association détection-track."""

    tracker_id: int
    read: Read
    bbox: BBox
    crossed_line: bool = False
    extra: dict[str, object] = field(default_factory=dict)
