"""Entrée CLI: assemble le pipeline depuis config/ et une source vidéo."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from anpr_poc.config import load_config
from anpr_poc.detect.base import load_detector
from anpr_poc.io.sink import JsonlSink, LogSink, MultiSink
from anpr_poc.io.source import VideoSource
from anpr_poc.ocr.paddle_reco import PaddleReco
from anpr_poc.pipeline import Pipeline
from anpr_poc.track.tracker import PlateTracker


def main() -> None:
    p = argparse.ArgumentParser(description="POC ANPR camions — vue fixe, plaques UE.")
    p.add_argument("source", help="Chemin vidéo ou URL RTSP.")
    p.add_argument("--config", default="config", help="Dossier config/.")
    p.add_argument("--weights", required=True, help="Poids détecteur (.pt/.onnx).")
    p.add_argument("--backend", default="auto", choices=["auto", "torch", "onnx", "tensorrt"])
    p.add_argument("--out", default="out/events.jsonl")
    a = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(a.config)

    detector = load_detector(a.weights, backend=a.backend)
    tracker = PlateTracker(cfg.roi)
    ocr = PaddleReco()
    sink = MultiSink(JsonlSink(a.out), LogSink())

    pipeline = Pipeline(config=cfg, detector=detector, tracker=tracker, ocr=ocr, sink=sink)
    with VideoSource(a.source) as src:
        events = pipeline.run(src)
    logging.getLogger("anpr").info("Terminé: %d événements. -> %s", len(events), Path(a.out))


if __name__ == "__main__":
    main()
