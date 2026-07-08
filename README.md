# anpr_poc — ANPR camions (vue fixe, plaques UE)

POC : depuis une caméra fixe, détecter + lire la plaque des camions, émettre **1 seule
valeur confirmée par camion** (pas de sortie frame-par-frame). Voir `CLAUDE.md`.

## Contraintes dures
- Licences **MIT / Apache-2.0 uniquement**. Aucun AGPL (pas Ultralytics YOLO), aucun poids NC.
- Tourne sur **Apple Silicon M1** : PyTorch MPS / CPU / ONNX Runtime + CoreML EP.
- **Backend-agnostic** : `.pt`/`.onnx` sur Mac → TensorRT sur Jetson plus tard.
- Temps réel déterministe : **pas de VLM/LLM** dans la boucle.

## Stack
| Rôle | Choix | Licence |
|------|-------|---------|
| Détection plaque | LibreYOLO (primaire) / RF-DETR base·S (repli) | MIT / Apache-2.0 |
| Tracking | supervision (ByteTrack + LineZone) | MIT |
| OCR reco | PaddleOCR PP-OCRv5 (reco seule) | Apache-2.0 |
| Vision utils | OpenCV | Apache-2.0 |

## Pipeline
Trigger (ROI/LineZone) → Détection plaque → Tracking (1 `tracker_id`/camion) →
Redressement (homographie pré-calibrée) → strip euroband → OCR reco (conf/char) →
**Confirmation** (buffer + gate + validation format + vote char-par-char + debounce K) → Sink.

Le cœur est `anpr_poc/confirm/` — 90 % des bugs vivent ici. Testé dans `tests/test_confirm.py`.

## Structure
```
anpr_poc/
  config.py        chargement config injectée (pydantic)
  types.py         dataclasses partagées (Read, Event, BBox…)
  detect/          détecteur backend-agnostic (torch/onnx/tensorrt) + export ONNX
  track/           wrapper supervision ByteTrack + LineZone
  ocr/             PP-OCRv5 reco + rectify() + euroband_strip()
  confirm/         buffer/tracker_id, vote consensus, validate_format, debounce
  io/              source vidéo (fichier/RTSP), sink événements (jsonl/log)
  pipeline.py      orchestration frame → event
  run.py           entrée CLI
config/            homographie.json, roi.json, formats.yaml, thresholds.yaml
eval/              harnais non-régression (CER + FP/FN événement)
data/              clips + crops + ground_truth.json (hors git)
tests/             unit tests du cœur confirmation
```

## Install
```bash
uv sync --extra torch --extra dev     # ou: pip install -e ".[torch,dev]"
```

## Lancer
```bash
python -m anpr_poc.run <video|rtsp> --weights weights/plate.onnx --out out/events.jsonl
```

## Eval
```bash
python -m eval.harness --weights weights/plate.onnx
```

## Tests (cœur, sans modèle)
```bash
pytest tests/ -q
```

## Tous les seuils
`config/thresholds.yaml` : `conf_min`, `k_consensus`, `det_conf_min`, `euroband_strip_frac`.
Jamais en dur dans le code.

## Portage Jetson (plus tard)
Même code, backend commuté `.onnx → .engine` (INT8/FP16). Wheels aarch64 depuis
`pypi.jetson-ai-lab.io`. Refroidissement actif requis.
