"""Etiquetado de los datos públicos en ritmo sinusal (0) y fibrilación o aleteo auricular (1).

Fuentes, todas parte de la competencia PhysioNet/CinC 2021:
1. ecg-arrhythmia (Chapman/Shaoxing y Ningbo), cabeceras con códigos SNOMED, desde AWS.
2. PTB-XL, con códigos SCP de ptbxl_database.csv, desde AWS.
3. CPSC 2018, CPSC 2018 Extra, Georgia y PTB, desde physionet2021/training (si están).

Sigue el criterio de Nassar et al.: se descartan registros con ambas clases, con etiquetas no
usadas en el conjunto UCI (marcapasos, bigeminia, trigeminia, taquicardia y fibrilación
ventricular, otras taquicardias y otras bradicardias), con menos de 10 s o sin I, II, III y V1.
Uso: python physionet_etiquetas.py <dir_data> <salida.csv>
"""
import ast
import os
import sys

import pandas as pd

SR = {"426783006", "426177001", "427084000", "427393009"}
AF = {"164889003", "164890007", "195080001", "426749004", "314208002"}
EXCL = {"10370003", "251268003", "251266004",                     # marcapasos
        "251173003", "11157007", "251168009", "251180001",        # bigeminia y trigeminia
        "164895002", "425856008", "164896001", "111288001",        # taquicardia y fibrilación ventricular
        "713422000", "426648003", "67198005", "426761007", "251166008", "233897008",  # otras taquicardias
        "426627000"}                                              # otras bradicardias
SCP_SR = {"SR", "SBRAD", "STACH", "SARRH"}
SCP_AF = {"AFIB", "AFLT"}
SCP_EXCL = {"PACE", "BIGU", "TRIGU", "SVTAC", "PSVT", "SVARR"}
FUENTE = {"cpsc_2018": "CPSC_2018 & CPSC_2018_Extra", "cpsc_2018_extra": "CPSC_2018 & CPSC_2018_Extra",
          "georgia": "Georgia", "ptb": "PTB & PTB-XL"}
LEADS = ["I", "II", "III", "V1"]


def leer_cabecera(path):
    with open(path) as f:
        lineas = f.read().splitlines()
    _, nsig, fs, n = lineas[0].split()[:4]
    nsig = int(nsig)
    sig = [l.split()[-1] for l in lineas[1:1 + nsig]]
    dx = next((l.split(":", 1)[1].strip() for l in lineas if l.replace(" ", "").startswith("#Dx")), "")
    return float(fs), int(n), sig, set(dx.split(","))


def etiqueta_snomed(dx):
    sr, af = bool(dx & SR), bool(dx & AF)
    if sr == af or dx & EXCL:
        return None
    return int(af)


def desde_cabeceras(base, carpeta, fuente_fn):
    filas = []
    for raiz, _, archivos in os.walk(os.path.join(base, carpeta)):
        for a in archivos:
            if not a.endswith(".hea"):
                continue
            p = os.path.join(raiz, a)
            try:
                fs, n, sig, dx = leer_cabecera(p)
            except Exception:
                continue
            y = etiqueta_snomed(dx)
            if y is None or n < 10 * fs or not all(l in sig for l in LEADS):
                continue
            rel = os.path.relpath(p, base)[:-4]
            fu = fuente_fn(rel)
            if fu is None:
                continue
            filas.append({"registro": rel, "fuente": fu, "fs": fs, "AF": y})
    return filas


def desde_ptbxl(base):
    d = pd.read_csv(os.path.join(base, "ptb-xl", "ptbxl_database.csv"))
    filas = []
    for _, r in d.iterrows():
        c = set(ast.literal_eval(r.scp_codes))
        sr, af = bool(c & SCP_SR), bool(c & SCP_AF)
        if sr == af or c & SCP_EXCL or isinstance(r.pacemaker, str):
            continue
        filas.append({"registro": "ptb-xl/" + r.filename_hr, "fuente": "PTB & PTB-XL", "fs": 500.0, "AF": int(af)})
    return filas


def main(base, salida):
    filas = desde_cabeceras(base, "ecg-arrhythmia", lambda rel: "Chapman/Shaoxing & Ningbo")
    filas += desde_ptbxl(base)
    filas += desde_cabeceras(base, "physionet2021/training",
                             lambda rel: FUENTE.get(rel.split(os.sep)[2]))
    df = pd.DataFrame(filas).drop_duplicates("registro").sort_values("registro")
    df.to_csv(salida, index=False)
    print(df.groupby("fuente")["AF"].agg(["count", "mean"]).round(3))
    print("Total", len(df), "prevalencia", round(df.AF.mean(), 3))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
