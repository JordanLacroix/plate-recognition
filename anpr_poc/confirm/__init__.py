"""Confirmation: buffer par tracker_id, gate qualité, validation format, vote, debounce."""

from anpr_poc.confirm.buffer import ConfirmBuffer
from anpr_poc.confirm.consensus import per_char_majority_vote
from anpr_poc.confirm.validate import make_validator

__all__ = ["ConfirmBuffer", "per_char_majority_vote", "make_validator"]
