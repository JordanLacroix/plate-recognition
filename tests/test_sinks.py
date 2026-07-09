"""Sinks événements: jsonl / log / multi."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from anpr_poc.io.sink import JsonlSink, LogSink, MultiSink
from anpr_poc.types import Event

_EV = Event(plate="AB123CD", tracker_id=3, timestamp=1.5, confidence=0.9, country="FR")


def test_jsonl_sink_appends_one_line_per_event(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "events.jsonl"  # crée aussi le dossier parent
    sink = JsonlSink(path)
    sink.emit(_EV)
    sink.emit(_EV)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert rec["plate"] == "AB123CD" and rec["tracker_id"] == 3


def test_log_sink_emits(caplog) -> None:  # type: ignore[no-untyped-def]
    with caplog.at_level(logging.INFO, logger="anpr"):
        LogSink().emit(_EV)
    assert "AB123CD" in caplog.text


def test_multi_sink_fans_out(tmp_path: Path) -> None:
    a = JsonlSink(tmp_path / "a.jsonl")
    b = JsonlSink(tmp_path / "b.jsonl")
    MultiSink(a, b).emit(_EV)
    assert (tmp_path / "a.jsonl").exists()
    assert (tmp_path / "b.jsonl").exists()
