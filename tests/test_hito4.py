"""Hito 4: carga de análisis, reglas de veredicto y criterios."""

import numpy as np
import pandas as pd

from causal import flujo_hito4, refutaciones


def test_cargar_canal_define_tratado(con) -> None:
    a = next(x for x in flujo_hito4.ANALISIS if x.id == "canal_khq_jovenes")
    df, cols = flujo_hito4.cargar(con, a)
    if len(df):
        assert set(df.canal) <= {"KHQ", "KHM"}
        assert (df.d == (df.canal == "KHQ")).all()
        assert df.edad.between(18, 30).all()
    assert not any(c.startswith(("x_", "canal_", "y_")) for c in cols)


def test_primarios_preregistrados() -> None:
    primarios = [a.id for a in flujo_hito4.ANALISIS if a.primario]
    assert primarios == [
        "nomina_actividad",
        "nomina_productos",
        "canal_meses_activo",
        "producto_recibo",
        "producto_tjcr",
        "producto_ecue",
    ]


def _res(**pruebas) -> dict:
    base = {
        "significativo": True,
        "placebo_permutacion": True,
        "causa_comun_aleatoria": True,
        "subconjunto": True,
        "consistencia": True,
        "sensibilidad_robusto": True,
        "placebo_adelanto": True,
    }
    return {"pruebas": base | pruebas}


def test_veredicto() -> None:
    assert flujo_hito4.veredicto(_res()) == "creíble"
    assert flujo_hito4.veredicto(_res(sensibilidad_robusto=False)) == "creíble pero sensible"
    assert flujo_hito4.veredicto(_res(placebo_adelanto=False)) == "no separable de la selección"
    assert flujo_hito4.veredicto(_res(consistencia=False)) == "frágil"
    assert flujo_hito4.veredicto(_res(significativo=False)) == "sin efecto detectable"


def test_holm_y_consistencia() -> None:
    aj = refutaciones.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert aj == {"a": 0.03, "c": 0.06, "b": 0.06}
    assert refutaciones.consistencia({"x": 0.1, "y": 0.15})["pasa"]
    assert not refutaciones.consistencia({"x": 0.1, "y": -0.1})["pasa"]
    assert not refutaciones.consistencia({"x": 0.1, "y": 0.25})["pasa"]


def test_sensibilidad_y_valor_e() -> None:
    rng = np.random.default_rng(0)
    n = 3000
    df = pd.DataFrame({"x1": rng.normal(size=n), "x2": rng.normal(size=n)})
    df["d"] = (rng.random(n) < 0.3).astype(int)
    df["y"] = df.x1 + 0.5 * df.d + rng.normal(size=n)
    s = refutaciones.sensibilidad(df, ["x1", "x2"], "y")
    assert 0 < s["valor_robustez_ic"] < s["valor_robustez"] < 1
    assert s["covariable_mas_fuerte"] in ("x1", "x2")
    assert refutaciones.valor_e(0.2, 0.1)["valor_e"] > 3
    assert abs(refutaciones.valor_robustez(0.0, 100)) < 1e-12
