#!/usr/bin/env bash
# Descarga las señales (.mat) de los registros seleccionados en etiquetas_physionet.csv.
# Uso: bash descargar_mat.sh <dir_physionet2021>; puede repetirse, omite lo ya descargado.
set -euo pipefail
D="$1"; BASE="https://physionet.org/files/challenge-2021/1.0.3"
SCR="$(cd "$(dirname "$0")" && pwd)"
"$SCR/../.venv/bin/python" -I "$SCR/physionet_etiquetas.py" "$D" "$D/etiquetas_physionet.csv"
tail -n +2 "$D/etiquetas_physionet.csv" | cut -d, -f1 | xargs -P 24 -I{} sh -c 'f="'"$D"'/{}.mat"; [ -s "$f" ] || curl -s --retry 5 -o "$f" "'"$BASE"'/{}.mat"'
echo "MAT LISTOS"
