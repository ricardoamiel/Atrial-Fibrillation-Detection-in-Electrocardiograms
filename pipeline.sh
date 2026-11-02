#!/usr/bin/env bash
# Flujo completo y reanudable del proyecto. Cada paso omite el trabajo ya hecho, de modo que
# puede interrumpirse (apagar la laptop, Ctrl+C) y volver a lanzarse con: bash pipeline.sh
# Los registros de cada paso quedan en logs/ y el avance general en logs/pipeline.log.
set -uo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
mkdir -p logs resultados
exec 9>logs/.pipeline.lock
flock -n 9 || { echo "Ya hay una ejecución en curso"; exit 1; }
msg() { echo "$(date '+%F %T') $*" | tee -a logs/pipeline.log; }
S3=https://physionet-open.s3.amazonaws.com
PN=https://physionet.org/files/challenge-2021/1.0.3

msg "1. Cabeceras de Chapman/Ningbo (AWS)"
[ -s data/ecg-arrhythmia/lista_hea.txt ] || { mkdir -p data/ecg-arrhythmia; curl -s "$S3/ecg-arrhythmia/1.0.0/SHA256SUMS.txt" | awk '{print $2}' | grep '\.hea$' > data/ecg-arrhythmia/lista_hea.txt; }
$PY -I scripts/descargar_lista.py "$S3/ecg-arrhythmia/1.0.0" data/ecg-arrhythmia/lista_hea.txt data/ecg-arrhythmia 64 >> logs/descargas.log 2>&1
mkdir -p data/ptb-xl
for f in ptbxl_database.csv scp_statements.csv; do [ -s data/ptb-xl/$f ] || curl -s "$S3/ptb-xl/1.0.3/$f" -o data/ptb-xl/$f; done

msg "2. Cabeceras de CPSC, Georgia y PTB (physionet.org, 4 hilos)"
$PY -I scripts/descargar_lista.py "$PN" data/physionet2021/lista_hea.txt data/physionet2021 4 >> logs/descargas.log 2>&1

msg "3. Etiquetado"
$PY -I scripts/physionet_etiquetas.py "$PWD/data" data/etiquetas_publicas.csv >> logs/etiquetas.log 2>&1
grep "^ecg-arrhythmia/" data/etiquetas_publicas.csv | cut -d, -f1 | sed 's|^ecg-arrhythmia/||; s|$|.mat|' > data/ecg-arrhythmia/lista_mat.txt
grep "^ptb-xl/" data/etiquetas_publicas.csv | cut -d, -f1 | sed 's|^ptb-xl/||' | awk '{print $0".hea"; print $0".dat"}' > data/ptb-xl/lista.txt
grep "^physionet2021/" data/etiquetas_publicas.csv | cut -d, -f1 | sed 's|^physionet2021/||; s|$|.mat|' > data/physionet2021/lista_mat.txt

msg "4. Señales (AWS y physionet.org)"
$PY -I scripts/descargar_lista.py "$S3/ecg-arrhythmia/1.0.0" data/ecg-arrhythmia/lista_mat.txt data/ecg-arrhythmia 64 >> logs/descargas.log 2>&1
$PY -I scripts/descargar_lista.py "$S3/ptb-xl/1.0.3" data/ptb-xl/lista.txt data/ptb-xl 64 >> logs/descargas.log 2>&1
$PY -I scripts/descargar_lista.py "$PN" data/physionet2021/lista_mat.txt data/physionet2021 4 >> logs/descargas.log 2>&1

msg "5. Rasgos de Kingston"
KIN=kingston-icu-af-dataset-1.0.0
$PY -c "import pandas as pd; m=pd.read_csv('data/$KIN/metadata.csv'); pd.DataFrame({'registro':'$KIN/'+m.ECG}).to_csv('data/lista_kingston.csv',index=False)"
$PY -I scripts/extraer_rasgos.py data/lista_kingston.csv "$PWD/data" data/rasgos_kingston.csv 7 >> logs/rasgos_kingston.log 2>&1

msg "6. Rasgos de los datos públicos"
$PY -I scripts/extraer_rasgos.py data/etiquetas_publicas.csv "$PWD/data" data/rasgos_publicos.csv 7 >> logs/rasgos_publicos.log 2>&1

msg "7. Experimentos (puntos de control en resultados/pred)"
$PY -I scripts/experimentos.py >> logs/experimentos_stdout.log 2>&1 || { msg "Error en experimentos, ver logs/experimentos.log"; exit 1; }

msg "8. Cuaderno"
$PY -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 reproduccion_fa_uci.ipynb >> logs/cuaderno.log 2>&1 \
  && msg "FLUJO COMPLETO" || msg "Error al ejecutar el cuaderno, ver logs/cuaderno.log"
