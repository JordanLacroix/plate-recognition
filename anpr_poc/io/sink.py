"""Sink événements. 1 event stable par camion -> jsonl et/ou log."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from anpr_poc.types import Event


class EventSink(Protocol):
    def emit(self, event: Event) -> None: ...


class JsonlSink:
    """Une ligne JSON par événement confirmé."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: Event) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")


class LogSink:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._log = logger or logging.getLogger("anpr")

    def emit(self, event: Event) -> None:
        self._log.info(
            "PLATE %s tid=%d conf=%.3f country=%s",
            event.plate,
            event.tracker_id,
            event.confidence,
            event.country,
        )


class MultiSink:
    def __init__(self, *sinks: EventSink) -> None:
        self._sinks = sinks

    def emit(self, event: Event) -> None:
        for s in self._sinks:
            s.emit(event)
