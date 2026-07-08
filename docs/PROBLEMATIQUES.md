# ⚠️ Problématiques & solutions

Les problèmes durs de l'ANPR et **comment ils sont traités ici** — avec les preuves empiriques récoltées pendant le POC.

[← Pipeline](PIPELINE.md) · [Retour README](../README.md) · [Risques →](RISQUES.md) · [Roadmap →](ROADMAP.md)

---

## Sommaire

| # | Problématique | Statut |
|---|---------------|--------|
| [P1](#p1--frame-par-frame--fausses-plaques-plausibles) | Frame-par-frame ⇒ fausses plaques | ✅ Traité (cœur) |
| [P2](#p2--hallucination--bruit-docr) | Hallucination / bruit d'OCR | ✅ Traité (multi-filtres) |
| [P3](#p3--contamination-de-licence-agpl) | Contamination de licence AGPL | ✅ Traité (stack + garde-fous) |
| [P4](#p4--portabilité-jetson) | Portabilité Jetson | ✅ Conçu (backend-agnostic) |
| [P5](#p5--résolution--flou-de-mouvement) | Résolution / flou de mouvement | ✅ Quantifié (exigence matérielle) |
| [P6](#p6--fragmentation-de-tracking) | Fragmentation de tracking | ✅ Traité (dédup) |
| [P7](#p7--plusieurs-véhicules-simultanés) | Multi-véhicules simultanés | ✅ Validé terrain |
| [P8](#p8--euroband-lu-comme-des-caractères) | Euroband lu comme caractères | ✅ Traité (strip) |
| [P9](#p9--alignement-annotation--coordonnées-ocr) | Alignement annotation / coords OCR | ✅ Corrigé (bug trouvé) |

> Les problèmes **non encore résolus** sont dans [RISQUES.md](RISQUES.md).

---

## P1 — Frame-par-frame ⇒ fausses plaques plausibles

**Problème.** Émettre la lecture de chaque frame produit des plaques fausses mais plausibles (un caractère mal lu sur une image floue). Inacceptable pour un système de contrôle.

**Solution.** On n'émet **jamais** par frame. On accumule les lectures par `tracker_id` pendant toute la traversée, puis on émet **une seule fois** après :
- gate de qualité,
- vote caractère-par-caractère sur plusieurs frames,
- debounce sur `K_CONSENSUS` lectures concordantes.

📍 [`confirm/buffer.py`](../anpr_poc/confirm/buffer.py) · détail : [Pipeline § confirmation](PIPELINE.md#la-logique-de-confirmation).

**Preuve.** Sur le clip Volvo 720p, une frame isolée lit `HWS1VSU` ; le vote sur plusieurs frames converge vers la vraie plaque `MW51 VSU`. Le bruit d'une frame ne se propage pas à l'événement.

---

## P2 — Hallucination / bruit d'OCR

**Problème.** L'OCR se trompe : caractères proches (`0/O`, `1/I`, `5/S`, `M/W`), reflets, ombres.

**Solution — défense en profondeur, 4 couches :**
1. **Gate de confiance** — rejette toute lecture avec un caractère sous `CONF_MIN`.
2. **Validation de format par pays** — une lecture qui ne respecte pas le gabarit du pays est écartée du vote (pas juste « pénalisée »).
3. **Vote pondéré par confiance** — les caractères sûrs pèsent plus.
4. **K-consensus** — il faut plusieurs frames d'accord.

**Choix explicite : pas de VLM/LLM dans la boucle.** Un LLM « corrigerait » une plaque en une plaque plausible mais fausse. On préfère un vote arithmétique déterministe et traçable.

**Preuve & limite.** Sur trafic UK, la validation GB (`^[A-Z]{2}\d{2}[A-Z]{3}$`) ne laisse sortir que des plaques bien formées. Le bruit résiduel (ex. `KH05ZZK` pour une plaque réelle `NH55 ZZK`) vient du **manque de détecteur dédié + redressement** en mode bootstrap — voir [Risques § R1](RISQUES.md#r1--détecteur-plaque-non-entraîné-bloqueur).

---

## P3 — Contamination de licence AGPL

**Problème.** La plupart des détecteurs ANPR populaires reposent sur Ultralytics (YOLOv5/v8/v11) → **AGPL-3.0**. Incompatible avec un déploiement commercial fermé. Idem YOLO-NAS (poids non-commerciaux).

**Solution — contrainte dure, appliquée et documentée :**

| Interdit | Raison | Alternative retenue |
|----------|--------|---------------------|
| Ultralytics YOLOv5/v8/v11/v12 | AGPL-3.0 | **LibreYOLO** (MIT) |
| YOLO-NAS | poids non-commercial | RF-DETR-S (Apache-2.0) |
| RF-DETR **XL/2XL** | licence PML | RF-DETR **base/S** uniquement |

Garde-fous en place :
- Dépendances épinglées, **toutes MIT/Apache-2.0** ([`pyproject.toml`](../pyproject.toml)).
- Rappel licence directement dans le code du wrapper détecteur ([`detect/libreyolo.py`](../anpr_poc/detect/libreyolo.py)).
- Règle projet : *vérifier le graphe de dépendances à chaque ajout de package ; aucune AGPL ne doit entrer.*

📌 **À ajouter** (voir [Roadmap](ROADMAP.md)) : un contrôle automatique de licences en CI (`pip-licenses`) pour rendre la contrainte *exécutable* et non seulement documentaire.

---

## P4 — Portabilité Jetson

**Problème.** Le POC tourne sur Mac M1 (MPS), la cible est un Jetson (TensorRT, aarch64). Réécrire le pipeline serait coûteux et risqué.

**Solution.** **Backend-agnostic dès le départ** :
- le détecteur est un `Protocol` ([`detect/base.py`](../anpr_poc/detect/base.py)) ;
- `load_detector(weights, backend="auto")` commute `torch`/`onnx`/`tensorrt` ;
- **aucun code Mac-only** dans le chemin d'inférence ;
- chemin d'export ONNX prêt ([`detect/export.py`](../anpr_poc/detect/export.py)), shapes fixes → TensorRT direct.

Passage Mac → Jetson = changer l'exécuteur, pas la logique. Détail : [Architecture § portabilité](ARCHITECTURE.md#portabilité).

---

## P5 — Résolution / flou de mouvement

**Problème.** Une plaque trop petite ou floue est illisible, quel que soit l'OCR.

**Ce qu'on a mesuré** (même véhicule, même scène, deux résolutions) :

| Source | Taille plaque | Résultat OCR |
|--------|---------------|--------------|
| 640 × 360 | ~90 px de large | ❌ illisible — au mieux `5210` partiel (score 0.71) |
| 1280 × 720 | ~180 px de large | ✅ `GX-521-EW` **complète**, confiance 0.99, confirmée par le pipeline |

**Solution = exigence matérielle chiffrée**, à imposer au déploiement :
- **≥ 1080p** sur le champ utile ;
- **plaque ≥ 120–150 px** de large dans le cadre ;
- **obturateur rapide** (anti-flou) — la scène cible « camion franchissant une ligne » est plus favorable qu'une caméra mobile ;
- **angle maîtrisé** + homographie pré-calibrée pour compenser le biais.

> C'est un livrable en soi : le POC démontre que **la qualité du capteur/placement est la variable dominante**, avant même le choix des modèles.

---

## P6 — Fragmentation de tracking

**Problème.** Un même véhicule peut recevoir **plusieurs `tracker_id`** (occlusion, changement d'apparence, mouvement rapide) → plusieurs événements pour une seule plaque.

**Solution.** Anti-doublon inter-tracks dans `ConfirmBuffer` : une plaque déjà émise dans `dedup_window_sec` supprime les ré-émissions, même sur un `tracker_id` différent.

**Preuve.** Avant correctif : clip Volvo → **2 événements** (`GX-521-E` sur le track #1, `GX-521-EW` sur le track #3). Après correctif (dédup + validation stricte qui rejette le partiel) : **1 seul événement** `GX-521-EW`, conf 0.99. Verrouillé par 2 tests (`test_dedup_*`).

---

## P7 — Plusieurs véhicules simultanés

**Problème.** Le trafic réel présente plusieurs plaques dans la même image.

**Solution.** Multi-plaque natif : un buffer par `tracker_id`, votes et debounces indépendants, dédup par chaîne de plaque (pas globale). Détail : [Pipeline § multi-plaque](PIPELINE.md#traitement-multi-plaque).

**Preuve.** Clip autoroute 1080p (caméra fixe) : **5 plaques UK confirmées en 5 s**, jusqu'à 3 boîtes simultanées correctement séparées :
```
GX15 OGJ · MW51 VSU · NA13 NRU · AP05 JEO · LM13 VCV · KH05 ZZK
```

---

## P8 — Euroband lu comme des caractères

**Problème.** La bande bleue UE (lettre pays + étoiles) est lue par l'OCR comme `F`, `D`, `NL`… collés à la plaque.

**Solution.** `euroband_strip(crop, frac=0.11)` retire ~11 % à gauche avant OCR. La fraction est configurable (`euroband_strip_frac`). Fonction miroir `read_country_letter()` pour, plus tard, router la validation par pays via la lettre lue.

📍 [`ocr/preprocess.py`](../anpr_poc/ocr/preprocess.py).

---

## P9 — Alignement annotation / coordonnées OCR

**Problème rencontré.** En mode démo, les boîtes annotées apparaissaient **~70 px sous la plaque**.

**Diagnostic.** Le pipeline PP-OCRv6 applique par défaut un **dé-warp document** (`doc_unwarping` + orientation) : les coordonnées renvoyées sont dans l'espace *dé-warpé*, pas dans l'image d'origine.

**Solution.** Désactiver `use_doc_unwarping` / `use_doc_orientation_classify`. Bonus : deux modèles en moins → inférence plus rapide. De plus, la démo dessine sur la **boîte OCR brute de la frame** (position exacte), pas sur la boîte Kalman prédite qui « traîne » derrière un véhicule rapide.

**Preuve.** Après correctif : boîte `#4 GX-521-EW` **exactement sur la plaque**, label calé juste au-dessus.

> Cas d'école du POC : un défaut de *coordonnées* peut se déguiser en défaut de *modèle*. Toujours superposer la boîte brute sur l'image source pour trancher.

---

[← Pipeline](PIPELINE.md) · [Risques restants →](RISQUES.md)
