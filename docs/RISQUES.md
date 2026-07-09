# 🎯 Risques restants & dette

Honnête inventaire de ce qui **n'est pas** encore traité. Classé par criticité. À lire avant tout jugement « prêt pour la prod ».

[← Problématiques](PROBLEMATIQUES.md) · [Retour README](../README.md) · [Roadmap →](ROADMAP.md)

---

## ✅ Déjà corrigé (historisé pour transparence)

### Itération « avocat du diable » — trous cachés dans le pipeline

| Trou trouvé | Correctif | Preuve |
|-------------|-----------|--------|
| Wrapper OCR `paddle_reco.py` codait l'API PaddleOCR **2.x** (morte) | Réécrit en **3.x** (`predict`, doc-unwarp off) | `anpr_poc.run --backend stub` tourne |
| Le **vrai pipeline** n'avait jamais tourné | Ajout `StubDetector` + backend `stub` | émet `GX150GJ` end-to-end |
| Aucun **test d'intégration** (cœur vert, produit non câblé) | `tests/test_pipeline.py` (détecteur/OCR factices) | 3 tests bout-en-bout |
| **Fuite mémoire** : buffers des tracks non-émetteurs jamais purgés | `ConfirmBuffer.retain(active_ids)` chaque frame | `test_retain_evicts_inactive_tracks` |
| Dédup par **chaîne exacte** (laissait passer les quasi-doublons OCR) | Dédup par **distance d'édition ≤ 1** | `test_dedup_edit_distance_catches_near_miss` |
| Vote **fracturé** par les séparateurs (`GX-521-EW` vs `GX521EW`) | **Plaques canoniques** (alphanumérique) partout | regex sans séparateur + tests |
| `crossed` (franchissement) calculé puis **jeté** | Gate optionnel `require_line_crossing` câblé | `test_require_crossing_blocks_until_crossed` |
| Contrainte licence **non exécutée** | **CI** `pip-licenses` + `scripts/check_licenses.sh` | échoue sur AGPL/GPL |

### Itération « durcissement CI/CD & qualité »

| Trou trouvé | Correctif | Preuve |
|-------------|-----------|--------|
| **Claim `python 3.10+` non vérifié** (CI en 3.12 seul) | Matrice CI **3.10 · 3.11 · 3.12 · 3.13** | 4 jobs verts |
| Job tests dodgeait les **vraies deps** (liste triée à la main) | Job `integration` : `pip install -e .` + smoke import + tests | job vert |
| **Couverture** non mesurée | `pytest-cov`, seuil **90 %** (actuel 94 %) | job tests |
| **Formatage** non vérifié | `ruff format --check` en CI | job lint |
| Aucun **scan de secrets** | Gitleaks (historique complet) | job `secrets` |
| Pas de **SBOM** ni build vérifié | `python -m build` + `twine check` + CycloneDX | job `build` |
| Sécurité **CI/CD** absente | moindre privilège, `pip-audit`, CodeQL, Dependabot, `SECURITY.md` | 11 jobs CI |
| `Event.snapshot_path` **champ mort** | Snapshots de preuve (fond flouté RGPD), `--snapshots-dir` | `test_snapshot_*` |
| Config foireuse passait **silencieusement** | Validation fail-fast (ROI, homographie 3×3 inversible) | `test_config.py` |
| mypy **strict jamais exécuté** (15 erreurs latentes) | mypy strict en CI, 0 erreur | job lint |

**Bilan tests : 11 → 34 · couverture 94 % · CI 5 → 11 jobs.**

> Ce qui reste ci-dessous n'a **pas** encore été corrigé.

---

## Cotation

| Niveau | Sens |
|--------|------|
| 🔴 Bloqueur | Empêche un déploiement réel |
| 🟠 Majeur | Doit être traité avant mise en service |
| 🟡 Modéré | Impacte qualité/robustesse, gérable en itération |
| 🔵 Surveillance | Pas urgent mais à ne pas oublier |

---

## Sommaire des risques

