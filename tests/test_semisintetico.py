"""Semisintético: verdad conocida y aislamiento de los resultados reales."""

import inspect

import numpy as np
import pandas as pd

from causal import disenos, semisintetico


def _X(n: int = 3000) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    return pd.DataFrame(
        {
            "act_m1": rng.integers(0, 2, n),
            "act_m2": rng.integers(0, 2, n),
            "otros_m1": rng.integers(0, 5, n),
            "edad": rng.integers(18, 90, n).astype(float),
            "relacion_activa": rng.integers(0, 2, n),
            "seg_universitario": rng.integers(0, 2, n),
            "x_tjcr": rng.integers(0, 2, n),
            "x_recibo": rng.integers(0, 2, n),
        }
    )


def test_generar_determinista_y_coherente() -> None:
    X = _X()
    for esc in semisintetico.ESCENARIOS:
        a = semisintetico.generar(X, esc, 5)
        b = semisintetico.generar(X, esc, 5)
        assert np.array_equal(a.y, b.y) and np.array_equal(a.d, b.d)
        assert 0.02 < a.d.mean() < 0.6
        assert np.isfinite(a.att)


def test_solo_lee_covariables(con) -> None:
    X = disenos.leer_covariables(con, "d_nomina", "nomina")
    assert not any(c.startswith(("y_", "ev_")) for c in X.columns)
    assert "d" not in X.columns and "cliente" not in X.columns
    assert set(semisintetico.NECESARIAS) <= set(X.columns)
    fuente = inspect.getsource(semisintetico)
    for real in ("y_activo", "y_dprod", "y_inactivo", "ev_"):
        assert real not in fuente
