#!/usr/bin/env bash
# Contrôle de licences — rend la contrainte dure du projet EXÉCUTABLE.
#
# Redline projet : aucune AGPL, aucun GPL fort (copyleft contaminant pour du
# closed-source), aucun poids/lib non-commercial. LGPL toléré (usage bibliothèque
# dynamique) mais listé comme exception revue ci-dessous.
#
# Usage : bash scripts/check_licenses.sh   (nécessite pip-licenses dans l'env)
set -euo pipefail

# Licences interdites (motifs insensibles à la casse, recherche dans le nom de licence).
FORBIDDEN='AGPL|Affero|GPLv2\b|GPLv3\b|GNU General Public License'

# Exceptions revues et acceptées (paquets tiers triés à la main).
# - LGPL (usage bibliothèque dynamique) : crc32c (LGPLv2+), python-bidi (LGPL).
# - UNKNOWN triés : aistudio-sdk (métadonnées PyPI vides ; usage Baidu, à confirmer amont).
REVIEWED='crc32c|python-bidi|aistudio-sdk'

echo "== Arbre de licences =="
pip-licenses --format=plain --with-system --order=license

echo
echo "== 1) Licences interdites (AGPL / GPL fort), hors exceptions LGPL revues =="
forbidden_hits=$(pip-licenses --format=plain --with-system \
  | grep -iE "$FORBIDDEN" \
  | grep -ivE 'Lesser|Library' \
  | grep -ivE "$REVIEWED" || true)

echo "== 2) Licences UNKNOWN non revues =="
unknown_hits=$(pip-licenses --format=plain --with-system \
  | grep -iE '\bUNKNOWN\b' \
  | grep -ivE "$REVIEWED" || true)

fail=0
if [[ -n "$forbidden_hits" ]]; then
  echo "❌ Licence interdite détectée :"; echo "$forbidden_hits"; fail=1
fi
if [[ -n "$unknown_hits" ]]; then
  echo "❌ Licence UNKNOWN non revue (ajouter à REVIEWED après triage) :"; echo "$unknown_hits"; fail=1
fi
[[ "$fail" -eq 1 ]] && exit 1

echo "✅ Aucune AGPL / GPL fort ni UNKNOWN non revue."
echo "   Exceptions revues : crc32c, python-bidi (LGPL) · aistudio-sdk (UNKNOWN, à confirmer)."
