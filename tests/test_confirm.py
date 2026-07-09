"""Tests unitaires du coeur confirmation (aucune dépendance modèle).

Plaques CANONIQUES (alphanumérique, sans séparateur) — cf. ocr.paddle_reco._normalize.
"""

from __future__ import annotations

from anpr_poc.config import FormatsConfig
from anpr_poc.confirm.buffer import ConfirmBuffer
from anpr_poc.confirm.consensus import per_char_majority_vote
from anpr_poc.confirm.validate import make_validator
from anpr_poc.types import Read


def _read(text: str, conf: float = 0.9, country: str = "FR") -> Read:
    return Read(text=text, char_confidences=tuple(conf for _ in text), country=country)


# --- vote ---


def test_vote_picks_majority_char() -> None:
    reads = [_read("AB123CD"), _read("AB123CD"), _read("AB123CE")]
    assert per_char_majority_vote(reads) == "AB123CD"


def test_vote_filters_to_majority_length() -> None:
    reads = [_read("AB123CD"), _read("AB123CD"), _read("AB123CDX")]
    assert per_char_majority_vote(reads) == "AB123CD"


def test_vote_weights_by_confidence() -> None:
    # 2 lectures basse conf 'X' vs 1 haute conf 'Y' à la même position
    reads = [_read("AAX", 0.3), _read("AAX", 0.3), _read("AAY", 0.99)]
    assert per_char_majority_vote(reads) == "AAY"


# --- validation format ---


def test_validator_fr_strict() -> None:
    v = make_validator(FormatsConfig())  # strict_when_known=True par défaut
    assert v("AB123CD", "FR")  # SIV canonique OK
    assert not v("AB12", "FR")  # trop court
    assert not v("ABC123", "FR")  # pays connu -> strict, PAS de fallback
    assert not v("AB123C", "FR")  # lecture partielle rejetée


def test_validator_fallback_for_unknown_country() -> None:
    v = make_validator(FormatsConfig())
    assert v("XYZ99", "ZZ")  # pays sans regex -> fallback souple
    assert not v("AB", "ZZ")  # trop court même en fallback


def test_validator_permissive_mode() -> None:
    v = make_validator(FormatsConfig(strict_when_known=False))
    assert v("ABC123", "FR")  # fallback réactivé pour pays connu


# --- dédup inter-tracks ---


def test_dedup_suppresses_same_plate_across_tracks() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=2, dedup_window_sec=5.0)
    buf.add(1, _read("AB123CD"), timestamp=1.0)
    assert buf.add(1, _read("AB123CD"), timestamp=1.1) is not None
    # track 2 = même plaque, camion fragmenté, dans la fenêtre -> supprimé
    buf.add(2, _read("AB123CD"), timestamp=2.0)
    assert buf.add(2, _read("AB123CD"), timestamp=2.1) is None


def test_dedup_allows_same_plate_after_window() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=2, dedup_window_sec=5.0)
    buf.add(1, _read("AB123CD"), timestamp=1.0)
    assert buf.add(1, _read("AB123CD"), timestamp=1.1) is not None
    buf.add(2, _read("AB123CD"), timestamp=10.0)
    assert buf.add(2, _read("AB123CD"), timestamp=10.1) is not None


def test_dedup_edit_distance_catches_near_miss() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=2, dedup_window_sec=5.0, dedup_edit_distance=1)
    buf.add(1, _read("GX521EW"), timestamp=1.0)
    assert buf.add(1, _read("GX521EW"), timestamp=1.1) is not None
    # track 2 lit GX521EV (1 caractère de différence) -> même camion -> supprimé
    buf.add(2, _read("GX521EV"), timestamp=2.0)
    assert buf.add(2, _read("GX521EV"), timestamp=2.1) is None


def test_dedup_exact_only_when_distance_zero() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=2, dedup_window_sec=5.0, dedup_edit_distance=0)
    buf.add(1, _read("GX521EW"), timestamp=1.0)
    assert buf.add(1, _read("GX521EW"), timestamp=1.1) is not None
    # distance 1 mais seuil 0 -> plaque distincte, émise
    buf.add(2, _read("GX521EV"), timestamp=2.0)
    assert buf.add(2, _read("GX521EV"), timestamp=2.1) is not None


# --- émission / gate / debounce ---


def test_buffer_emits_once_on_consensus() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=3)
    ev = None
    for _ in range(3):
        ev = buf.add(1, _read("AB123CD"), timestamp=0.0)
    assert ev is not None
    assert ev.plate == "AB123CD"
    assert buf.add(1, _read("AB123CD"), timestamp=0.0) is None  # déjà émis


def test_buffer_gate_rejects_low_confidence() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=3)
    for _ in range(5):
        assert buf.add(1, _read("AB123CD", conf=0.4), timestamp=0.0) is None


def test_buffer_waits_for_k_consensus() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=3)
    assert buf.add(1, _read("AB123CD"), timestamp=0.0) is None
    assert buf.add(1, _read("AB123CD"), timestamp=0.0) is None
    assert buf.add(1, _read("AB123CD"), timestamp=0.0) is not None


# --- gate franchissement de ligne ---


def test_require_crossing_blocks_until_crossed() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=2, require_crossing=True)
    # consensus atteint mais pas de franchissement -> pas d'émission
    buf.add(1, _read("AB123CD"), timestamp=0.0, crossed=False)
    assert buf.add(1, _read("AB123CD"), timestamp=0.1, crossed=False) is None
    # franchissement -> émission
    assert buf.add(1, _read("AB123CD"), timestamp=0.2, crossed=True) is not None


# --- éviction mémoire ---


def test_retain_evicts_inactive_tracks() -> None:
    v = make_validator(FormatsConfig())
    buf = ConfirmBuffer(v, conf_min=0.6, k_consensus=3)
    buf.add(1, _read("AB123CD"), timestamp=0.0)  # sous le K, buffer conservé
    buf.add(2, _read("XY999ZZ"), timestamp=0.0)
    assert 1 in buf._buffer and 2 in buf._buffer
    buf.retain({1})  # track 2 disparu
    assert 1 in buf._buffer and 2 not in buf._buffer
