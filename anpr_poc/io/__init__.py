"""IO: source vidéo (fichier/RTSP), sink événements (json/log)."""

from anpr_poc.io.sink import EventSink, JsonlSink, LogSink
from anpr_poc.io.source import VideoSource

__all__ = ["VideoSource", "EventSink", "JsonlSink", "LogSink"]
