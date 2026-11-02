"""Preprocesamiento y extracción de rasgos de ECG para la detección de fibrilación auricular.

Reproduce el flujo de Nassar et al. (arXiv:2512.18031): filtro Butterworth pasabanda de
5 a 30 Hz en ambos sentidos, remuestreo a 240 Hz, picos R con SleepECG y 27 rasgos por
derivación con NeuroKit2. Agrega rasgos ampliados: wavelet (DWT y Haar sobre RR),
transformada de Radón de diagramas de recurrencia y rasgos espectrales de la banda auricular.
"""
import warnings

import numpy as np
import pywt
import scipy.signal as ss
from skimage.transform import radon

warnings.filterwarnings("ignore")

FS = 240
LEADS = ["I", "II", "III", "V1"]

# Nombres de NeuroKit2 para los rasgos de la Tabla I del artículo base
HRV_TIME = ["HRV_MinNN", "HRV_MaxNN", "HRV_MeanNN", "HRV_MedianNN", "HRV_SDNN",
            "HRV_MadNN", "HRV_IQRNN", "HRV_Prc20NN", "HRV_Prc80NN", "HRV_SDSD",
            "HRV_pNN20", "HRV_pNN50", "HRV_HTI"]
HRV_NL = ["HRV_SD1", "HRV_SD2", "HRV_S", "HRV_SD1d", "HRV_SD1a", "HRV_SD2d",
          "HRV_SD2a", "HRV_SDNNd", "HRV_SDNNa", "HRV_PIP", "HRV_ShanEn"]
BASE_NAMES = ["Quality", "HR"] + HRV_TIME + HRV_NL + ["P_amp"]  # 27 rasgos

EXT_NAMES = ([f"DWT_E{b}" for b in ["A5", "D5", "D4", "D3", "D2", "D1"]] + ["DWT_Ent"]
             + ["HaarRR_Ed1", "HaarRR_Ed2"]
             + ["Radon_var45", "Radon_ratio45", "Radon_angmax", "Radon_kurt45"]
             + ["Spec_DF", "Spec_OI", "Spec_Hent"])


def preprocesar(x, fs_in, fs_out=FS):
    """Filtro Butterworth de orden 2 entre 5 y 30 Hz en ambos sentidos y remuestreo."""
    b, a = ss.butter(2, [5, 30], btype="bandpass", fs=fs_in)
    y = ss.filtfilt(b, a, x, axis=-1)
    if fs_in != fs_out:
        n_out = int(round(y.shape[-1] * fs_out / fs_in))
        y = ss.resample_poly(y, fs_out, fs_in, axis=-1) if float(fs_in).is_integer() else ss.resample(y, n_out, axis=-1)
    return y


def picos_r(x, fs=FS):
    import sleepecg
    return np.asarray(sleepecg.detect_heartbeats(x, fs), dtype=int)


def rasgos_base(x, fs=FS):
    """27 rasgos de la Tabla I para una derivación ya filtrada. Devuelve None si hay 3 picos R o menos."""
    import neurokit2 as nk
    r = picos_r(x, fs)
    if len(r) <= 3:
        return None, r
    out = dict.fromkeys(BASE_NAMES, np.nan)
    try:
        q = nk.ecg_quality(x, rpeaks=r, sampling_rate=fs)
        out["Quality"] = float(np.nanmean(q))
    except Exception:
        pass
    rr = np.diff(r) / fs
    out["HR"] = 60.0 / np.mean(rr)
    peaks = {"ECG_R_Peaks": r}
    try:
        t = nk.hrv_time(peaks, sampling_rate=fs)
        for k in HRV_TIME:
            out[k] = float(t[k].iloc[0])
    except Exception:
        pass
    try:
        n = nk.hrv_nonlinear(peaks, sampling_rate=fs)
        for k in HRV_NL:
            if k in n:
                out[k] = float(n[k].iloc[0])
    except Exception:
        pass
    try:
        _, w = nk.ecg_delineate(x, rpeaks=r, sampling_rate=fs, method="peak")
        p = np.asarray(w["ECG_P_Peaks"], dtype=float)
        p = p[~np.isnan(p)].astype(int)
        out["P_amp"] = float(np.mean(x[p])) if len(p) else np.nan
    except Exception:
        pass
    return out, r


def recurrence_plot(x, n=256, m=3, tau=2, tasa=0.1):
    """Diagrama de recurrencia con embebido de retardo (dimensión m, retardo tau) de la señal
    submuestreada a n puntos. El umbral fija una tasa de recurrencia constante (10 %), lo que
    hace comparables registros con amplitudes distintas."""
    z = ss.resample(x, n + (m - 1) * tau)
    z = (z - z.mean()) / (z.std() + 1e-12)
    E = np.stack([z[i * tau:i * tau + n] for i in range(m)], axis=1)
    D = np.sqrt(((E[:, None, :] - E[None, :, :]) ** 2).sum(-1))
    return (D < np.quantile(D, tasa)).astype(float)


