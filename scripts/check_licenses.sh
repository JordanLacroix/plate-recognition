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

# Exceptions LGPL revues et acceptées (usage dynamique, non modifiées).
# crc32c (LGPLv2+), python-bidi (LGPL) : tirées transitivement par paddleocr/paddlepaddle.
LGPL_OK='crc32c|python-bidi'

echo "== Arbre de licences =="
pip-licenses --format=plain --with-system --order=license

echo
echo "== Recherche de licences interdites (hors exceptions LGPL revues) =="
# On liste les lignes GPL-like, on retire les LGPL (Lesser) et les exceptions connues.
hits=$(pip-licenses --format=plain --with-system \
  | grep -iE "$FORBIDDEN" \
  | grep -ivE 'Lesser|Library' \
  | grep -ivE "$LGPL_OK" || true)

if [[ -n "$hits" ]]; then
  echo "❌ Licence interdite détectée :"
  echo "$hits"
  exit 1
fi

echo "✅ Aucune AGPL / GPL fort. (LGPL tolérées : crc32c, python-bidi — usage dynamique)"
