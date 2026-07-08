"""Orchestration frame -> event. Multi-frames + vote, jamais frame-par-frame.

Trigger(ROI) -> Détection -> Tracking -> Redressement -> strip euroband -> OCR
-> Confirmation (buffer/vote/debounce) -> Sink. Config injectée, sans état global.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from anpr_poc.config import AppConfig
from anpr_poc.confirm import ConfirmBuffer, make_validator
from anpr_poc.detect.base import Detector
from anpr_poc.io.sink import EventSink
from anpr_poc.io.source import VideoSource
from anpr_poc.ocr.paddle_reco import PaddleReco
from anpr_poc.ocr.preprocess import euroband_strip, rectify
from anpr_poc.track.tracker import PlateTracker
from anpr_poc.types import BBox, Event

log = logging.getLogger("anpr")


@dataclass
class Pipeline:
    config: AppConfig
    detector: Detector
    tracker: PlateTracker
    ocr: PaddleReco
    sink: EventSink

    def __post_init__(self) -> None:
        t = self.config.thresholds
        self._confirm = ConfirmBuffer(
            validate_format=make_validator(self.config.formats),
            conf_min=t.conf_min,
            k_consensus=t.k_consensus,
            default_country=self.config.formats.default_country,
            dedup_window_sec=t.dedup_window_sec,
            dedup_edit_distance=t.dedup_edit_distance,
            require_crossing=t.require_line_crossing,
        )
        self._H = self.config.homography_matrix
        self._strip = t.euroband_strip_frac
        self._det_conf = t.det_conf_min

    def run(self, source: VideoSource) -> list[Event]:
        events: list[Event] = []
        fps = source.fps
        for frame_idx, frame in source.frames():
            ts = frame_idx / fps if fps else float(frame_idx)

            detections = self.detector.detect(frame, self._det_conf)
            tracks = self.tracker.update(detections)

            # purge mémoire: buffers des tracks disparus (flux long / RTSP 24-7)
            self._confirm.retain({tid for tid, _, _ in tracks})

            for tracker_id, bbox, crossed in tracks:
                if self._confirm.already_emitted(tracker_id):
                    continue
                if not self.tracker.in_roi(bbox):
                    continue

                read = self._read_plate(frame, bbox, frame_idx)
                if read is None:
                    continue

                event = self._confirm.add(tracker_id, read, timestamp=ts, crossed=crossed)
                if event is not None:
                    self.sink.emit(event)
                    events.append(event)
                    self._confirm.flush(tracker_id)
        return events

    def _read_plate(self, frame, bbox: BBox, frame_idx: int):
        x1, y1, x2, y2 = (int(v) for v in bbox.xyxy)
        crop = frame[max(0, y1):y2, max(0, x1):x2]
        if crop.size == 0:
            return None
        crop = rectify(crop, self._H)
        crop = euroband_strip(crop, self._strip)
        return self.ocr.read(crop, frame_idx=frame_idx)
