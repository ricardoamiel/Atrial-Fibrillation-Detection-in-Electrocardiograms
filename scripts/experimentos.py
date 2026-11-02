"""Experimentos de clasificación con puntos de control y registro.

Cada experimento (configuración, conjunto de rasgos, modelo) guarda sus probabilidades en
resultados/pred/<clave>.npy y una línea en resultados/metricas.csv. Si el punto de control
existe y fue entrenado con el mismo número de registros, se reutiliza; así la ejecución puede
interrumpirse y reanudarse en cualquier momento.

Uso: python experimentos.py   (corre la reproducción y la ablación completas)
"""
import json
import logging
import os
import sys
import time

import joblib
import numpy as np
import pandas as pd
from sklearn import metrics as M
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import MinMaxScaler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rasgos as R  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(RAIZ, "data")
RES = os.path.join(RAIZ, "resultados")
PRED = os.path.join(RES, "pred")
LOGS = os.path.join(RAIZ, "logs")
for d in (RES, PRED, LOGS):
    os.makedirs(d, exist_ok=True)
KIN = "kingston-icu-af-dataset-1.0.0"
SEMILLA = 0
MAX_SVM = 20000

log = logging.getLogger("experimentos")
if not log.handlers:
    log.setLevel(logging.INFO)
    fh = logging.FileHandler(os.path.join(LOGS, "experimentos.log"))
    fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log.addHandler(fh)

MODELOS = ["KNN", "MLP", "SVM", "LR", "RF", "LightGBM", "XGBoost", "CatBoost"]
MOD_AB = ["LR", "KNN", "CatBoost"]
BASE_COLS = [f"{l}_{k}" for l in R.LEADS for k in R.BASE_NAMES]
GRUPOS = {"Wavelet": [k for k in R.EXT_NAMES if k.startswith(("DWT", "Haar"))],
          "Radon": [k for k in R.EXT_NAMES if k.startswith("Radon")],
          "Espectro": [k for k in R.EXT_NAMES if k.startswith("Spec")]}


def cols_de(nombres):
    return [f"{l}_{k}" for l in R.LEADS for k in nombres]


CONJ = {"Base": ("base", BASE_COLS),
        "Base + Wavelet": ("wav", BASE_COLS + cols_de(GRUPOS["Wavelet"])),
        "Base + Radón": ("rad", BASE_COLS + cols_de(GRUPOS["Radon"])),
        "Base + Espectro": ("esp", BASE_COLS + cols_de(GRUPOS["Espectro"])),
        "Todos": ("todo", BASE_COLS + cols_de(R.EXT_NAMES))}


def modelo(nombre):
    from catboost import CatBoostClassifier
    from lightgbm import LGBMClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.svm import SVC
    from xgboost import XGBClassifier
    return {"KNN": lambda: KNeighborsClassifier(),
            "MLP": lambda: MLPClassifier(max_iter=1000, random_state=SEMILLA),
            "SVM": lambda: SVC(probability=True, random_state=SEMILLA, cache_size=4000),
            "LR": lambda: LogisticRegression(max_iter=5000),
            "RF": lambda: RandomForestClassifier(n_estimators=1000, n_jobs=-1, random_state=SEMILLA),
            "LightGBM": lambda: LGBMClassifier(n_estimators=1000, verbose=-1, random_state=SEMILLA),
            "XGBoost": lambda: XGBClassifier(n_estimators=1000, n_jobs=-1, random_state=SEMILLA),
            "CatBoost": lambda: CatBoostClassifier(iterations=1000, verbose=0, random_seed=SEMILLA)}[nombre]()


def leer_rasgos(nombre):
    f = pd.read_csv(os.path.join(DATA, nombre), on_bad_lines="skip")
    return f.drop_duplicates("registro", keep="last")


def cargar_datos():
    """Devuelve (publicos, kingston_entrenamiento, kingston_prueba) con etiquetas y rasgos."""
    pub = pd.read_csv(os.path.join(DATA, "etiquetas_publicas.csv"))
    fp = leer_rasgos("rasgos_publicos.csv")
    kin = pd.read_csv(os.path.join(DATA, KIN, "metadata.csv"))
    kl = pd.DataFrame({"registro": KIN + "/" + kin.ECG, "AF": (kin.Rhythm != "SINUS").astype(int),
                       "particion": kin.TrainOrTest.str.lower()})
    fk = leer_rasgos("rasgos_kingston.csv")
    Xp = pub.merge(fp[fp.estado == "ok"], on="registro")
    Xk = kl.merge(fk[fk.estado == "ok"], on="registro")
    return Xp, Xk[Xk.particion == "train"], Xk[Xk.particion == "test"]


