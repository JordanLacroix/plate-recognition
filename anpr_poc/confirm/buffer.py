"""Buffer par tracker_id: accumule lectures, gate, valide, vote, émet 1x (debounce).

Coeur du POC — 90 % des bugs vivent ici. Sans état global: instancié par run.
"""

from __future__ import annotations

from collections import defaultdict

from anpr_poc.confirm.consensus import per_char_majority_vote
from anpr_poc.confirm.validate import Validator
from anpr_poc.types import Event, Read


class ConfirmBuffer:
    def __init__(
        self,
        validate_format: Validator,
        conf_min: float,
        k_consensus: int,
        default_country: str = "FR",
        dedup_window_sec: float = 5.0,
    ) -> None:
        self._validate = validate_format
        self._conf_min = conf_min
        self._k = k_consensus
        self._default_country = default_country
        self._dedup_window = dedup_window_sec
        self._buffer: dict[int, list[Read]] = defaultdict(list)
        self._emitted: set[int] = set()
        # anti-doublon inter-tracks: plaque -> timestamp de dernière émission
        self._emitted_plates: dict[str, float] = {}

    def add(
        self,
        tracker_id: int,
        read: Read,
        timestamp: float,
        snapshot_path: str | None = None,
    ) -> Event | None:
        """Ajoute une lecture. Retourne un Event si le consensus vient d'être atteint."""
        if tracker_id in self._emitted:
            return None

        self._buffer[tracker_id].append(read)

        # 1. gate qualité
        reads = [r for r in self._buffer[tracker_id] if r.min_conf >= self._conf_min]
        # 2. validation format (par pays de la lecture, sinon défaut)
        reads = [
            r for r in reads if self._validate(r.text, r.country or self._default_country)
        ]
        if not reads:
            return None

        # 3. consensus: vote char-par-char sur longueur majoritaire
        candidate = per_char_majority_vote(reads)
        if candidate is None:
            return None

        # 4. debounce: K lectures concordant avec le candidat
        concordant = sum(1 for r in reads if r.text == candidate)
        if concordant < self._k:
            return None

        # 5. anti-doublon inter-tracks: même plaque déjà émise récemment
        #    (fragmentation ByteTrack -> 1 camion, plusieurs tracker_id).
        prev_ts = self._emitted_plates.get(candidate)
        if prev_ts is not None and (timestamp - prev_ts) <= self._dedup_window:
            self._emitted.add(tracker_id)  # stoppe ce track: doublon
            self._emitted_plates[candidate] = timestamp  # étend la fenêtre
            return None

        # émission unique
        self._emitted.add(tracker_id)
        self._emitted_plates[candidate] = timestamp
        conf = self._mean_conf(reads, candidate)
        country = self._majority_country(reads)
        return Event(
            plate=candidate,
            tracker_id=tracker_id,
            timestamp=timestamp,
            confidence=conf,
            country=country,
            snapshot_path=snapshot_path,
        )

    def already_emitted(self, tracker_id: int) -> bool:
        return tracker_id in self._emitted

    def flush(self, tracker_id: int) -> None:
        """Libère le buffer d'un track sorti de scène (mémoire)."""
        self._buffer.pop(tracker_id, None)

    @staticmethod
    def _mean_conf(reads: list[Read], candidate: str) -> float:
        matching = [r for r in reads if r.text == candidate]
        if not matching:
            return 0.0
        vals = [c for r in matching for c in r.char_confidences]
        return sum(vals) / len(vals) if vals else 0.0

    def _majority_country(self, reads: list[Read]) -> str | None:
        from collections import Counter

        countries = [r.country for r in reads if r.country]
        if not countries:
            return None
        return Counter(countries).most_common(1)[0][0]
