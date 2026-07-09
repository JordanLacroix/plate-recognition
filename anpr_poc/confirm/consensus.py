"""Vote caractère par caractère sur les lectures alignées par longueur majoritaire."""

from __future__ import annotations

from collections import Counter, defaultdict

from anpr_poc.types import Read


def majority_length(reads: list[Read]) -> int:
    """Longueur de texte la plus fréquente parmi les lectures."""
    counts = Counter(len(r.text) for r in reads)
    return counts.most_common(1)[0][0]


def per_char_majority_vote(reads: list[Read]) -> str | None:
    """Consensus: filtre à la longueur majoritaire, puis vote pondéré par confiance
    à chaque position. Retourne None si aucune lecture.

    Pondération: somme des char_confidences par candidat -> robuste aux lectures
    basse confiance sans les jeter d'office.
    """
    if not reads:
        return None
    target_len = majority_length(reads)
    aligned = [r for r in reads if len(r.text) == target_len]
    if not aligned:
        return None

    out: list[str] = []
    for pos in range(target_len):
        weights: dict[str, float] = defaultdict(float)
        for r in aligned:
            ch = r.text[pos]
            conf = r.char_confidences[pos] if pos < len(r.char_confidences) else 1.0
            weights[ch] += conf
        # caractère au poids max (départage stable par ordre alphabétique)
        out.append(max(sorted(weights), key=lambda c: weights[c]))
    return "".join(out)
