"""Hito 5: evaluación de políticas y quintiles con datos de experimento simulados."""

import numpy as np

from causal import flujo_hito5


def test_quintiles_recuperan_heterogeneidad() -> None:
    rng = np.random.default_rng(0)
    n = 40000
    x = rng.random(n)
    d = (rng.random(n) < 0.5).astype(int)
    y = (rng.random(n) < 0.1 + 0.2 * x * d).astype(float)
    q = flujo_hito5._deciles(x, d, y)
    efectos = [g["efecto_real"] for g in q]
    assert efectos[-1] > efectos[0] + 0.1
    assert sum(g["n"] for g in q) == n


def test_valor_ipw_politica() -> None:
    rng = np.random.default_rng(1)
    n = 60000
    t = rng.integers(0, 3, n)
    y = (rng.random(n) < np.array([0.10, 0.18, 0.14])[t]).astype(float)
    costo = np.where(t > 0, 0.05, 0.0)
    todos_1 = flujo_hito5._valor_ipw(y, t, np.ones(n, dtype=int), 1 / 3, costo, reps=50)
    nadie = flujo_hito5._valor_ipw(y, t, np.zeros(n, dtype=int), 1 / 3, costo, reps=50)
    assert abs(todos_1["valor"] - 0.13) < 0.01
    assert abs(nadie["valor"] - 0.10) < 0.01