def metricas(y, p, u=0.5):
    yh = (p >= u).astype(int)
    tn, fp_, fn, tp = M.confusion_matrix(y, yh, labels=[0, 1]).ravel()
    return {"AUROC": M.roc_auc_score(y, p), "AUPRC": M.average_precision_score(y, p),
            "LogLoss": M.log_loss(y, np.clip(p, 1e-7, 1 - 1e-7), labels=[0, 1]), "Brier": M.brier_score_loss(y, p),
            "Recall": M.recall_score(y, yh, zero_division=0), "Precision": M.precision_score(y, yh, zero_division=0),
            "F1": M.f1_score(y, yh, zero_division=0), "Especificidad": tn / (tn + fp_),
            "ExactBal": M.balanced_accuracy_score(y, yh), "MCC": M.matthews_corrcoef(y, yh)}


def experimento(conf, conjunto, nombre, Xp, tr, te):
    """Entrena o recupera del punto de control y devuelve las probabilidades sobre la prueba."""
    etiqueta, cols = CONJ[conjunto]
    Xtr, ytr = (tr[cols], tr.AF.values) if conf == "conf2" else (Xp[cols], Xp.AF.values)
    clave = f"{conf}_{etiqueta}_{nombre}"
    ruta, meta = os.path.join(PRED, clave + ".npy"), os.path.join(PRED, clave + ".json")
    if os.path.exists(ruta) and os.path.exists(meta):
        if json.load(open(meta)).get("n_train") == len(Xtr):  # punto de control válido
            return np.load(ruta)
    n_total = len(Xtr)
    log.info(f"INICIO {clave} n_train={n_total}")
    t0 = time.time()
    pipe = make_pipeline(SimpleImputer(strategy="median"), MinMaxScaler(), modelo(nombre))
    if nombre == "SVM" and len(Xtr) > MAX_SVM:
        # libsvm escala casi cuadráticamente: submuestra estratificada para acotar el tiempo
        from sklearn.model_selection import train_test_split
        Xtr, _, ytr, _ = train_test_split(Xtr, ytr, train_size=MAX_SVM, stratify=ytr, random_state=SEMILLA)
        log.info(f"SVM con submuestra estratificada de {MAX_SVM}")
    pipe.fit(Xtr, ytr)
    p = pipe.predict_proba(te[cols])[:, 1]
    np.save(ruta, p)
    if nombre == "CatBoost":
        joblib.dump(pipe, os.path.join(RES, f"modelo_{conf}_{etiqueta}.joblib"))
    m = metricas(te.AF.values, p)
    json.dump({"n_train": n_total, "segundos": time.time() - t0, **m}, open(meta, "w"))
    fila = pd.DataFrame([{"fecha": time.strftime("%Y-%m-%d %H:%M"), "conf": conf, "rasgos": conjunto,
                          "modelo": nombre, "n_train": len(Xtr), **m}])
    fm = os.path.join(RES, "metricas.csv")
    fila.to_csv(fm, mode="a", header=not os.path.exists(fm), index=False)
    log.info(f"FIN {clave} {time.time() - t0:.0f}s F1={m['F1']:.3f} AUROC={m['AUROC']:.3f}")
    return p


def correr(conf, conjunto, nombres, Xp, tr, te):
    preds = {n: experimento(conf, conjunto, n, Xp, tr, te) for n in nombres}
    tabla = pd.DataFrame({n: metricas(te.AF.values, p) for n, p in preds.items()}).T
    return tabla, preds


def bootstrap(y, p, B=1000, semilla=SEMILLA):
    rng = np.random.default_rng(semilla)
    f1, au = [], []
    for _ in range(B):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        f1.append(M.f1_score(y[i], p[i] >= 0.5))
        au.append(M.roc_auc_score(y[i], p[i]))
    return np.percentile(f1, [2.5, 97.5]), np.percentile(au, [2.5, 97.5])


def main():
    Xp, tr, te = cargar_datos()
    log.info(f"DATOS publicos={len(Xp)} kingston_train={len(tr)} kingston_test={len(te)}")
    for conf in ["conf2", "conf3"]:
        correr(conf, "Base", MODELOS, Xp, tr, te)
        for conjunto in CONJ:
            correr(conf, conjunto, MOD_AB, Xp, tr, te)
    log.info("EXPERIMENTOS COMPLETOS")
    print("EXPERIMENTOS COMPLETOS", flush=True)


if __name__ == "__main__":
    main()
