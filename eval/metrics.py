"""Métriques eval: CER (Levenshtein normalisé) + faux positifs/négatifs événement."""

from __future__ import annotations

from dataclasses import dataclass


def levenshtein(a: str, b: str) -> int:
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
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def cer(pred: str, truth: str) -> float:
    """Character Error Rate normalisé par longueur vérité."""
    if not truth:
        return 0.0 if not pred else 1.0
    return levenshtein(pred, truth) / len(truth)


@dataclass
class ClipResult:
    clip: str
    truth: str
    pred: str | None  # None = aucun événement émis (faux négatif si truth attendu)

    @property
    def emitted(self) -> bool:
        return self.pred is not None

    @property
    def correct(self) -> bool:
        return self.pred == self.truth

    @property
    def cer(self) -> float:
        return cer(self.pred or "", self.truth)


@dataclass
class EvalReport:
    results: list[ClipResult]

    @property
    def mean_cer(self) -> float:
        r = [x.cer for x in self.results if x.emitted]
        return sum(r) / len(r) if r else 1.0

    @property
    def exact_match_rate(self) -> float:
        return sum(x.correct for x in self.results) / len(self.results) if self.results else 0.0

    @property
    def false_negative_rate(self) -> float:
        """Clips avec vérité mais aucun événement émis."""
        expected = [x for x in self.results if x.truth]
        if not expected:
            return 0.0
        return sum(not x.emitted for x in expected) / len(expected)

    @property
    def false_positive_rate(self) -> float:
        """Événements émis mais faux (plaque ≠ vérité)."""
        emitted = [x for x in self.results if x.emitted]
        if not emitted:
            return 0.0
        return sum(not x.correct for x in emitted) / len(emitted)

    def summary(self) -> str:
        return (
            f"clips={len(self.results)} "
            f"exact={self.exact_match_rate:.2%} "
            f"CER={self.mean_cer:.3f} "
            f"FP={self.false_positive_rate:.2%} "
            f"FN={self.false_negative_rate:.2%}"
        )
