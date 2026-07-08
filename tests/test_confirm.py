"""Tests unitaires du coeur confirmation (aucune dépendance modèle)."""

from __future__ import annotations

from anpr_poc.config import FormatsConfig
from anpr_poc.confirm.buffer import ConfirmBuffer
from anpr_poc.confirm.consensus import per_char_majority_vote
from anpr_poc.confirm.validate import make_validator
from anpr_poc.types import Read


def _read(text: str, conf: float = 0.9, country: str = "FR") -> Read:
    return Read(text=text, char_confidences=tuple(conf for _ in text), country=country)


def test_vote_picks_majority_char() -> None:
    reads = [_read("AB-123-CD"), _read("AB-123-CD"), _read("AB-123-CE")]
    assert per_char_majority_vote(reads) == "AB-123-CD"


def test_vote_filters_to_majority_length() -> None:
    reads = [_read("AB123CD"), _read("AB123CD"), _read("AB123CDX")]
    assert per_char_majority_vote(reads) == "AB123CD"


def test_vote_weights_by_confidence() -> None:
    # 2 lectures basse conf 'X' vs 1 haute conf 'Y' à la même position
    reads = [_read("AAX", 0.3), _read("AAX", 0.3), _read("AAY", 0.99)]
    assert per_char_majority_vote(reads) == "AAY"


def test_validator_fr_strict() -> None:
    v = make_validator(FormatsConfig())        # strict_when_known=True par défaut
    assert v("AB-123-CD", "FR")                # SIV strict OK
    assert not v("AB12", "FR")                 # trop court
    assert not v("ABC123", "FR")               # pays connu -> strict, PAS de fallback
    assert not v("AB-123-C", "FR")             # lecture partielle rejetée (fix 2)


def test_validator_fallback_for_unknown_country() -> None:
    v = make_validator(FormatsConfig())
    # pays sans regex -> fallback souple s'applique
    assert v("XYZ99", "ZZ")
    assert not v("AB", "ZZ")                    # trop court même en fallback


def test_validator_permissive_mode() -> None:
    v = make_validator(FormatsConfig(strict_when_known=False))
    assert v("ABC123", "FR")                    # fallback réactivé pour pays connu


def test_dedup_suppresses_same_plate_across_tracks() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=2, dedup_window_sec=5.0)
    # track 1 émet la plaque
    buf.add(1, _read("AB-123-CD"), timestamp=1.0)
    ev1 = buf.add(1, _read("AB-123-CD"), timestamp=1.1)
    assert ev1 is not None
    # track 2 = même plaque, même camion fragmenté, dans la fenêtre -> supprimé
    buf.add(2, _read("AB-123-CD"), timestamp=2.0)
    ev2 = buf.add(2, _read("AB-123-CD"), timestamp=2.1)
    assert ev2 is None


def test_dedup_allows_same_plate_after_window() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=2, dedup_window_sec=5.0)
    buf.add(1, _read("AB-123-CD"), timestamp=1.0)
    assert buf.add(1, _read("AB-123-CD"), timestamp=1.1) is not None
    # hors fenêtre (>5s plus tard) -> vrai second passage, ré-émis
    buf.add(2, _read("AB-123-CD"), timestamp=10.0)
    assert buf.add(2, _read("AB-123-CD"), timestamp=10.1) is not None


def test_buffer_emits_once_on_consensus() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=3)
    ev = None
    for _ in range(3):
        ev = buf.add(1, _read("AB-123-CD"), timestamp=0.0)
    assert ev is not None
    assert ev.plate == "AB-123-CD"
    # 4e lecture: déjà émis -> None
    assert buf.add(1, _read("AB-123-CD"), timestamp=0.0) is None


def test_buffer_gate_rejects_low_confidence() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=3)
    for _ in range(5):
        ev = buf.add(1, _read("AB-123-CD", conf=0.4), timestamp=0.0)
        assert ev is None  # jamais émis: sous le gate


def test_buffer_waits_for_k_consensus() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=3)
    assert buf.add(1, _read("AB-123-CD"), timestamp=0.0) is None
    assert buf.add(1, _read("AB-123-CD"), timestamp=0.0) is None
    assert buf.add(1, _read("AB-123-CD"), timestamp=0.0) is not None