| # | Risque | Niveau | Domaine |
|---|--------|--------|---------|
| [R1](#r1--détecteur-plaque-non-entraîné-bloqueur) | Détecteur plaque non entraîné | 🔴 | Modèle |
| [R2](#r2--confidences-ocr-par-caractère-approximées) | Confidences OCR par caractère approximées | 🟠 | OCR |
| [R3](#r3--débit-temps-réel-non-profilé) | Débit temps réel non profilé | 🟠 | Performance |
| [R4](#r4--calibration-terrain-manquante) | Calibration terrain (homographie, ROI) | 🟠 | Déploiement |
| [R5](#r5--conformité-rgpd) | Conformité RGPD | 🟠 | Légal |
| [R6](#r6--robustesse-du-flux-rtsp) | Robustesse du flux RTSP | 🟡 | Infra |
| [R7](#r7--conditions-difficiles-non-testées) | Nuit / pluie / contre-jour | 🟡 | Vision |
| [R8](#r8--persistance-des-événements) | Persistance des événements | 🟡 | Intégration |
| [R9](#r9--dépréciation-bytetrack-supervision) | Dépréciation ByteTrack (supervision) | 🟡 | Dépendance |
| [R10](#r10--seuils-empiriques-non-retunés) | Seuils empiriques non retunés | 🟡 | Réglage |
| [R11](#r11--sécurité-flux--stockage) | Sécurité flux & stockage | 🔵 | Sécurité |
| [R12](#r12--contrôle-de-licences-non-automatisé-corrigé) | Contrôle de licences non automatisé | ✅ | Conformité |
| [R13](#r13--routage-par-pays-non-câblé) | Routage de validation par pays non câblé | 🟡 | OCR |
| [R14](#r14--deux-dépendances-lgpl--une-licence-unknown) | 2 deps LGPL + 1 licence UNKNOWN | 🔵 | Conformité |

---

## R1 — Détecteur plaque non entraîné 🔴 **BLOQUEUR**

`TorchDetector` / `OnnxDetector` sont des **stubs** (`NotImplementedError`). Aucun poids plaque n'existe. Sans lui, le pipeline complet ne tourne pas ; la démo bootstrap utilise l'OCR générique en substitut (moins robuste, boîtes lâches).

**Ce qu'il faut :** filmer 3–4 passages réels, annoter ~100–300 crops plaque, fine-tuner LibreYOLO (ou RF-DETR-S), exporter ONNX. Voir [Roadmap § Jalon 1](ROADMAP.md#jalon-1--détecteur-plaque-le-bloqueur).

**Impact tant que non fait :** pas de mesure de performance réelle (précision, rappel, CER) possible.

---

## R2 — Confidences OCR par caractère approximées 🟠

PP-OCRv5 rend un score *par ligne*. On le **réplique** sur chaque caractère ([`ocr/paddle_reco.py`](../anpr_poc/ocr/paddle_reco.py)). Le vote pondéré est donc sous-optimal : un seul caractère douteux dans une lecture globalement sûre n'est pas dévalué comme il le devrait.

**Correctif visé :** exporter le modèle reco en ONNX et lire les **logits CTC** → vraie confiance par caractère → vote plus fin.

---

## R3 — Débit temps réel non profilé 🟠

En bootstrap CPU, PP-OCRv6 mesure **~0,7 à 2,5 s/frame** selon la densité. **Loin du temps réel** en l'état.

Leviers non encore actionnés :
- le **trigger ROI** (ne traiter que les frames avec véhicule dans la zone) — conçu, pas encore branché comme court-circuit CPU ;
- OCR **seulement sur le crop plaque** (détecteur dédié) au lieu de la frame entière ;
- accélération **ONNX + CoreML** (Mac) puis **TensorRT INT8/FP16** (Jetson).

**Aucun budget de latence cible n'est encore fixé** (frames/s à soutenir, nb véhicules simultanés). À définir avec le besoin métier.

---

## R4 — Calibration terrain manquante 🟠

- `homographie.json` = **matrice identité** → aucun redressement réel.
- `roi.json` = polygone/ligne **génériques** (valeurs 1280×720 arbitraires).

> **Garde-fou ajouté** : la config est désormais **validée au chargement** (fail-fast) — ROI ≥ 3 points, ligne non dégénérée, homographie 3×3 inversible. Ça empêche un déploiement avec une calibration syntaxiquement cassée, mais **ne remplace pas** la vraie calibration terrain (ci-dessous).

Sur site, il faut : capturer la vue réelle, calibrer l'homographie (4 points plaque connus), tracer la ROI et la ligne de franchissement. Tant que non fait, le trigger et le redressement ne valent rien.

---

## R5 — Conformité RGPD 🟠

Une plaque d'immatriculation est une **donnée à caractère personnel** (RGPD, en France : cadre CNIL). Le POC n'adresse rien de tout ça :
- base légale du traitement, information des personnes, durée de conservation ;
- minimisation (faut-il stocker le snapshot ? le flou du reste de l'image ?) ;
- sécurité et journalisation des accès ;
- éventuelle DPIA (analyse d'impact) selon l'usage.

**Amorce en place** : les snapshots de preuve floutent tout sauf la plaque (`--snapshots-dir`, minimisation/anonymisation). Mais l'essentiel du cadre RGPD (base légale, information, rétention, DPIA) reste **à cadrer avant toute mise en service réelle**, pas après. Un ingénieur sérieux bloquera ici si ce n'est pas anticipé.

---

## R6 — Robustesse du flux RTSP 🟡

[`VideoSource`](../anpr_poc/io/source.py) ouvre un flux et itère. **Aucune** gestion de : coupure réseau, reconnexion, drop de frames, décalage horloge, redémarrage caméra. Indispensable pour un flux 24/7.

---

## R7 — Conditions difficiles non testées 🟡

Testé uniquement en **plein jour, temps sec**. Non couvert : nuit / phares / IR, pluie, brouillard, contre-jour, plaque sale/pliée/partiellement masquée, deux-roues, plaques non-UE. Chacun peut dégrader fortement détection et OCR.

---

## R8 — Persistance des événements 🟡

Sorties actuelles : `jsonl` + log. Pas de base de données, pas d'idempotence garantie côté consommateur, pas d'API. À définir selon l'intégration SI cible (file de messages ? DB ? webhook ?).

---

## R9 — Dépréciation ByteTrack (supervision) 🟡

`supervision.ByteTrack` est **déprécié depuis la v0.28**, retrait annoncé en **v0.30**. Le code fonctionne mais il faut soit épingler `supervision<0.30`, soit migrer vers le tracker recommandé. À traiter avant qu'une mise à jour ne casse le build.

---

## R10 — Seuils empiriques non retunés 🟡

`conf_min=0.6`, `k_consensus=3`, `det_conf_min=0.4`, `dedup_window_sec=5.0` sont des **valeurs de départ raisonnables**, pas optimisées. Elles doivent être retunées sur données réelles via le harnais eval (compromis précision/rappel, taux de faux événements).

---

## R11 — Sécurité flux & stockage 🔵

**Sécurité CI/CD : traitée.** Voir [`SECURITY.md`](../SECURITY.md) — moindre privilège du `GITHUB_TOKEN`, `persist-credentials:false`, `pip-audit` (CVE deps), CodeQL (SAST), Dependabot, contrôle de licences.

**Sécurité runtime : non traitée.** Identifiants caméra RTSP, chiffrement du flux, protection des snapshots (plaques = données perso), contrôle d'accès aux sorties. Durcissement CI restant (SHA-pin des actions, scan de secrets, `pip-audit` bloquant) listé dans `SECURITY.md`.

---

## R12 — Contrôle de licences non automatisé ✅ *(corrigé)*

[`scripts/check_licenses.sh`](../scripts/check_licenses.sh) + job CI `licenses` échouent sur toute **AGPL / GPL fort** *et* sur toute licence **`UNKNOWN` non revue**. Reste un point de vigilance mineur : les motifs de noms de licences sont fragiles (dépendent du texte renvoyé par PyPI) — durcissement possible via une liste blanche stricte (`--allow-only`).

---

## R13 — Routage par pays non câblé 🟡

La validation de format est multi-pays, mais chaque `Read` a `country=None` → tout est validé avec `default_country`. La fonction [`read_country_letter()`](../anpr_poc/ocr/preprocess.py) (OCR de la lettre-pays euroband) **existe mais n'est jamais appelée**. Sur trafic **mixte** (FR + DE + IT…), tout serait validé comme FR → faux rejets/acceptations.

**Correctif visé :** OCR de la bande euroband → renseigner `Read.country` → validation par le bon pays. Voir [Roadmap backlog](ROADMAP.md#idées--améliorations-backlog-non-planifié).

---

## R14 — Deux dépendances LGPL + une licence UNKNOWN 🔵

L'audit `pip-licenses` ne trouve **aucune AGPL** (le vrai redline), mais :
- **`crc32c` (LGPLv2+)** et **`python-bidi` (LGPL)** — tirées transitivement par `paddleocr`/`paddlepaddle`. LGPL ≠ AGPL : acceptable en usage bibliothèque dynamique non modifiée, mais **pas strictement MIT/Apache** comme le proclame la contrainte. Listées comme exceptions revues dans `check_licenses.sh`.
- **`aistudio-sdk` : licence `UNKNOWN`** — à investiguer (probable Apache côté Baidu, à confirmer amont). Le contrôle CI **échoue désormais sur toute `UNKNOWN`** ; `aistudio-sdk` est explicitement **whitelisté** (`REVIEWED`) dans `check_licenses.sh` en attendant confirmation. Toute nouvelle `UNKNOWN` bloquera la CI.

Risque faible mais à trancher formellement avant mise en service (revue juridique légère).

---

## Synthèse pour décision

- **Ce qui marche et est prouvé** : le cœur de confirmation (multi-frames, vote, dédup edit-distance, validation par pays, gate franchissement, purge mémoire), le **pipeline réel end-to-end** (`--backend stub`, test d'intégration), le multi-plaque, la portabilité par conception, l'exigence de résolution chiffrée. **Socle qualité/CI solide** : 34 tests / couverture 94 %, matrice Python 3.10–3.13, lint+format+mypy strict, licences (AGPL+UNKNOWN), CVE, secrets, SBOM, CodeQL.
- **Le seul vrai bloqueur technique** : R1 (détecteur à entraîner) — tout le reste en dépend pour être mesuré.
- **Les vrais bloqueurs de mise en service** : R3 (temps réel), R4 (calibration), R5 (RGPD).
- **Le reste** : dette gérable en itération, tracée ici.

👉 Toutes ces lignes sont converties en tâches cochables dans **[ROADMAP.md](ROADMAP.md)**.

---

[← Problématiques](PROBLEMATIQUES.md) · [Roadmap →](ROADMAP.md)
