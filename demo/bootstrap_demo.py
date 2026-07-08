"""Démo bootstrap — voir le pipeline BOUGER sur une vidéo quelconque.

PAS le vrai détecteur plaque. Utilise PaddleOCR (det+rec, Apache-2.0) comme
proposeur générique de texte -> ByteTrack (mouvement/track_id) -> ConfirmBuffer
(le VRAI coeur du repo: gate + vote + debounce). Écrit une vidéo annotée.

Sert à valider la plomberie + observer le tracking en mouvement. Sur du texte
de carrosserie (pas des plaques), donc les "events" sont du texte confirmé, pas
des immatriculations. Remplacer PaddleOCR par le détecteur plaque fine-tuné pour
le vrai POC.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import cv2
import numpy as np
import supervision as sv

from anpr_poc.confirm.buffer import ConfirmBuffer
from anpr_poc.confirm.validate import make_validator
from anpr_poc.config import FormatsConfig
from anpr_poc.types import Read

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


def build_ocr():
    from paddleocr import PaddleOCR

    # doc_unwarping/orientation OFF: sinon les boites reviennent dans l'espace
    # dé-warpé et ne collent pas à l'image d'origine (annotation décalée). Plus rapide aussi.
    return PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        lang="en",
    )


def ocr_boxes(ocr, frame: np.ndarray, conf_min: float):
    """Retourne (xyxy Nx4 float32, scores N, texts list[str]) au-dessus de conf_min."""
    res = ocr.predict(frame)
    if not res:
        return np.zeros((0, 4), np.float32), np.zeros((0,), np.float32), []
    r = res[0]
    boxes = r.get("rec_boxes")
    texts = r.get("rec_texts") or []
    scores = r.get("rec_scores") or []
    xyxy, sc, tx = [], [], []
    for b, t, s in zip(boxes if boxes is not None else [], texts, scores):
        s = float(s)
        if s < conf_min:
            continue
        x1, y1, x2, y2 = (float(v) for v in np.asarray(b).reshape(-1)[:4])
        xyxy.append([x1, y1, x2, y2])
        sc.append(s)
        tx.append(re.sub(r"[^A-Z0-9]", "", str(t).upper()))  # canonique (cf. paddle_reco)
    if not xyxy:
        return np.zeros((0, 4), np.float32), np.zeros((0,), np.float32), []
    return np.asarray(xyxy, np.float32), np.asarray(sc, np.float32), tx


_PALETTE = [
    (66, 135, 245), (52, 211, 153), (245, 158, 66), (236, 72, 153),
    (168, 85, 247), (250, 204, 21), (34, 197, 94), (239, 68, 68),
]


def _color_for(tid: int) -> tuple[int, int, int]:
    if tid < 0:
        return (128, 128, 128)
    r, g, b = _PALETTE[tid % len(_PALETTE)]
    return (b, g, r)  # BGR pour OpenCV


def _ascii(text: str) -> str:
    """cv2.putText ne rend que l'ASCII -> remplace le reste (évite les '??')."""
    return "".join(c if 32 <= ord(c) < 127 else "?" for c in text)


def _center(box) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2, (y1 + y2) / 2


def _match_det_to_track_ids(xyxy: np.ndarray, tracked) -> list[int]:
    """Associe chaque détection brute au tracker_id du track le plus proche (centre)."""
    ids = [-1] * len(xyxy)
    if len(xyxy) == 0 or len(tracked) == 0:
        return ids
    tcenters = [(_center(tracked.xyxy[j]), int(tracked.tracker_id[j])) for j in range(len(tracked))]
    for i in range(len(xyxy)):
        cx, cy = _center(xyxy[i])
        best_d, best_id = 1e18, -1
        for (tcx, tcy), tid in tcenters:
            d = (cx - tcx) ** 2 + (cy - tcy) ** 2
            if d < best_d:
                best_d, best_id = d, tid
        ids[i] = best_id
    return ids


def _draw_label(img: np.ndarray, text: str, x1: int, y1: int, color, frame_h: int) -> None:
    """Label calé juste au-dessus de la boite; bascule dessous si collé au bord haut."""
    font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
    (tw, th), base = cv2.getTextSize(text, font, scale, thick)
    ytop = y1 - th - base - 4
    if ytop < 0:  # boite tout en haut -> label sous la boite
        ytop = y1 + 4
    x = max(0, min(x1, img.shape[1] - tw - 4))
    cv2.rectangle(img, (x, ytop), (x + tw + 4, ytop + th + base + 4), color, -1)
    cv2.putText(img, text, (x + 2, ytop + th + 2), font, scale, (255, 255, 255), thick, cv2.LINE_AA)


