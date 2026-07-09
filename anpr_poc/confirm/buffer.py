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
        dedup_edit_distance: int = 1,
        require_crossing: bool = False,
    ) -> None:
        self._validate = validate_format
        self._conf_min = conf_min
        self._k = k_consensus
        self._default_country = default_country
        self._dedup_window = dedup_window_sec
        self._dedup_edit = dedup_edit_distance
        self._require_crossing = require_crossing
        self._buffer: dict[int, list[Read]] = defaultdict(list)
        self._emitted: set[int] = set()
        # anti-doublon inter-tracks: (plaque, timestamp de dernière émission)
        self._emitted_plates: list[tuple[str, float]] = []
        # tracks ayant franchi la ligne (pour le gate optionnel de franchissement)
        self._crossed: set[int] = set()

    def add(
        self,
        tracker_id: int,
        read: Read,
        timestamp: float,
        snapshot_path: str | None = None,
        crossed: bool = False,
    ) -> Event | None:
        """Ajoute une lecture. Retourne un Event si le consensus vient d'être atteint."""
        if crossed:
            self._crossed.add(tracker_id)
        if tracker_id in self._emitted:
            return None

        self._buffer[tracker_id].append(read)

        # 1. gate qualité
        reads = [r for r in self._buffer[tracker_id] if r.min_conf >= self._conf_min]
        # 2. validation format (par pays de la lecture, sinon défaut)
        reads = [r for r in reads if self._validate(r.text, r.country or self._default_country)]
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

        # 5. gate franchissement de ligne (optionnel)
        if self._require_crossing and tracker_id not in self._crossed:
            return None

        # 6. anti-doublon inter-tracks: même plaque (à distance d'édition près) déjà
        #    émise récemment -> fragmentation ByteTrack (1 camion, plusieurs tracker_id).
        if self._is_recent_duplicate(candidate, timestamp):
            self._emitted.add(tracker_id)  # stoppe ce track: doublon
            self._emitted_plates.append((candidate, timestamp))  # étend la fenêtre
            return None

        # émission unique
        self._emitted.add(tracker_id)
        self._emitted_plates.append((candidate, timestamp))
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

    def retain(self, active_ids: set[int]) -> None:
        """Évite la fuite mémoire sur flux long: purge les buffers des tracks disparus.

        À appeler à chaque frame avec les tracker_id encore actifs. Un track qui
        n'émet jamais (mauvaise lecture, faux positif) verrait sinon son buffer
        grossir à l'infini. Ne touche pas l'ensemble `_emitted` (garde le debounce).
        """
        for tid in list(self._buffer):
            if tid not in active_ids:
                del self._buffer[tid]

    def _is_recent_duplicate(self, candidate: str, timestamp: float) -> bool:
        """Vrai si une plaque à distance d'édition ≤ seuil a été émise dans la fenêtre."""
        for plate, ts in self._emitted_plates:
            if (timestamp - ts) <= self._dedup_window and _edit_distance(
                candidate, plate
            ) <= self._dedup_edit:
                return True
        return False

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


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein. Court-circuit si l'écart de longueur dépasse déjà le besoin."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
