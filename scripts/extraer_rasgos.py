"""Extracción paralela y reanudable de rasgos (base y ampliados) para una lista de registros WFDB.

Uso: python extraer_rasgos.py <lista.csv> <dir_base> <salida.csv> [n_procesos]
La lista debe tener la columna registro (ruta relativa sin extensión). Cada 200 registros se
agrega un lote a la salida (punto de control). Al reanudar se omiten los registros ya
procesados y se reintentan los que terminaron en error.
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd
import wfdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rasgos  # noqa: E402

BASE = None
ALIAS_V1 = ["V1", "V", "MCL1", "V1_equiv"]


def indices_derivaciones(nombres):
    idx = []
    for l in ["I", "II", "III"]:
        idx.append(nombres.index(l))
    v = next((n for n in ALIAS_V1 if n in nombres), None)
    idx.append(nombres.index(v) if v else 3)
    return idx


def procesar(reg):
    try:
        rec = wfdb.rdrecord(os.path.join(BASE, reg))
        fs = rec.fs
        sig = rec.p_signal[: int(10 * fs), indices_derivaciones(rec.sig_name)]
        if np.any(np.isnan(sig)) or np.any(np.ptp(sig, axis=0) == 0):
            return {"registro": reg, "estado": "derivacion_plana"}
        f = rasgos.rasgos_registro(sig, fs)
        if f is None:
            return {"registro": reg, "estado": "pocos_picos"}
        f.update({"registro": reg, "estado": "ok"})
        return f
    except Exception as e:  # registro corrupto o incompleto
        return {"registro": reg, "estado": f"error:{type(e).__name__}"}


def init(base):
    global BASE
    BASE = base


def main(lista, base, salida, nproc=7):
    regs = pd.read_csv(lista)["registro"].tolist()
    hechos = set()
    if os.path.exists(salida):
        prev = pd.read_csv(salida, usecols=["registro", "estado"], on_bad_lines="skip").drop_duplicates("registro", keep="last")
        hechos = set(prev.loc[~prev.estado.astype(str).str.startswith("error"), "registro"])
    pend = [r for r in regs if r not in hechos and os.path.exists(os.path.join(base, r + ".hea")) and any(
        os.path.exists(os.path.join(base, r + ext)) for ext in (".mat", ".dat"))]
    print(f"Pendientes: {len(pend)} de {len(regs)}", flush=True)
    cols = None
    if os.path.exists(salida):
        cols = pd.read_csv(salida, nrows=0).columns.tolist()
    lote = []
    with Pool(nproc, initializer=init, initargs=(base,)) as pool:
        for i, fila in enumerate(pool.imap_unordered(procesar, pend, chunksize=8), 1):
            lote.append(fila)
            if len(lote) >= 200 or i == len(pend):
                df = pd.DataFrame(lote)
                if cols is None:
                    nombres = [f"{l}_{k}" for l in rasgos.LEADS for k in rasgos.BASE_NAMES + rasgos.EXT_NAMES]
                    cols = ["registro", "estado"] + nombres
                df = df.reindex(columns=cols)
                df.to_csv(salida, mode="a", header=not os.path.exists(salida), index=False)
                lote = []
                print(time.strftime("%H:%M:%S"), f"{i}/{len(pend)}", flush=True)
    print("LISTO", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 7)
