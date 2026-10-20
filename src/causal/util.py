"""Utilidades comunes: JSON, redondeo y formato de cifras."""

import datetime as dt
import json
import math
from pathlib import Path

import numpy as np


def _normalizar(x: object) -> object:
    if isinstance(x, dict):
        return {str(k): _normalizar(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_normalizar(v) for v in x]
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating | float):
        v = float(x)
        return None if math.isnan(v) else v
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, dt.date | dt.datetime):
        return x.isoformat()
    return x


def escribir_json(datos: object, ruta: Path) -> None:
    """JSON legible, UTF-8 y con fin de línea LF (la misma huella en Windows y en Linux)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(_normalizar(datos), ensure_ascii=False, indent=2) + "\n"
    with ruta.open("w", encoding="utf-8", newline="\n") as f:
        f.write(texto)


def leer_json(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def coma(x: float, d: int) -> str:
    """Número con coma decimal, como en los textos del proyecto."""
    return f"{x:.{d}f}".replace(".", ",")


def miles(n: int) -> str:
    """Entero con punto de miles."""
    return f"{n:,}".replace(",", ".")
