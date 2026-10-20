"""Datos de la página interactiva (``docs/demo.html``).

El simulador de campaña evalúa cualquier estrategia de envío en la **mitad de prueba** de
Hillstrom, la misma del hito 5. Para que el navegador pueda hacerlo sin los datos por cliente,
se resumen en seis celdas (qué compraba el cliente × historia de compra) con, para cada brazo
del experimento, clientes y visitas. Las celdas coinciden con los cortes del árbol de política
del hito 5, que se reajusta aquí con los mismos datos y parámetros y se comprueba cliente a
cliente que su acción es constante dentro de cada celda.

Valor neto de una estrategia (visitas por cliente menos el costo de los correos), estimado por
estratos: sum_k w_k * (visitas_k[accion_k] / clientes_k[accion_k] - costo * [accion_k != nada]),
con w_k = la fracción de clientes de prueba en la celda. Es la misma fórmula de
``docs/demo/motor.js`` (lo verifica ``tests/test_demo.py``).
"""

import lightgbm as lgb
import numpy as np

from causal import hillstrom
from causal.flujo_hito5 import COSTO_CORREO
from causal.metodos import _lgb_params

ACCIONES = ("sin correo", "correo de hombre", "correo de mujer")
COMPRADOR = {
    (0, 1): "solo ropa de mujer",
    (1, 0): "solo ropa de hombre",
    (1, 1): "ambas",
}


def _particion(n: int, semilla: int) -> np.ndarray:
    """La misma mitad de prueba que ``flujo_hito5.hillstrom_heterogeneidad``."""
    return np.random.default_rng(semilla).random(n) < 0.5


def arbol_hillstrom(semilla: int = 0):
    """Reajusta el árbol de política del hito 5 (mismos datos, parámetros y semilla)."""
    from econml.policy import DRPolicyTree

    df = hillstrom.cargar()
    X = hillstrom.covariables(df)
    t = (
        df["segment"]
        .map({hillstrom.CONTROL: 0, hillstrom.BRAZOS["hombre"]: 1, hillstrom.BRAZOS["mujer"]: 2})
        .to_numpy()
    )
    y = df["visit"].to_numpy(dtype=float)
    prueba = _particion(len(df), semilla)
    costo = np.where(t > 0, COSTO_CORREO, 0.0)
    params = _lgb_params(semilla)
    arbol = DRPolicyTree(
        model_regression=lgb.LGBMRegressor(**params),
        model_propensity=lgb.LGBMClassifier(**params),
        max_depth=2,
        min_samples_leaf=500,
        honest=True,
        random_state=semilla,
    )
    arbol.fit(y[~prueba] - costo[~prueba], t[~prueba], X=X[~prueba].to_numpy())
    return arbol, df, X, t, y, prueba


def valor(celdas: list[dict], asignacion: list[int], costo: float) -> dict:
    """Valor neto por cliente de una asignación (una acción por celda) y su error estándar."""
    total = sum(c["clientes_prueba"] for c in celdas)
    v, var = 0.0, 0.0
    for c, a in zip(celdas, asignacion, strict=True):
        w = c["clientes_prueba"] / total
        n, s = c["brazos"][a]["clientes"], c["brazos"][a]["visitas"]
        p = s / n
        v += w * (p - (costo if a > 0 else 0.0))
        var += w**2 * p * (1 - p) / n
    return {"valor": v, "ee": float(np.sqrt(var))}


def celdas_hillstrom(semilla: int = 0) -> dict:
    arbol, df, X, t, y, prueba = arbol_hillstrom(semilla)
    pt = arbol.policy_model_.tree_
    # umbral exacto de la historia en la rama "no compraba ropa de hombre"
    nombres = list(X.columns)
    i_mens, i_hist = nombres.index("mens"), nombres.index("log_history")
    raiz = 0
    assert pt.feature[raiz] == i_mens, "el árbol ya no corta primero por 'mens'"
    izq = pt.children_left[raiz]
    assert pt.feature[izq] == i_hist, "el árbol ya no corta por historia en la rama izquierda"
    corte_log = float(pt.threshold[izq])
    corte = float(np.exp(corte_log) - 1)

    accion_arbol = arbol.predict(X[prueba].to_numpy())
    dp = df[prueba].reset_index(drop=True)
    tp, yp = t[prueba], y[prueba]
    alta = np.log1p(dp["history"].to_numpy()) > corte_log
    celdas, inconsistentes = [], 0
    for (m, w), nombre in COMPRADOR.items():
        for es_alta, tramo in (
            (False, f"historia de hasta {corte:.0f} USD"),
            (True, f"historia de más de {corte:.0f} USD"),
        ):
            sel = (dp["mens"].to_numpy() == m) & (dp["womens"].to_numpy() == w) & (alta == es_alta)
            acciones = np.unique(accion_arbol[sel])
            inconsistentes += int(len(acciones) > 1)
            celdas.append(
                {
                    "comprador": nombre,
                    "historia": tramo,
                    "clientes_prueba": int(sel.sum()),
                    "accion_arbol": int(np.bincount(accion_arbol[sel], minlength=3).argmax()),
                    "brazos": [
                        {
                            "clientes": int((sel & (tp == a)).sum()),
                            "visitas": int(yp[sel & (tp == a)].sum()),
                        }
                        for a in range(3)
                    ],
                }
            )
    vacias = [f"{c['comprador']}, {c['historia']}" for c in celdas if c["clientes_prueba"] == 0]
    celdas = [c for c in celdas if c["clientes_prueba"] > 0]
    estrategias = {
        "nadie": [0] * len(celdas),
        "todos_hombre": [1] * len(celdas),
        "todos_mujer": [2] * len(celdas),
        "arbol": [c["accion_arbol"] for c in celdas],
    }
    return {
        "descripcion": "Hillstrom, mitad de prueba del hito 5: clientes y visitas por celda y "
        "brazo del experimento (aleatorizado: aquí se conoce la verdad).",
        "acciones": list(ACCIONES),
        "costo_hito5": COSTO_CORREO,
        "corte_historia_usd": corte,
        "celdas": celdas,
        "celdas_con_accion_mixta": inconsistentes,
        "celdas_vacias": vacias,
        "estrategias": estrategias,
        "verificacion": {k: valor(celdas, a, COSTO_CORREO) for k, a in estrategias.items()},
        "clientes_prueba": int(prueba.sum()),
        "clientes_experimento": int(len(df)),
    }
