<div align="center">

# 🚚 plate-recognition — ANPR camions (vue fixe, plaques UE)

**Lecture automatique de plaques d'immatriculation depuis une caméra fixe.
Une seule valeur confirmée par véhicule — jamais de sortie frame-par-frame.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](.github/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-34%2F34-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-94%25-brightgreen.svg)](pyproject.toml)
[![Lint](https://img.shields.io/badge/ruff%20%C2%B7%20mypy-strict-brightgreen.svg)](.github/workflows/ci.yml)
[![CI licences](https://img.shields.io/badge/licences-AGPL--free%20(CI)-success.svg)](.github/workflows/ci.yml)
[![Security](https://img.shields.io/badge/security-CodeQL%20%C2%B7%20pip--audit%20%C2%B7%20Dependabot-blue.svg)](SECURITY.md)
[![Deps](https://img.shields.io/badge/licences-MIT%20%2F%20Apache--2.0-success.svg)](docs/PROBLEMATIQUES.md#p3--contamination-de-licence-agpl)
[![Portage](https://img.shields.io/badge/backend-M1%20MPS%20%E2%86%92%20Jetson%20TensorRT-orange.svg)](docs/ARCHITECTURE.md#portabilité)
[![Statut](https://img.shields.io/badge/statut-POC%20%C2%B7%20d%C3%A9tecteur%20%C3%A0%20entra%C3%AEner-yellow.svg)](docs/ROADMAP.md)

</div>

---

## 📖 Documentation

| Document | Contenu |
|----------|---------|
| **[🛠️ Installation](docs/INSTALLATION.md)** | Procédure complète pas à pas, vérification, dépannage |
| **[🧪 Guide de test](docs/GUIDE_TEST.md)** | 3 niveaux de test : unitaire → démo vidéo → pipeline réel |
| **[🧱 Architecture](docs/ARCHITECTURE.md)** | Briques fonctionnelles & techniques, carte des modules, portabilité |
| **[🔀 Pipeline & Workflow](docs/PIPELINE.md)** | Le flux frame → événement, étape par étape. La logique de confirmation en détail |
| **[⚠️ Problématiques & solutions](docs/PROBLEMATIQUES.md)** | Les 9 problèmes durs de l'ANPR et comment ils sont traités (avec preuves) |
| **[🎯 Risques restants](docs/RISQUES.md)** | Dette, inconnues, blocages, points RGPD/sécurité à traiter |
| **[✅ Roadmap & TODO](docs/ROADMAP.md)** | Jalons POC → production → Jetson, avec cases à cocher |

> 💡 Nouveau sur le projet ? **[Installe](docs/INSTALLATION.md)**, puis **[teste](docs/GUIDE_TEST.md)**, puis lis **Architecture → Pipeline → Problématiques**.

---

## 🎬 En une image

Test sur trafic réel (caméra fixe, 1080p, plaques UK), 5 s : **5 plaques suivies et confirmées en parallèle**, une boîte par véhicule.

```
#2 GX15 OGJ   #3 MW51 VSU   #4 NA13 NRU   ...   (multi-plaque simultané)
```

Chaque véhicule = un `tracker_id` = un buffer de lectures = **un seul événement final**, après vote caractère-par-caractère sur plusieurs frames. C'est le cœur du système ([détail](docs/PIPELINE.md#la-logique-de-confirmation)).

---

## ⚡ Démarrage rapide

```bash
# Python 3.10+ requis (unions pydantic). Sur Mac : brew install python@3.13
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[torch,dev]"          # ou : uv sync --extra torch --extra dev

# Tests du cœur (aucun modèle requis)
pytest tests/ -q                        # 11 passed

# Pipeline réel (nécessite un détecteur plaque entraîné — voir Roadmap)
python -m anpr_poc.run <video|rtsp> --weights weights/plate.onnx --out out/events.jsonl

# Démo bootstrap (sans détecteur dédié — valide la plomberie + rend une vidéo annotée)
python -m demo.bootstrap_demo --video clip.mp4 --start-sec 0 --end-sec 5 --country GB
```

Sortie : un événement JSON par véhicule.

```json
{"plate": "GX-521-EW", "tracker_id": 3, "timestamp": 37.5, "confidence": 0.992, "country": "FR", "snapshot_path": null}
```

---

## 🗺️ Structure du dépôt

```
anpr_poc/
├── config.py         chargement config injectée (pydantic) — aucun seuil en dur
├── types.py          dataclasses partagées (Read, Event, BBox…)
├── detect/           détecteur backend-agnostic (torch/onnx/tensorrt) + export ONNX
├── track/            wrapper supervision (ByteTrack + LineZone)
├── ocr/              PP-OCRv5 reco + rectify() + euroband_strip()
├── confirm/          ★ cœur : buffer/tracker_id, vote, validate_format, debounce, dédup
├── io/               source vidéo (fichier/RTSP), sink événements (jsonl/log)
├── pipeline.py       orchestration frame → événement
└── run.py            entrée CLI
config/               homographie.json · roi.json · formats.yaml · thresholds.yaml
demo/                 démo bootstrap (PaddleOCR + rendu vidéo annoté)
eval/                 harnais non-régression (CER + taux FP/FN)
tests/                tests unitaires du cœur confirmation
docs/                 📖 cette documentation
```

---

## 🔒 Contraintes dures (non négociables)

- **Licences MIT / Apache-2.0 uniquement.** Aucun AGPL (⇒ **pas** d'Ultralytics YOLOv5/v8/v11), aucun poids non-commercial (pas de YOLO-NAS). RF-DETR limité à **base/S** (XL/2XL = licence PML, interdit).
- **Apple Silicon M1** : PyTorch MPS / CPU / ONNX Runtime + CoreML EP.
- **Portable Jetson** : tout modèle exportable ONNX → TensorRT. Aucun code Mac-only dans le chemin d'inférence.
- **Temps réel déterministe** : pas de VLM/LLM dans la boucle (hallucination = fausse plaque plausible).

Détail et garde-fous : [Problématiques § licences](docs/PROBLEMATIQUES.md#p3--contamination-de-licence-agpl).

---

## 📌 Statut actuel

| Brique | État |
|--------|------|
| Cœur confirmation (vote, gate, validation, dédup edit-distance, gate franchissement) | ✅ Codé + testé (25/25) |
| Pipeline réel end-to-end (`anpr_poc.run --backend stub`) | ✅ Tourne (détecteur factice + OCR 3.x réel) |
| Config injectée + **validation fail-fast** (ROI, homographie), plaques canoniques | ✅ |
| Snapshots de preuve (fond flouté RGPD) | ✅ Câblé (`--snapshots-dir`) |
| Tracking multi-plaque (supervision) | ✅ Validé sur trafic réel |
| OCR PP-OCRv5/v6 (API 3.x) | ✅ Intégré |
| Rendu vidéo annoté + démo bootstrap | ✅ |
| CI : lint+format+mypy · tests **matrice 3.10–3.13** · install réel · couverture 94% · licences · CVE · **secrets** · **build+SBOM** · CodeQL | ✅ |
| Purge mémoire flux long | ✅ |
| Harnais eval (CER, FP/FN) | ✅ Codé |
| **Détecteur plaque entraîné** | ⛔ **Bloqueur** — stub only, à entraîner sur données réelles |
| Confidences OCR par caractère (CTC) | 🟡 Approximé (score-ligne répliqué, documenté) |
| Calibration homographie + ROI terrain | 🟡 Valeurs génériques |
| Portage Jetson / TensorRT | ⬜ Prévu, non commencé |

👉 Feuille de route complète et cases à cocher : **[docs/ROADMAP.md](docs/ROADMAP.md)**.
