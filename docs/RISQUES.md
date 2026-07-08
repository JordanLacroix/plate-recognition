# 🎯 Risques restants & dette

Honnête inventaire de ce qui **n'est pas** encore traité. Classé par criticité. À lire avant tout jugement « prêt pour la prod ».

[← Problématiques](PROBLEMATIQUES.md) · [Retour README](../README.md) · [Roadmap →](ROADMAP.md)

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
| [R12](#r12--contrôle-de-licences-non-automatisé) | Contrôle de licences non automatisé | 🔵 | Conformité |

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

Sur site, il faut : capturer la vue réelle, calibrer l'homographie (4 points plaque connus), tracer la ROI et la ligne de franchissement. Tant que non fait, le trigger et le redressement ne valent rien.

---

## R5 — Conformité RGPD 🟠

Une plaque d'immatriculation est une **donnée à caractère personnel** (RGPD, en France : cadre CNIL). Le POC n'adresse rien de tout ça :
- base légale du traitement, information des personnes, durée de conservation ;
- minimisation (faut-il stocker le snapshot ? le flou du reste de l'image ?) ;
- sécurité et journalisation des accès ;
- éventuelle DPIA (analyse d'impact) selon l'usage.

**À cadrer avant toute mise en service réelle**, pas après. Un ingénieur sérieux bloquera ici si ce n'est pas anticipé.

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

Identifiants caméra RTSP, chiffrement du flux, protection des snapshots (qui contiennent des plaques = données perso), contrôle d'accès aux sorties. Non traité.

---

## R12 — Contrôle de licences non automatisé 🔵

La contrainte « MIT/Apache uniquement, zéro AGPL » est **documentée mais pas exécutable**. Un `pip-licenses` en CN/CI qui échoue à la moindre AGPL rendrait la garantie automatique. Bon marché, forte valeur.

---

## Synthèse pour décision

- **Ce qui marche et est prouvé** : le cœur de confirmation (multi-frames, vote, dédup, validation par pays), le multi-plaque, la portabilité par conception, l'exigence de résolution chiffrée.
- **Le seul vrai bloqueur technique** : R1 (détecteur à entraîner) — tout le reste en dépend pour être mesuré.
- **Les vrais bloqueurs de mise en service** : R3 (temps réel), R4 (calibration), R5 (RGPD).
- **Le reste** : dette gérable en itération, tracée ici.

👉 Toutes ces lignes sont converties en tâches cochables dans **[ROADMAP.md](ROADMAP.md)**.

---

[← Problématiques](PROBLEMATIQUES.md) · [Roadmap →](ROADMAP.md)
