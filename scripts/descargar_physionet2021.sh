#!/usr/bin/env bash
# Descarga de physionet.org de los subconjuntos de PhysioNet/CinC 2021 que no están en AWS
# (CPSC 2018, CPSC 2018 Extra, Georgia y PTB). Pocas conexiones para no exceder el límite del servidor.
# Uso: bash descargar_physionet2021.sh <dir_physionet2021>
set -euo pipefail
DEST="$1"; BASE="https://physionet.org/files/challenge-2021/1.0.3"; P=4
SCR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DEST"; cd "$DEST"
curl -s "$BASE/RECORDS" -o RECORDS_dirs
: > lista_registros.txt
grep -E "cpsc_2018|georgia|/ptb/" RECORDS_dirs | while read -r d; do
  curl -s "$BASE/$d/RECORDS" | sed "s|^|$d|" >> lista_registros.txt
done
wc -l lista_registros.txt
cat lista_registros.txt | xargs -P $P -I{} sh -c 'f="{}.hea"; [ -s "$f" ] || { mkdir -p "$(dirname "$f")"; curl -s --retry 5 -o "$f" "'"$BASE"'/$f"; }'
echo "CABECERAS LISTAS"
# Señales solo de los registros etiquetados como sinusal o fibrilación
"$SCR/../.venv/bin/python" -I "$SCR/physionet_etiquetas.py" "$DEST/.." "$DEST/etiquetas_tmp.csv" > /dev/null
grep "physionet2021/" "$DEST/etiquetas_tmp.csv" | cut -d, -f1 | sed 's|^physionet2021/||' | xargs -P $P -I{} sh -c 'f="{}.mat"; [ -s "$f" ] || curl -s --retry 5 -o "$f" "'"$BASE"'/$f"'
echo "MAT LISTOS"
