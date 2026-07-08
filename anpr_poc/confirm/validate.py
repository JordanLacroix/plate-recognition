"""Validation format = dict pays -> regex. Pluggable, PAS un regex UE unique."""

from __future__ import annotations

import re
from typing import Callable

from anpr_poc.config import FormatsConfig

Validator = Callable[[str, str | None], bool]


def make_validator(formats: FormatsConfig) -> Validator:
    """Construit validate_format(text, country) -> bool depuis la config.

    strict_when_known=True (défaut): un pays avec regex définie est validé STRICT,
    sans fallback -> rejette les lectures partielles (ex. "GX-521-E" pour FR). Le
    fallback souple ne sert que pour un pays inconnu.

    strict_when_known=False: comportement permissif d'origine (regex pays OU fallback).
    """
    compiled = {c: re.compile(rx) for c, rx in formats.regex_by_country.items()}
    fallback = re.compile(formats.fallback_regex)
    default = formats.default_country
    strict = formats.strict_when_known

    def validate_format(text: str, country: str | None = None) -> bool:
        c = country or default
        pattern = compiled.get(c)
        if pattern is not None:
            if pattern.match(text):
                return True
            if strict:
                return False  # pays connu -> strict, pas de repli
        return bool(fallback.match(text))

    return validate_format