def run(video: str, out_video: str, every: int, max_frames: int, conf: float, k: int,
        start_sec: float = 0.0, end_sec: float = 0.0, dedup_sec: float = 5.0,
        country: str = "FR") -> None:
    ocr = build_ocr()
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise RuntimeError(f"open failed: {video}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    start_frame = int(round(start_sec * src_fps))
    end_frame = int(round(end_sec * src_fps)) if end_sec else 0
    if start_frame:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    eff_fps = max(1.0, src_fps / every)

    Path(out_video).parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(out_video, cv2.VideoWriter_fourcc(*"mp4v"), eff_fps, (w, h))

    tracker = sv.ByteTrack(frame_rate=int(round(eff_fps)))
    # annotation dessinée à la main (cv2) sur les boites OCR brutes -> position exacte

    # coeur repo: gate 0.6, K concordantes, validation STRICTE du pays + anti-doublon
    fmt = FormatsConfig(default_country=country)
    confirm = ConfirmBuffer(
        make_validator(fmt),
        conf_min=0.6,
        k_consensus=k,
        default_country=country,
        dedup_window_sec=dedup_sec,
    )
    events: list[dict] = []

    src_idx = start_frame
    proc = 0
    while True:
        if end_frame and src_idx >= end_frame:
            break
        ok, frame = cap.read()
        if not ok:
            break
        if (src_idx - start_frame) % every != 0:
            src_idx += 1
            continue
        ts = src_idx / src_fps

        xyxy, scores, texts = ocr_boxes(ocr, frame, conf)
        if len(xyxy):
            det = sv.Detections(
                xyxy=xyxy,
                confidence=scores,
                data={"text": np.asarray(texts, dtype=object)},
            )
        else:
            det = sv.Detections.empty()

        tracked = tracker.update_with_detections(det)

        # confirmation sur les tracks (IDs stables)
        for i in range(len(tracked)):
            tid = int(tracked.tracker_id[i])
            text = str(tracked.data["text"][i]) if "text" in tracked.data else ""
            score = float(tracked.confidence[i]) if tracked.confidence is not None else 1.0
            if text and not confirm.already_emitted(tid):
                read = Read(text=text, char_confidences=tuple(score for _ in text), frame_idx=src_idx)
                ev = confirm.add(tid, read, timestamp=ts)
                if ev is not None:
                    events.append(
                        {"text": ev.plate, "tracker_id": ev.tracker_id, "t": round(ev.timestamp, 2), "conf": round(ev.confidence, 3)}
                    )

        # ANNOTATION: dessin sur la boite OCR BRUTE de cette frame (position exacte,
        # pas la boite Kalman prédite qui traîne). ID récupéré par plus-proche-centre.
        annotated = frame.copy()
        id_by_det = _match_det_to_track_ids(xyxy, tracked)
        for i in range(len(xyxy)):
            x1, y1, x2, y2 = (int(v) for v in xyxy[i])
            tid = id_by_det[i]
            color = _color_for(tid)
            label = f"#{tid} {_ascii(texts[i])}" if tid >= 0 else _ascii(texts[i])
            emitted = tid >= 0 and confirm.already_emitted(tid)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3 if emitted else 2)
            _draw_label(annotated, label, x1, y1, color, h)
        cv2.putText(annotated, f"t={ts:5.1f}s  confirmed={len(events)}", (8, h - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
        writer.write(annotated)

        proc += 1
        if proc % 25 == 0:
            print(f"[{proc}] src_frame={src_idx} t={ts:.1f}s tracks={len(tracked)} events={len(events)}", flush=True)
        if max_frames and proc >= max_frames:
            break
        src_idx += 1

    cap.release()
    writer.release()
    out_json = Path(out_video).with_suffix(".events.jsonl")
    with out_json.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"DONE frames={proc} events={len(events)} -> {out_video} / {out_json}", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--video", default="data/clips/volvo_test.mp4")
    p.add_argument("--out-video", default="out/volvo_annotated.mp4")
    p.add_argument("--every", type=int, default=4, help="traite 1 frame sur N")
    p.add_argument("--max-frames", type=int, default=0, help="0 = toute la vidéo")
    p.add_argument("--conf", type=float, default=0.6, help="seuil score OCR pour garder une boite")
    p.add_argument("--k", type=int, default=3, help="K_CONSENSUS")
    p.add_argument("--start-sec", type=float, default=0.0)
    p.add_argument("--end-sec", type=float, default=0.0, help="0 = jusqu'a la fin")
    p.add_argument("--dedup-sec", type=float, default=5.0, help="fenetre anti-doublon plaque")
    p.add_argument("--country", default="FR", help="pays pour validation format (FR/GB/DE/...)")
    a = p.parse_args()
    run(a.video, a.out_video, a.every, a.max_frames, a.conf, a.k, a.start_sec, a.end_sec,
        a.dedup_sec, a.country)
