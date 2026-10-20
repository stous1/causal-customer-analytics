"""Capa predictiva: propensión a adquirir cada producto el mes siguiente.

Una fila por cliente y mes ``t`` (meses 6 a 15: solo meses con demografía real). Variables
medidas en ``t`` y antes; la etiqueta de un producto ``p`` vale 1 si el cliente no lo tenía
en ``t`` y lo tiene en ``t + 1``. Quien ya tiene ``p`` en ``t`` no entra en el modelo de
``p`` (no puede adquirirlo). Quien no aparece en ``t + 1`` no tiene etiqueta.

Esto **predice**; no dice qué causa la adquisición. Las importancias SHAP de estos modelos
se publican marcadas como predictivas y se contrastan con los efectos causales del hito 4.
"""

from dataclasses import dataclass

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from causal.disenos import CANALES_TOP, PROVINCIAS_TOP
from causal.ingesta import PRODUCTOS

PRIMER_T = 6
ULTIMO_T = 15  # la etiqueta de t = 15 está en mayo de 2016
EDADES = (0, 25, 35, 45, 55, 65, 200)


def crear_tabla(con: duckdb.DuckDBPyConnection) -> None:
    """Tabla ``pred``: variables en t (y rezagos) y etiquetas de adquisición en t+1."""
    canales = ", ".join(f"(x.canal = '{c}')::UTINYINT AS canal_{c.lower()}" for c in CANALES_TOP)
    provincias = ", ".join(f"(x.cod_prov = {p})::UTINYINT AS prov_{p}" for p in PROVINCIAS_TOP)
    actuales = ", ".join(f"coalesce(x.{p}, 0)::UTINYINT AS {p}" for p in PRODUCTOS)
    previos = ", ".join(f"a.{p}::UTINYINT AS {p}_ant" for p in PRODUCTOS)
    etiquetas = ", ".join(
        f"CASE WHEN coalesce(x.{p}, 0) = 1 OR s.cliente IS NULL THEN NULL "
        f"ELSE coalesce(s.{p}, 0) END::UTINYINT AS y_{p}"
        for p in PRODUCTOS
    )
    n_t = " + ".join(f"coalesce(x.{p}, 0)" for p in PRODUCTOS)
    n_3 = " + ".join(f"coalesce(c.{p}, 0)" for p in PRODUCTOS)
    altas_3 = " + ".join(
        f"(coalesce(x.{p}, 0) = 1 AND coalesce(c.{p}, 0) = 0)::INT" for p in PRODUCTOS
    )
    bajas_3 = " + ".join(
        f"(coalesce(x.{p}, 0) = 0 AND coalesce(c.{p}, 0) = 1)::INT" for p in PRODUCTOS
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE pred AS
        SELECT x.cliente, x.mes AS t,
               x.edad::DOUBLE AS edad,
               (x.sexo = 'H')::UTINYINT AS mujer,
               ln(coalesce(x.renta, 1.0))::DOUBLE AS log_renta,
               (x.renta IS NULL)::UTINYINT AS renta_faltante,
               x.antiguedad::DOUBLE AS antiguedad,
               (x.segmento = '01 - TOP')::UTINYINT AS seg_top,
               (x.segmento = '03 - UNIVERSITARIO')::UTINYINT AS seg_universitario,
               (x.extranjero = 'S')::UTINYINT AS extranjero,
               (x.empleado <> 'N')::UTINYINT AS empleado_banco,
               (x.relacion_mes = 'A')::UTINYINT AS relacion_activa,
               x.nuevo::UTINYINT AS nuevo,
               {canales}, {provincias},
               x.activo::DOUBLE AS activo,
               (CASE WHEN x.mes - 1 >= {PRIMER_T} THEN a.activo END)::DOUBLE AS activo_ant,
               ({n_t})::DOUBLE AS n_productos,
               (CASE WHEN c.cliente IS NULL THEN NULL ELSE {n_3} END)::DOUBLE AS n_productos_t3,
               (CASE WHEN c.cliente IS NULL THEN NULL ELSE {altas_3} END)::DOUBLE AS altas_3m,
               (CASE WHEN c.cliente IS NULL THEN NULL ELSE {bajas_3} END)::DOUBLE AS bajas_3m,
               {actuales}, {previos}, {etiquetas}
        FROM panel x
        LEFT JOIN panel a ON a.cliente = x.cliente AND a.mes = x.mes - 1
        LEFT JOIN panel c ON c.cliente = x.cliente AND c.mes = x.mes - 3
        LEFT JOIN panel s ON s.cliente = x.cliente AND s.mes = x.mes + 1
        WHERE x.mes BETWEEN {PRIMER_T} AND {ULTIMO_T}
          AND x.edad IS NOT NULL
        """
    )


def variables(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Columnas de entrada del modelo (todo menos identificadores y etiquetas)."""
    cols = [r[0] for r in con.execute("SELECT column_name FROM (DESCRIBE pred)").fetchall()]
    return [c for c in cols if c not in ("cliente", "t") and not c.startswith("y_")]


def positivos_por_mes(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Adquisiciones por producto y mes t (etiqueta en t+1)."""
    exprs = ", ".join(f"sum(y_{p}) AS {p}" for p in PRODUCTOS)
    return con.execute(f"SELECT t, {exprs} FROM pred GROUP BY 1 ORDER BY 1").df()


def cargar(
    con: duckdb.DuckDBPyConnection,
    producto: str,
    t_desde: int,
    t_hasta: int,
    cols: list[str],
    frac_negativos: float = 1.0,
    semilla: int = 5,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Filas elegibles para ``producto`` con su etiqueta y peso.

    Con ``frac_negativos < 1`` se conserva cada negativo con esa probabilidad (de forma
    determinista) y se le da peso ``1 / frac_negativos``: el modelo ve la misma distribución.
    """
    filtro = ""
    if frac_negativos < 1.0:
        filtro = (
            f"AND (y_{producto} = 1 OR "
            f"(hash(cliente, t, {semilla}) % 1000000) / 1000000.0 < {frac_negativos})"
        )
    df = con.execute(
        f"""
        SELECT cliente, t, {", ".join(cols)}, y_{producto} AS y FROM pred
        WHERE t BETWEEN {t_desde} AND {t_hasta} AND y_{producto} IS NOT NULL {filtro}
        ORDER BY t, cliente
        """
    ).df()
    y = df.pop("y").to_numpy().astype(np.int8)
    peso = np.where(y == 1, 1.0, 1.0 / frac_negativos)
    return df, y, peso


@dataclass
class Configuracion:
    """Hiperparámetros de LightGBM; ``rondas`` se fija con parada temprana en validación."""

    num_leaves: int = 63
    learning_rate: float = 0.05
    min_data_in_leaf: int = 200
    feature_fraction: float = 0.8
    bagging_fraction: float = 0.8
    lambda_l2: float = 1.0
    rondas: int = 1000

    def lgb(self, semilla: int = 7) -> dict:
        return {
            "objective": "binary",
            "num_leaves": self.num_leaves,
            "learning_rate": self.learning_rate,
            "min_data_in_leaf": self.min_data_in_leaf,
            "feature_fraction": self.feature_fraction,
            "bagging_fraction": self.bagging_fraction,
            "bagging_freq": 1,
            "lambda_l2": self.lambda_l2,
            "seed": semilla,
            "deterministic": True,
            "force_col_wise": True,
            "num_threads": 8,
            "verbose": -1,
        }


def entrenar(
    X: pd.DataFrame,
    y: np.ndarray,
    peso: np.ndarray,
    conf: Configuracion,
    validacion: tuple[pd.DataFrame, np.ndarray] | None = None,
) -> lgb.Booster:
    """Entrena; con ``validacion`` usa parada temprana por precisión promedio."""
    datos = lgb.Dataset(X, y, weight=peso, free_raw_data=False)
    params = conf.lgb() | {"metric": "average_precision"}
    if validacion is None:
        return lgb.train(params, datos, num_boost_round=conf.rondas)
    Xv, yv = validacion
    dv = lgb.Dataset(Xv, yv, reference=datos)
    return lgb.train(
        params,
        datos,
        num_boost_round=conf.rondas,
        valid_sets=[dv],
        callbacks=[lgb.early_stopping(50, verbose=False)],
    )


def metricas(y: np.ndarray, puntaje: np.ndarray) -> dict:
    """Precisión promedio (AP), AUC ROC, tasa base y precisión en el 1 % superior."""
    k = max(1, len(y) // 100)
    orden = np.argsort(-puntaje, kind="stable")[:k]
    return {
        "ap": float(average_precision_score(y, puntaje)),
        "auc": float(roc_auc_score(y, puntaje)),
        "tasa_base": float(y.mean()),
        "precision_top1pct": float(y[orden].mean()),
        "positivos": int(y.sum()),
        "filas": int(len(y)),
    }


def ic_ap(y: np.ndarray, puntaje: np.ndarray, reps: int = 100, semilla: int = 3) -> list[float]:
    """Intervalo bootstrap (percentiles 2,5 y 97,5) de la precisión promedio."""
    rng = np.random.default_rng(semilla)
    n = len(y)
    valores = []
    for _ in range(reps):
        i = rng.integers(0, n, n)
        if y[i].sum() == 0:
            continue
        valores.append(average_precision_score(y[i], puntaje[i]))
    return [float(np.percentile(valores, 2.5)), float(np.percentile(valores, 97.5))]


# Referencia simple: tasa de adquisición del producto en la celda (segmento, tramo de edad,
# actividad) durante el entrenamiento.
CELDA = ("seg_top", "seg_universitario", "tramo_edad", "activo")


def _tramo(edad: pd.Series) -> pd.Series:
    return pd.cut(edad.fillna(40), bins=list(EDADES), labels=False, right=False)


def referencia_ajustar(X: pd.DataFrame, y: np.ndarray, peso: np.ndarray) -> dict:
    """Tasas por celda (ponderadas) y la tasa global para celdas vacías."""
    df = X[["seg_top", "seg_universitario", "activo"]].copy()
    df["tramo_edad"] = _tramo(X["edad"])
    df["activo"] = df["activo"].fillna(0)
    df["y"] = y * peso
    df["w"] = peso
    g = df.groupby(list(CELDA), observed=True)[["y", "w"]].sum()
    tasas = (g["y"] / g["w"]).to_dict()
    return {"tasas": tasas, "global": float((y * peso).sum() / peso.sum())}


def referencia_puntuar(modelo: dict, X: pd.DataFrame) -> np.ndarray:
    df = X[["seg_top", "seg_universitario", "activo"]].copy()
    df["tramo_edad"] = _tramo(X["edad"])
    df["activo"] = df["activo"].fillna(0)
    claves = list(zip(*(df[c] for c in CELDA), strict=True))
    return np.array([modelo["tasas"].get(k, modelo["global"]) for k in claves])


def ap_por_fila(puntajes: pd.DataFrame, verdad: pd.DataFrame, k: int = 7) -> np.ndarray:
    """AP@k de cada fila (cliente-mes); NaN en las filas sin ninguna adquisición.

    NaN en ``puntajes`` = producto no candidato (ya lo tiene o no se modela): nunca se recomienda.
    """
    P = puntajes.to_numpy(dtype=float)
    V = np.nan_to_num(verdad.to_numpy(dtype=float))
    P = np.where(np.isnan(P), -np.inf, P)
    orden = np.argsort(-P, axis=1, kind="stable")[:, :k]
    aciertos = np.take_along_axis(V, orden, axis=1)
    aciertos = np.where(np.isinf(np.take_along_axis(P, orden, axis=1)), 0.0, aciertos)
    prec = np.cumsum(aciertos, axis=1) / np.arange(1, orden.shape[1] + 1)
    n = V.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, (prec * aciertos).sum(axis=1) / np.minimum(n, k), np.nan)


def map_k(puntajes: pd.DataFrame, verdad: pd.DataFrame, k: int = 7) -> tuple[float, int]:
    """MAP@k por cliente (métrica de la competencia de Kaggle).

    ``puntajes`` y ``verdad``: una fila por (cliente, t), una columna por producto; NaN en
    ``puntajes`` donde el cliente ya tiene el producto. Solo cuentan los clientes con al menos
    una adquisición entre los productos modelados.
    """
    P = puntajes.to_numpy(dtype=float)
    V = verdad.to_numpy(dtype=float)
    V = np.nan_to_num(V)
    con_alta = V.sum(axis=1) > 0
    P, V = P[con_alta], V[con_alta]
    P = np.where(np.isnan(P), -np.inf, P)
    orden = np.argsort(-P, axis=1, kind="stable")[:, :k]
    aciertos = np.take_along_axis(V, orden, axis=1)
    acum = np.cumsum(aciertos, axis=1)
    prec = acum / np.arange(1, orden.shape[1] + 1)
    ap = (prec * aciertos).sum(axis=1) / np.minimum(V.sum(axis=1), k)
    return float(ap.mean()), int(con_alta.sum())
