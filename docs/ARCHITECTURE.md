# 🧱 Architecture

[← Retour au README](../README.md) · [Pipeline →](PIPELINE.md) · [Problématiques →](PROBLEMATIQUES.md) · [Risques →](RISQUES.md) · [Roadmap →](ROADMAP.md)

---

## Sommaire

- [Vue d'ensemble](#vue-densemble)
- [Briques fonctionnelles](#briques-fonctionnelles)
- [Briques techniques](#briques-techniques)
- [Carte des modules](#carte-des-modules)
- [Principes de conception](#principes-de-conception)
- [Portabilité](#portabilité)

---

## Vue d'ensemble

Le système transforme un flux vidéo (caméra fixe) en **événements plaque**, à raison d'**un seul événement confirmé par véhicule**. Il n'émet jamais de lecture frame-par-frame : une plaque n'est publiée qu'après consensus sur plusieurs images du même véhicule.

```mermaid
flowchart LR
    CAM[📹 Caméra fixe<br/>fichier / RTSP] --> TRG[Trigger ROI]
    TRG --> DET[Détection plaque]
    DET --> TRK[Tracking<br/>1 id / véhicule]
    TRK --> REC[Redressement<br/>homographie]
    REC --> OCR[OCR reco<br/>+ confiances]
    OCR --> CONF[★ Confirmation<br/>vote + debounce]
    CONF --> SINK[📤 Événement unique<br/>JSON / log]

    style CONF fill:#ffe08a,stroke:#d98b00,color:#000
    style DET fill:#e0e0e0,stroke:#888,color:#000
```

> La brique **Détection** (grisée) est le seul maillon non encore entraîné — voir [Roadmap](ROADMAP.md).

---

## Briques fonctionnelles

Ce que le système *fait*, du point de vue métier.

| # | Brique | Responsabilité | Pourquoi elle existe |
|---|--------|----------------|----------------------|
| F1 | **Déclenchement (Trigger)** | Ne traiter que quand un véhicule entre dans la zone utile (ROI) et franchit la ligne | Économie CPU : la vue est fixe, le fond constant. Inutile d'analyser une route vide |
| F2 | **Localisation plaque** | Trouver la boîte de la plaque dans l'image | Un camion porte du texte partout (marque, pub, ADR) : on cible la plaque, pas « du texte » |
| F3 | **Suivi véhicule** | Attribuer un identifiant stable à chaque véhicule | Permet d'**agréger plusieurs lectures de la même plaque** — base du vote |
| F4 | **Redressement** | Ramener la plaque en quasi fronto-parallèle | La caméra voit la plaque de biais ; l'OCR lit mieux une plaque droite |
| F5 | **Nettoyage euroband** | Retirer la bande bleue UE (pays + étoiles) avant OCR | Sinon l'OCR lit « F », « D », « NL »… comme des caractères de la plaque |
| F6 | **Lecture (OCR)** | Transcrire la plaque + une confiance par caractère | Les confiances alimentent le vote pondéré |
| F7 | **Confirmation** | Décider *quand* et *quoi* émettre | ★ Le cœur métier : 90 % de la valeur (et des bugs) sont ici |
| F8 | **Publication** | Émettre l'événement final | Interface avec le reste du SI (fichier, log, plus tard file/DB) |

---

## Briques techniques

Comment chaque brique est *implémentée*. Choix figés — ne pas substituer sans raison licence/perf explicite.

| Rôle | Choix | Licence | Backend M1 | Module |
|------|-------|---------|------------|--------|
| Détection plaque | **LibreYOLO** (primaire) / **RF-DETR-S** (repli occlusion/angle) | MIT / Apache-2.0 | PyTorch MPS | [`detect/`](../anpr_poc/detect) |
| Tracking | **supervision** (ByteTrack + LineZone / PolygonZone) | MIT | CPU / numpy | [`track/`](../anpr_poc/track) |
| OCR reco | **PaddleOCR PP-OCRv5** (reconnaissance seule) | Apache-2.0 | CPU ou ONNX + CoreML | [`ocr/`](../anpr_poc/ocr) |
| Vision utils | **OpenCV** | Apache-2.0 | — | transverse |
| Config | **pydantic** + YAML/JSON | MIT | — | [`config.py`](../anpr_poc/config.py) |

> ⚠️ **RF-DETR** : rester sur `base`/`S`. Les variantes `XL`/`2XL` sont sous licence PML → interdites ici. Voir [Problématiques § licences](PROBLEMATIQUES.md#p3--contamination-de-licence-agpl).

---

## Carte des modules

```mermaid
flowchart TB
    subgraph io["io/ — entrées/sorties"]
        SRC[source.py<br/>VideoSource fichier/RTSP]
        SNK[sink.py<br/>Jsonl / Log / Multi]
    end
    subgraph detect["detect/ — backend-agnostic"]
        BASE[base.py<br/>Detector Protocol + load_detector]
        TORCH[libreyolo.py<br/>TorchDetector MPS]
        ONNX[onnx_detector.py<br/>OnnxDetector CoreML]
        EXP[export.py<br/>.pt → .onnx]
    end
    subgraph track["track/"]
        TRK[tracker.py<br/>PlateTracker : ByteTrack + LineZone + ROI]
    end
    subgraph ocr["ocr/"]
        PRE[preprocess.py<br/>rectify · euroband_strip]
        PAD[paddle_reco.py<br/>PaddleReco]
    end
    subgraph confirm["confirm/ — ★ cœur"]
        VAL[validate.py<br/>validate_format par pays]
        VOTE[consensus.py<br/>vote char pondéré]
        BUF[buffer.py<br/>ConfirmBuffer : gate/vote/debounce/dédup]
    end
    CFG[config.py<br/>Thresholds · Roi · Formats · Homographie]
    PIPE[pipeline.py<br/>orchestration]

    SRC --> PIPE --> BASE
    PIPE --> TRK --> PIPE
    PIPE --> PRE --> PAD --> PIPE
    PIPE --> BUF
    BUF --> VAL & VOTE
    BUF --> SNK
    CFG -.injecté.-> PIPE
    BASE --> TORCH & ONNX

    style confirm fill:#fff6db,stroke:#d98b00
```

Le fichier [`pipeline.py`](../anpr_poc/pipeline.py) est le seul point qui connaît toutes les briques ; chacune est isolée et testable séparément.

---

## Principes de conception

1. **Backend-agnostic dès le premier jour.** Le détecteur est un `Protocol` ([`detect/base.py`](../anpr_poc/detect/base.py)). `load_detector(weights, backend="auto")` choisit `torch` / `onnx` / `tensorrt` selon l'extension. Aucune ligne Mac-only dans le chemin d'inférence → le portage Jetson ne touche que le backend.

2. **Sans état global.** `ConfirmBuffer`, `PlateTracker` sont instanciés par run. L'eval crée un tracker neuf par clip → aucune fuite d'état entre clips.

3. **Config injectée, zéro seuil en dur.** `CONF_MIN`, `K_CONSENSUS`, ROI, homographie, regex par pays, fenêtre de dédup → tous dans [`config/`](../config), chargés via pydantic. Changer un seuil = éditer un YAML, pas le code.

4. **Déterministe.** Pas de VLM/LLM dans la boucle. Le seul « jugement » est un vote arithmétique + des regex — traçable et reproductible.

5. **Le cœur est isolé et testé.** Tout [`confirm/`](../anpr_poc/confirm) fonctionne sans aucun modèle (numpy pur) → 11 tests unitaires rapides couvrent la logique où vivent 90 % des bugs.

---

## Portabilité

```mermaid
flowchart LR
    subgraph mac["🍎 Mac M1 — développement"]
        PT[.pt PyTorch MPS]
        ORT1[.onnx ONNX Runtime<br/>CoreML EP]
    end
    subgraph jetson["🟩 Jetson — production"]
        ORT2[.onnx ONNX Runtime<br/>TensorRT/CUDA EP]
        TRT[.engine TensorRT<br/>INT8 / FP16]
    end
    PT -->|export.py| ORT1
    ORT1 -->|même graphe| ORT2
    ORT2 -->|trtexec| TRT

    style jetson fill:#e8f5e9,stroke:#2e7d32
```

- **Même code, backend commuté.** Le passage Mac → Jetson change l'exécuteur, pas la logique.
- **Export ONNX** ([`detect/export.py`](../anpr_poc/detect/export.py)) : shapes fixes, opset stable → conversion TensorRT simplifiée sur Jetson.
- **Wheels aarch64** depuis `pypi.jetson-ai-lab.io` (éviter la compilation manuelle des deps).
- **Refroidissement actif** requis sur Jetson pour charge soutenue.

⚠️ Ce portage est **prévu mais non commencé** — voir [Roadmap § Jalon 3](ROADMAP.md#jalon-3--portage-jetson).

---

[← README](../README.md) · [Pipeline →](PIPELINE.md)
