"""Harnais eval: rejoue des clips avec vérité-terrain -> EvalReport.

Vérité: data/ground_truth.json = { "clip_relpath": "PLATE", ... }.
1 plaque attendue par clip (POC: 1 camion/clip). Émet au plus 1 event/tracker.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from anpr_poc.config import load_config
from anpr_poc.detect.base import load_detector
from anpr_poc.io.source import VideoSource
from anpr_poc.ocr.paddle_reco import PaddleReco
from anpr_poc.pipeline import Pipeline
from anpr_poc.track.tracker import PlateTracker
from eval.metrics import ClipResult, EvalReport


def load_ground_truth(path: str | Path) -> dict[str, str]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def run_eval(clips_dir: str | Path, gt_path: str | Path, config_dir: str, weights: str, backend: str) -> EvalReport:
    gt = load_ground_truth(gt_path)
    cfg = load_config(config_dir)
    detector = load_detector(weights, backend=backend)
    ocr = PaddleReco()

    results: list[ClipResult] = []
    for clip_rel, truth in gt.items():
        clip_path = Path(clips_dir) / clip_rel
        # tracker neuf par clip: pas de fuite d'état inter-clips
        tracker = PlateTracker(cfg.roi)
        pipeline = Pipeline(config=cfg, detector=detector, tracker=tracker, ocr=ocr, sink=_NullSink())
        with VideoSource(str(clip_path)) as src:
            events = pipeline.run(src)
        pred = events[0].plate if events else None
        results.append(ClipResult(clip=clip_rel, truth=truth, pred=pred))
    return EvalReport(results=results)


class _NullSink:
    def emit(self, event: object) -> None:  # noqa: D401
        pass


def main() -> None:
    p = argparse.ArgumentParser(description="Non-régression ANPR sur clips.")
    p.add_argument("--clips", default="data/clips")
    p.add_argument("--gt", default="data/ground_truth.json")
    p.add_argument("--config", default="config")
    p.add_argument("--weights", required=True)
    p.add_argument("--backend", default="auto")
    a = p.parse_args()

    logging.basicConfig(level=logging.INFO)
    report = run_eval(a.clips, a.gt, a.config, a.weights, a.backend)
    print(report.summary())
    for r in report.results:
        print(f"  {r.clip}: pred={r.pred!r} truth={r.truth!r} cer={r.cer:.3f}")


if __name__ == "__main__":
    main()
