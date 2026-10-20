"""Estimadores causales sobre datos simulados con efecto conocido."""

import numpy as np
import pandas as pd
import pytest

from causal import metodos


def _sim(n: int = 6000, semilla: int = 0):
    rng = np.random.default_rng(semilla)
    X = pd.DataFrame(rng.normal(size=(n, 4)), columns=list("abcd"))
    e = 1 / (1 + np.exp(-(0.9 * X.a - 0.5 * X.b - 1.0)))
    d = (rng.random(n) < e).astype(int).to_numpy()
    tau = 1.0 + 0.5 * (X.a > 0)
    y_pre = 2 * X.a + X.b + rng.normal(size=n)
    y = y_pre + 0.5 * X.b + tau * d + rng.normal(size=n)
    return X, d, y.to_numpy(), y_pre.to_numpy(), float(tau[d == 1].mean())


def test_ingenuo_sesgado_y_ajustados_aciertan() -> None:
    X, d, y, y_pre, att = _sim()
    assert abs(metodos.ingenuo(X, d, y).efecto - att) > 0.3
    for est in (
        metodos.dml_att(X, d, y),
        metodos.did_dr(X, d, y, y_pre),
        metodos.emparejamiento(X, d, y, reps=50),
    ):
        assert abs(est.efecto - att) < 0.2, est
        assert est.ic95[0] < est.efecto < est.ic95[1]


def test_determinista() -> None:
    X, d, y, _, _ = _sim(3000)
    a, b = metodos.dml_att(X, d, y, semilla=3), metodos.dml_att(X, d, y, semilla=3)
    assert a.efecto == b.efecto


@pytest.mark.integracion
def test_bosque_causal() -> None:
    X, d, y, _, att = _sim(4000)
    est = metodos.bosque_causal(X, d, y, arboles=100)
    assert abs(est.efecto - att) < 0.3
