"""Capa predictiva: etiquetas, métricas y referencia."""

import numpy as np
import pandas as pd

from causal import prediccion


def test_map_k_ejemplo() -> None:
    puntajes = pd.DataFrame({"a": [0.9, 0.1], "b": [0.5, np.nan], "c": [0.1, 0.8]})
    verdad = pd.DataFrame({"a": [0, 0], "b": [1, np.nan], "c": [0, 1]})
    valor, n = prediccion.map_k(puntajes, verdad, k=7)
    # cliente 1: b en la posición 2 -> 1/2; cliente 2: c en la posición 1 -> 1
    assert n == 2 and abs(valor - 0.75) < 1e-12


def test_metricas_y_referencia() -> None:
    rng = np.random.default_rng(0)
    X = pd.DataFrame(
        {
            "seg_top": 0,
            "seg_universitario": rng.integers(0, 2, 2000),
            "activo": rng.integers(0, 2, 2000).astype(float),
            "edad": rng.integers(18, 80, 2000).astype(float),
        }
    )
    y = (rng.random(2000) < 0.05 + 0.1 * X["activo"]).astype(int).to_numpy()
    ref = prediccion.referencia_ajustar(X, y, np.ones(len(y)))
    s = prediccion.referencia_puntuar(ref, X)
    m = prediccion.metricas(y, s)
    assert m["auc"] > 0.6 and 0 < m["ap"] <= 1
    lo, hi = prediccion.ic_ap(y, s, reps=30)
    assert lo <= m["ap"] <= hi


def test_tabla_pred(con) -> None:
    # crear_tabla escribe, así que se usa una copia en memoria
    import duckdb

    c = duckdb.connect()
    c.register("p", con.execute("SELECT * FROM panel").df())
    c.execute("CREATE TABLE panel AS SELECT * FROM p")
    prediccion.crear_tabla(c)
    df = c.execute("SELECT * FROM pred").df()
    assert df.t.between(6, 15).all()
    # quien tiene el producto en t no tiene etiqueta
    assert df.loc[df.tjcr == 1, "y_tjcr"].isna().all()
    cols = prediccion.variables(c)
    assert not any(x.startswith("y_") for x in cols)


def test_ap_por_fila_coincide_con_map_k() -> None:
    puntajes = pd.DataFrame({"a": [0.9, 0.1, 0.3], "b": [0.5, np.nan, 0.2], "c": [0.1, 0.8, 0.4]})
    verdad = pd.DataFrame({"a": [0, 0, 0], "b": [1, np.nan, 0], "c": [0, 1, 0]})
    ap = prediccion.ap_por_fila(puntajes, verdad)
    assert np.isnan(ap[2])  # sin adquisiciones
    assert abs(np.nanmean(ap) - prediccion.map_k(puntajes, verdad)[0]) < 1e-12
    # un producto no candidato (NaN) nunca cuenta como acierto
    ap2 = prediccion.ap_por_fila(puntajes.assign(c=np.nan), verdad)
    assert ap2[1] == 0.0
