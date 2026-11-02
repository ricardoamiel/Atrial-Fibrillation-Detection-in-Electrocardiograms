#!/usr/bin/env bash
# Descarga desde el espejo abierto de PhysioNet en AWS (physionet-open).
# Paso 1: cabeceras de ecg-arrhythmia y tabla de PTB-XL. Uso: bash descargar_s3.sh <dir_data>
set -euo pipefail
D="$1"; S3="https://physionet-open.s3.amazonaws.com"
mkdir -p "$D/ecg-arrhythmia" "$D/ptb-xl"
cd "$D/ecg-arrhythmia"
curl -s "$S3/ecg-arrhythmia/1.0.0/SHA256SUMS.txt" -o SHA256SUMS.txt
curl -s "$S3/ecg-arrhythmia/1.0.0/ConditionNames_SNOMED-CT.csv" -o ConditionNames_SNOMED-CT.csv
awk '{print $2}' SHA256SUMS.txt | grep '\.hea$' > lista_hea.txt
wc -l lista_hea.txt
cat lista_hea.txt | xargs -P 96 -I{} sh -c '[ -s "{}" ] || { mkdir -p "$(dirname "{}")"; curl -s --retry 5 -o "{}" "'"$S3"'/ecg-arrhythmia/1.0.0/{}"; }'
cd "$D/ptb-xl"
curl -s "$S3/ptb-xl/1.0.3/ptbxl_database.csv" -o ptbxl_database.csv
curl -s "$S3/ptb-xl/1.0.3/scp_statements.csv" -o scp_statements.csv
echo "S3 CABECERAS LISTAS"
