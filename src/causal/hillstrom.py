"""Hillstrom: campaña de correo con tratamiento y control aleatorizados (64.000 clientes).

Tres brazos: correo de mujer, correo de hombre y sin correo. Resultados: visita al sitio,
conversión y gasto en las dos semanas siguientes. Como el tratamiento es aleatorio, la
diferencia de medias es la verdad contra la que se validan los métodos.

Para probar los métodos en condiciones observacionales se **sesga** el experimento: se
conserva cada tratado con una probabilidad conocida que depende de sus covariables (los
compradores recientes y de mayor historia quedan sobrerrepresentados). El efecto verdadero
en esos tratados se calcula con el experimento completo, ponderando por esa probabilidad.
"""

import numpy as np
import pandas as pd

from causal.rutas import DIR_HILLSTROM

ARCHIVO = "hillstorm_no_indices.csv.gz"  # nombre que usa scikit-uplift
BRAZOS = {"mujer": "Womens E-Mail", "hombre": "Mens E-Mail"}
CONTROL = "No E-Mail"
RESULTADOS = ("visit", "conversion", "spend")


def cargar() -> pd.DataFrame:
    """Lee el archivo descargado por ``sklift.datasets.fetch_hillstrom``; lo descarga si falta."""
    ruta = DIR_HILLSTROM / ARCHIVO
    if not ruta.exists():
        from sklift.datasets import fetch_hillstrom

        fetch_hillstrom(data_home=str(DIR_HILLSTROM))
    return pd.read_csv(ruta)


def covariables(df: pd.DataFrame) -> pd.DataFrame:
    """Covariables previas a la campaña, numéricas."""
    X = pd.DataFrame(
        {
            "recency": df["recency"].astype(float),
            "log_history": np.log1p(df["history"].astype(float)),
            "mens": df["mens"].astype(float),
            "womens": df["womens"].astype(float),
            "newbie": df["newbie"].astype(float),
        }
    )
    for z in ("Urban", "Rural"):
        X[f"zip_{z.lower()}"] = (df["zip_code"] == z).astype(float)
    for c in ("Web", "Phone"):
        X[f"canal_{c.lower()}"] = (df["channel"] == c).astype(float)
    return X


def brazo(df: pd.DataFrame, nombre: str) -> pd.DataFrame:
    """Filas del brazo ``nombre`` y del control, con ``d`` = 1 para el brazo."""
    sel = df[df["segment"].isin([BRAZOS[nombre], CONTROL])].reset_index(drop=True)
    sel["d"] = (sel["segment"] == BRAZOS[nombre]).astype(np.int8)
    return sel


def efecto_experimento(df: pd.DataFrame, resultado: str) -> dict:
    """Diferencia de medias con su intervalo de 95 % (la verdad del experimento)."""
    y1 = df.loc[df.d == 1, resultado].astype(float)
    y0 = df.loc[df.d == 0, resultado].astype(float)
    efecto = y1.mean() - y0.mean()
    ee = np.sqrt(y1.var(ddof=1) / len(y1) + y0.var(ddof=1) / len(y0))
    return {
        "efecto": float(efecto),
        "ee": float(ee),
        "ic95": [float(efecto - 1.96 * ee), float(efecto + 1.96 * ee)],
        "media_tratados": float(y1.mean()),
        "media_control": float(y0.mean()),
        "n_tratados": int(len(y1)),
        "n_control": int(len(y0)),
    }


def probabilidad_seleccion(X: pd.DataFrame) -> np.ndarray:
    """Probabilidad conocida de conservar a un tratado (sesgo por covariables)."""
    z_hist = (X["log_history"] - X["log_history"].mean()) / X["log_history"].std()
    z_rec = (X["recency"] - X["recency"].mean()) / X["recency"].std()
    lin = -0.3 + 1.0 * z_hist - 0.8 * z_rec + 0.9 * (1 - X["newbie"]) + 0.6 * X["canal_web"]
    return (1 / (1 + np.exp(-lin))).to_numpy()


def efecto_objetivo_sesgado(df: pd.DataFrame, X: pd.DataFrame, resultado: str) -> dict:
    """ATT verdadero en la población de tratados que deja el sesgo.

    Con el experimento completo: medias de tratados y de controles ponderadas por la
    probabilidad de selección (que solo depende de ``X``). Error por función de influencia.
    """
    p = probabilidad_seleccion(X)
    y = df[resultado].to_numpy(dtype=float)
    d = df["d"].to_numpy()
    partes = []
    for brazo_ in (1, 0):
        w, v = p[d == brazo_], y[d == brazo_]
        media = (w * v).sum() / w.sum()
        var = ((w * (v - media)) ** 2).sum() / w.sum() ** 2
        partes.append((media, var))
    efecto = partes[0][0] - partes[1][0]
    ee = float(np.sqrt(partes[0][1] + partes[1][1]))
    return {"efecto": float(efecto), "ee": ee, "ic95": [efecto - 1.96 * ee, efecto + 1.96 * ee]}


def sesgar(df: pd.DataFrame, X: pd.DataFrame, semilla: int) -> np.ndarray:
    """Índices que se conservan: todos los controles y los tratados sorteados con ``p(X)``."""
    rng = np.random.default_rng(semilla)
    p = probabilidad_seleccion(X)
    d = df["d"].to_numpy()
    queda = (d == 0) | (rng.random(len(df)) < p)
    return np.flatnonzero(queda)
