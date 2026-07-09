# 🛠️ Installation

Procédure complète, reproductible, testée sur **macOS Apple Silicon (M1)**.

[← Retour README](../README.md) · [Guide de test →](GUIDE_TEST.md) · [Architecture](ARCHITECTURE.md) · [Pipeline](PIPELINE.md)

---

## Sommaire

- [Prérequis](#prérequis)
- [Installation pas à pas](#installation-pas-à-pas)
- [Vérification](#vérification)
- [Environnement de référence](#environnement-de-référence)
- [Dépannage](#dépannage)
- [Désinstallation](#désinstallation)

---

## Prérequis

| Outil | Version | Pourquoi | Vérifier |
|-------|---------|----------|----------|
| **Python** | **≥ 3.10** | Le code utilise les unions `X \| None` évaluées par pydantic → **échoue en 3.9** | `python3.13 --version` |
| **ffmpeg** | ≥ 6 | Sonder les vidéos, extraire des frames pour vérifier | `ffmpeg -version` |
| **git** | — | Cloner le dépôt | `git --version` |
| **Homebrew** | — | Installer Python/ffmpeg sur Mac | `brew --version` |

> ⚠️ **Le `python3` système de macOS est en 3.9** → incompatible. Installez un Python récent :
> ```bash
> brew install python@3.13 ffmpeg
> ```

---

## Installation pas à pas

### 1. Cloner

```bash
git clone https://github.com/JordanLacroix/plate-recognition.git
cd plate-recognition
```

### 2. Créer un environnement virtuel Python 3.10+

```bash
python3.13 -m venv .venv
source .venv/bin/activate            # zsh/bash ; (Windows : .venv\Scripts\activate)
```

### 3. Installer

Deux niveaux selon ce que vous voulez faire.

<details open>
<summary><b>A. Complet (pipeline + démo + dev)</b> — recommandé</summary>

```bash
pip install -e ".[torch,dev]"
```

Installe : cœur (numpy, opencv, supervision, paddleocr + paddlepaddle, onnxruntime, pydantic, pyyaml), le backend torch (MPS) et les outils dev (pytest, ruff, mypy).
</details>

<details>
<summary><b>B. Minimal — juste les tests du cœur (sans modèle)</b></summary>

Le cœur de confirmation ne dépend que de numpy + pydantic + pyyaml :

```bash
pip install numpy pyyaml pydantic pytest
pytest tests/ -q                     # 34 passed
```

Idéal pour valider la logique sans télécharger PaddleOCR ni torch.
</details>

> **paddlepaddle** est lourd (~plusieurs centaines de Mo) et propre à la plateforme.
> Sur **Jetson (aarch64)**, ne pas l'installer depuis PyPI : utiliser les wheels de
> `pypi.jetson-ai-lab.io` (cf. [Architecture § portabilité](ARCHITECTURE.md#portabilité)).

### 4. (Optionnel) Poids du détecteur plaque

Le détecteur n'est **pas encore entraîné** (cf. [Risques § R1](RISQUES.md#r1--détecteur-plaque-non-entraîné-bloqueur)).
Pour le pipeline réel, placez un `.onnx`/`.pt` dans `weights/` (hors dépôt, gitignoré). En attendant, utilisez la **démo bootstrap** ([Guide de test](GUIDE_TEST.md)).

---

## Vérification

```bash
# 1. Version Python correcte (≥ 3.10)
python --version

# 2. Cœur : tests unitaires (aucun modèle requis)
python -m pytest tests/ -q
# → attendu : 34 passed

# 3. Config réelle chargée
python -c "from anpr_poc.config import load_config; c=load_config('config'); \
print('OK', c.thresholds.k_consensus, c.formats.regex_by_country['FR'])"
# → OK 3 ^[A-Z]{2}-\d{3}-[A-Z]{2}$

# 4. Tout le paquet compile
python -m compileall -q anpr_poc demo eval && echo "compile OK"
```

Les 4 verts ⇒ installation saine. Pour aller plus loin : **[Guide de test](GUIDE_TEST.md)**.

---

## Environnement de référence

Versions réellement validées pendant le POC (macOS M1, arm64) :

| Paquet | Version testée |
|--------|----------------|
| Python | 3.13.11 (arm64) |
| numpy | 2.3.5 |
| opencv-python-headless | 4.10.0 |
| supervision | 0.29.1 |
| paddleocr | 3.7.0 |
| paddlepaddle | 3.3.1 |
| pydantic | 2.13.4 |
| pyyaml | 6.0.2 |
| ffmpeg | 8.0.1 |

---

## Dépannage

<details>
<summary><b>Erreur pydantic <code>Unable to evaluate type annotation 'list[...] | None'</code></b></summary>

Vous êtes en **Python 3.9** (le `python3` système de macOS). Les unions `|` ne sont pas
évaluables par pydantic en 3.9. Recréez le venv avec un Python ≥ 3.10 :
```bash
brew install python@3.13
python3.13 -m venv .venv && source .venv/bin/activate
```
</details>

<details>
<summary><b><code>ModuleNotFoundError: No module named 'paddle'</code></b></summary>

`paddleocr` ne tire pas `paddlepaddle` automatiquement. Installez-le :
```bash
pip install "paddlepaddle>=3,<4"
```
(déjà inclus par `pip install -e .`).
</details>

<details>
<summary><b>Au 1er run, PaddleOCR télécharge des modèles / <code>Checking connectivity to the model hosters…</code></b></summary>

Normal : PP-OCRv6 récupère ses poids une fois puis les met en cache
(`~/.paddlex/official_models`). Pour couper le contrôle de connectivité :
```bash
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
```
(la démo le positionne déjà elle-même).
</details>

<details>
<summary><b><code>UserWarning: No ccache found</code></b></summary>

Avertissement inoffensif de paddlepaddle. Optionnel : `brew install ccache`.
</details>

<details>
<summary><b><code>FutureWarning: ByteTrack was deprecated since v0.28</code></b></summary>

`supervision.ByteTrack` sera retiré en 0.30. Le pin `supervision<0.30` du
`pyproject.toml` protège le build. Migration à planifier (cf. [Risques § R9](RISQUES.md#r9--dépréciation-bytetrack-supervision)).
</details>

<details>
<summary><b>La commande <code>pytest</code> échoue via un proxy/hook, mais <code>python -m pytest</code> marche</b></summary>

Si un hook shell réécrit vos commandes, préférez toujours la forme module :
```bash
python -m pytest tests/ -q
```
</details>

<details>
<summary><b>Vérifier le contrôle de licences en local</b></summary>

```bash
pip install pip-licenses
bash scripts/check_licenses.sh    # échoue si AGPL / GPL fort ; tolère LGPL documentées
```
Même contrôle qu'en CI ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)).
</details>

<details>
<summary><b>Faire tourner le vrai pipeline sans détecteur entraîné</b></summary>

Backend `stub` (détecteur factice + OCR réel) → `anpr_poc.run` s'exécute end-to-end :
```bash
python -m anpr_poc.run data/clips/mon_clip.mp4 --backend stub --out out/events.jsonl
```
Détail : [Guide de test § Niveau 3a](GUIDE_TEST.md#3a-avec-le-détecteur-factice-tourne-aujourdhui).
</details>

---

## Désinstallation

```bash
deactivate 2>/dev/null
rm -rf .venv
# cache modèles PaddleOCR (optionnel)
rm -rf ~/.paddlex
```

---

[← README](../README.md) · [Guide de test →](GUIDE_TEST.md)