def rasgos_radon(rp, angulos=np.arange(0, 180, 15)):
    """Rasgos de orientación de la transformada de Radón del diagrama de recurrencia.

    En ritmo regular las recurrencias forman líneas paralelas a la diagonal (45 grados en
    la convención de skimage, columnas = ángulo), y su proyección es muy picuda.
    """
    s = radon(rp - rp.mean(), theta=angulos, circle=False)
    v = s.var(axis=0)
    i45 = int(np.argmin(np.abs(angulos - 45)))
    p45 = s[:, i45]
    m = p45 - p45.mean()
    kurt = float(np.mean(m ** 4) / (np.mean(m ** 2) ** 2 + 1e-12))
    return {"Radon_var45": float(v[i45]), "Radon_ratio45": float(v[i45] / (v.mean() + 1e-12)),
            "Radon_angmax": float(angulos[int(np.argmax(v))]), "Radon_kurt45": kurt}


def rasgos_espectrales(x_raw, r, fs):
    """Frecuencia dominante e índice de organización de la actividad auricular (3 a 12 Hz)
    tras restar una plantilla promedio del complejo QRST."""
    b, a = ss.butter(2, [0.5, 40], btype="bandpass", fs=fs)
    y = ss.filtfilt(b, a, x_raw)
    w0, w1 = int(0.1 * fs), int(0.4 * fs)
    rv = r[(r - w0 >= 0) & (r + w1 < len(y))]
    if len(rv) >= 2:
        tpl = np.mean([y[k - w0:k + w1] for k in rv], axis=0)
        for k in rv:
            y[k - w0:k + w1] -= tpl
    f, P = ss.welch(y, fs=fs, nperseg=min(len(y), 4 * fs))
    band = (f >= 3) & (f <= 12)
    Pb, fb = P[band], f[band]
    if Pb.sum() <= 0:
        return {"Spec_DF": np.nan, "Spec_OI": np.nan, "Spec_Hent": np.nan}
    df = fb[np.argmax(Pb)]
    oi = Pb[np.abs(fb - df) <= 0.5].sum() / Pb.sum()
    pn = Pb / Pb.sum()
    hent = float(-(pn * np.log(pn + 1e-12)).sum() / np.log(len(pn)))
    return {"Spec_DF": float(df), "Spec_OI": float(oi), "Spec_Hent": hent}


def rasgos_ampliados(x, r, x_raw, fs_raw, fs=FS):
    out = dict.fromkeys(EXT_NAMES, np.nan)
    # Energía relativa y entropía wavelet (db4, 5 niveles): a 240 Hz, D3 cubre 15 a 30 Hz (QRS),
    # D5 de 3,75 a 7,5 Hz (ondas P, T y fibrilatorias)
    c = pywt.wavedec(x, "db4", level=5)
    e = np.array([np.sum(ci ** 2) for ci in c])
    pe = e / (e.sum() + 1e-12)
    for k, v in zip(["A5", "D5", "D4", "D3", "D2", "D1"], pe):
        out[f"DWT_E{k}"] = float(v)
    out["DWT_Ent"] = float(-(pe * np.log(pe + 1e-12)).sum())
    # Haar sobre la serie RR: la energía de detalle mide la irregularidad latido a latido
    rr = np.diff(r) / fs
    if len(rr) >= 4:
        rrc = rr - rr.mean()
        lv = 2 if len(rr) >= 8 else 1
        ch = pywt.wavedec(rrc, "haar", level=lv)
        tot = np.sum(rrc ** 2) + 1e-12
        out["HaarRR_Ed1"] = float(np.sum(ch[-1] ** 2) / tot)
        out["HaarRR_Ed2"] = float(np.sum(ch[-2] ** 2) / tot) if lv == 2 else np.nan
    out.update(rasgos_radon(recurrence_plot(x)))
    r_raw = np.round(r * fs_raw / fs).astype(int)
    out.update(rasgos_espectrales(x_raw, r_raw, fs_raw))
    return out


def rasgos_registro(sig, fs_in, nombres_der=LEADS, ampliados=True):
    """sig: matriz (n_muestras, 4) en mV con las derivaciones I, II, III y V1.
    Devuelve un diccionario de rasgos por derivación o None si falta alguna derivación."""
    fila = {}
    xf = preprocesar(sig.T, fs_in)
    for j, nom in enumerate(nombres_der):
        base, r = rasgos_base(xf[j])
        if base is None:
            return None
        for k, v in base.items():
            fila[f"{nom}_{k}"] = v
        if ampliados:
            for k, v in rasgos_ampliados(xf[j], r, sig[:, j], fs_in).items():
                fila[f"{nom}_{k}"] = v
    return fila
