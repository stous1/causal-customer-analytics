"""Semisintético: tratamientos y resultados inyectados sobre covariables reales de Santander.

Las covariables son las del diseño de nómina (``d_nomina``), con su distribución conjunta
real. El tratamiento y los resultados se simulan con funciones conocidas, así que el efecto
verdadero se conoce exactamente. **Este módulo solo recibe covariables**: nunca ve los
resultados reales de Santander (lo verifica ``tests/test_semisintetico.py``).

Escenarios:

- ``observables``: la selección depende solo de covariables observadas (actividad, tenencia,
  edad). Resultado binario tipo "activo en t+3". Todos los métodos que ajustan deberían
  acertar; el ingenuo no.
- ``efecto_fijo``: además, un rasgo no observado ``u`` del cliente sube la probabilidad de
  tratarse y el nivel del resultado, igual antes y después. Resultado continuo. Los métodos
  de corte transversal se sesgan; diferencias en diferencias no.
- ``tendencias``: ``u`` también cambia la tendencia. Diferencias en diferencias se sesga, y el
  placebo con dos períodos previos debería delatarlo.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

ESCENARIOS = ("observables", "efecto_fijo", "tendencias")
NECESARIAS = (
    "act_m1",
    "act_m2",
    "otros_m1",
    "edad",
    "relacion_activa",
    "seg_universitario",
    "x_tjcr",
    "x_recibo",
)


@dataclass
class Simulacion:
    escenario: str
    d: np.ndarray
    y: np.ndarray
    y_pre: np.ndarray
    y_pre2: np.ndarray
    cate: np.ndarray  # efecto condicional verdadero de cada cliente

    @property
    def att(self) -> float:
        return float(self.cate[self.d == 1].mean())


def _sig(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def generar(X: pd.DataFrame, escenario: str, semilla: int) -> Simulacion:
    """Simula tratamiento y resultados sobre las covariables ``X``."""
    if escenario not in ESCENARIOS:
        raise ValueError(escenario)
    rng = np.random.default_rng(semilla)
    n = len(X)
    act1 = X["act_m1"].fillna(0).to_numpy()
    act2 = X["act_m2"].fillna(0).to_numpy()
    otros = np.minimum(X["otros_m1"].fillna(0).to_numpy(), 4)
    edad = X["edad"].fillna(40).to_numpy()
    rel = X["relacion_activa"].fillna(0).to_numpy()
    univ = X["seg_universitario"].fillna(0).to_numpy()
    tjcr = X["x_tjcr"].fillna(0).to_numpy()
    recibo = X["x_recibo"].fillna(0).to_numpy()
    joven = (edad < 30).astype(float)

    lin_e = (
        -2.8 + 1.2 * act1 + 0.5 * otros - 0.04 * (edad - 40) + 0.6 * rel - 0.8 * univ + 0.3 * tjcr
    )
    g = (
        -1.0
        + 2.2 * act1
        + 0.8 * act2
        + 0.35 * otros
        + 0.3 * rel
        - 0.02 * (edad - 40)
        + 0.4 * recibo
        + 0.3 * np.sin(edad / 8)
    )
    if escenario == "observables":
        d = (rng.random(n) < _sig(lin_e)).astype(np.int8)
        p0 = _sig(g)
        tau = 0.10 - 0.06 * act1 + 0.06 * joven + 0.02 * np.minimum(otros, 3)
        p1 = np.clip(p0 + tau, 0, 1)
        u_res = rng.random(n)
        y0 = (u_res < p0).astype(float)
        y1 = (u_res < p1).astype(float)
        y = np.where(d == 1, y1, y0)
        y_pre = (rng.random(n) < _sig(g - 0.1)).astype(float)
        y_pre2 = (rng.random(n) < _sig(g - 0.2)).astype(float)
        return Simulacion(escenario, d, y, y_pre, y_pre2, p1 - p0)

    u = rng.normal(size=n)
    d = (rng.random(n) < _sig(lin_e + 1.0 * u)).astype(np.int8)
    tau = 0.3 + 0.2 * joven - 0.1 * act1
    tendencia_u = 0.4 if escenario == "tendencias" else 0.0
    base = 0.5 * g + u
    y_pre2 = base - tendencia_u * u + rng.normal(scale=0.5, size=n)
    y_pre = base + rng.normal(scale=0.5, size=n)
    y = base + 0.3 * act1 + tendencia_u * u + tau * d + rng.normal(scale=0.5, size=n)
    return Simulacion(escenario, d, y, y_pre, y_pre2, tau)
