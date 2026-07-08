# data/

Clips réels + crops annotés. **Lourds -> hors git** (voir `.gitignore`).

- `clips/` — passages camions filmés (vue fixe). 3-4 passages pour bootstrap.
- `crops/` — ~100-300 crops plaque annotés (fine-tune détecteur).
- `ground_truth.json` — vérité-terrain par clip pour `eval/harness.py` : `{ "clip.mp4": "AB-123-CD" }`.

Bootstrap annotation : détection texte générique pour pré-cropper avant annotation manuelle.
