"""Descarga en paralelo una lista de archivos reutilizando conexiones HTTP (keep alive).

Uso: python descargar_lista.py <url_base> <lista.txt> <dir_destino> [hilos]
Cada línea de la lista es una ruta relativa; se omiten los archivos ya descargados.
"""
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import requests

local = threading.local()


def sesion():
    if not hasattr(local, "s"):
        s = requests.Session()
        s.mount("https://", requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=5))
        local.s = s
    return local.s


def bajar(args):
    url, destino = args
    if os.path.exists(destino) and os.path.getsize(destino) > 0:
        return 0
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    for _ in range(3):
        try:
            r = sesion().get(url, timeout=60)
            if r.status_code == 200:
                with open(destino + ".part", "wb") as f:
                    f.write(r.content)
                os.replace(destino + ".part", destino)
                return 1
        except requests.RequestException:
            pass
    return -1


def main(base, lista, dest, hilos=64):
    rutas = [l.strip() for l in open(lista) if l.strip()]
    tareas = [(f"{base}/{r}", os.path.join(dest, r)) for r in rutas]
    ok = err = 0
    with ThreadPoolExecutor(hilos) as ex:
        for i, res in enumerate(ex.map(bajar, tareas), 1):
            ok += res == 1
            err += res == -1
            if i % 5000 == 0:
                print(f"{i}/{len(tareas)} nuevos={ok} errores={err}", flush=True)
    print(f"LISTO {len(tareas)} nuevos={ok} errores={err}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 64)
