"""Hito 3: validación de los métodos causales donde se conoce la respuesta.

1. **Hillstrom.** En el experimento completo cada método debe reproducir la diferencia de
   medias. En el experimento sesgado (tratados conservados con probabilidad conocida según sus
   covariables) debe recuperar el efecto verdadero en esos tratados, que el ingenuo no ve.
2. **Semisintético.** Efectos inyectados sobre covariables reales de Santander, en tres
   escenarios (``semisintetico.ESCENARIOS``), con varias repeticiones: sesgo, error
   cuadrático, cobertura del intervalo de 95 % y, para el bosque causal, cuánto se parece el
   efecto condicional estimado al verdadero.

Nada de este hito mira resultados reales de Santander.
"""

import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from causal import disenos, graficos, hillstrom, metodos, semisintetico
from causal.util import escribir_json

NOMBRES_METODOS = {
    "ingenuo": "Ingenuo (diferencia de medias)",
    "regresion": "Regresión lineal",
    "emparejamiento": "Emparejamiento por propensión",
    "dml_att": "Double ML (ATT)",
    "dml_att_rezago": "Double ML con resultados previos",
    "did_dr": "Diferencias en diferencias (DR)",
    "bosque_causal": "Bosque causal",
}


def _resumen(estimaciones: list[dict], verdad: list[float]) -> dict:
    """Sesgo, RMSE, cobertura y ancho medio del IC sobre repeticiones."""
    e = np.array([x["efecto"] for x in estimaciones])
    v = np.array(verdad)
    lo = np.array([x["ic95"][0] for x in estimaciones])
    hi = np.array([x["ic95"][1] for x in estimaciones])
    return {
        "sesgo": float((e - v).mean()),
        "sesgo_relativo": float(((e - v) / np.abs(v)).mean()),
        "rmse": float(np.sqrt(((e - v) ** 2).mean())),
        "cobertura": float(((lo <= v) & (v <= hi)).mean()),
        "ancho_ic": float((hi - lo).mean()),
        "repeticiones": int(len(e)),
    }


def validar_hillstrom(reps: int = 10, salida: Path | None = None) -> dict:
    df = hillstrom.cargar()
    res: dict = {"experimento_completo": {}, "experimento_sesgado": {}}
    for nombre in hillstrom.BRAZOS:
        datos = hillstrom.brazo(df, nombre)
        X = hillstrom.covariables(datos)
        d = datos["d"].to_numpy()
        for resultado in hillstrom.RESULTADOS:
            y = datos[resultado].to_numpy(dtype=float)
            verdad = hillstrom.efecto_experimento(datos, resultado)
            est = metodos.todos(X, d, y, semilla=1, con_bosque=(resultado == "visit"))
            res["experimento_completo"][f"{nombre}_{resultado}"] = {
                "verdad_experimento": verdad,
                "metodos": {k: v.como_dict() for k, v in est.items()},
            }
            print(f"Hillstrom {nombre} {resultado}: verdad {verdad['efecto']:.4f}", flush=True)
    # experimento sesgado: correo de mujer, visita
    datos = hillstrom.brazo(df, "mujer")
    X = hillstrom.covariables(datos)
    objetivo = hillstrom.efecto_objetivo_sesgado(datos, X, "visit")
    corridas: dict[str, list[dict]] = {}
    for r in range(reps):
        idx = hillstrom.sesgar(datos, X, semilla=100 + r)
        Xs = X.iloc[idx].reset_index(drop=True)
        d = datos["d"].to_numpy()[idx]
        y = datos["visit"].to_numpy(dtype=float)[idx]
        est = metodos.todos(Xs, d, y, semilla=r)
        for k, v in est.items():
            corridas.setdefault(k, []).append(v.como_dict())
        print(f"Hillstrom sesgado {r}: {[round(v.efecto, 4) for v in est.values()]}", flush=True)
    res["experimento_sesgado"] = {
        "brazo": "mujer",
        "resultado": "visit",
        "efecto_objetivo": objetivo,
        "efecto_experimento": hillstrom.efecto_experimento(datos, "visit"),
        "metodos": {
            k: {"resumen": _resumen(v, [objetivo["efecto"]] * len(v)), "corridas": v}
            for k, v in corridas.items()
        },
        "seleccion": "Se conserva cada tratado con probabilidad logística de la historia de "
        "compra (+), la recencia (-), no ser nuevo (+) y el canal web (+).",
    }
    if salida is not None:
        escribir_json(res, salida / "hillstrom.json")
    return res


def validar_semisintetico(
    con: duckdb.DuckDBPyConnection, reps: int = 10, n: int = 50000, salida: Path | None = None
) -> dict:
    X_total = disenos.leer_covariables(con, "d_nomina", "nomina")
    rng = np.random.default_rng(2024)
    X = X_total.iloc[np.sort(rng.choice(len(X_total), size=n, replace=False))]
    X = X.reset_index(drop=True)
    res: dict = {"n": n, "covariables": list(X.columns), "escenarios": {}}
    for esc in semisintetico.ESCENARIOS:
        corridas: dict[str, list[dict]] = {}
        verdades, placebos, cate = [], [], []
        for r in range(reps):
            inicio = time.time()
            sim = semisintetico.generar(X, esc, semilla=1000 * (1 + r))
            verdades.append(sim.att)
            est = metodos.todos(X, sim.d, sim.y, y_pre=sim.y_pre, semilla=r, con_bosque=False)
            # como en Santander: los resultados previos entran como covariables
            est["dml_att_rezago"] = metodos.dml_att(
                X.assign(y_previo=sim.y_pre, y_previo2=sim.y_pre2), sim.d, sim.y, semilla=r
            )
            cf, modelo = metodos.bosque_causal(
                X, sim.d, sim.y, semilla=r, arboles=200, devolver_modelo=True
            )
            est["bosque_causal"] = cf
            tau_hat = modelo.effect(metodos.matriz_bosque(X)[sim.d == 1])
            tau = sim.cate[sim.d == 1]
            cate.append(
                {
                    "correlacion": float(np.corrcoef(tau_hat, tau)[0, 1]),
                    "rmse": float(np.sqrt(((tau_hat - tau) ** 2).mean())),
                    "sd_verdadero": float(tau.std()),
                }
            )
            placebo = metodos.did_dr(X, sim.d, sim.y_pre, sim.y_pre2, semilla=r)
            placebos.append(placebo.como_dict())
            for k, v in est.items():
                corridas.setdefault(k, []).append(v.como_dict())
            print(
                f"{esc} {r}: verdad {sim.att:.4f} "
                f"{ {k: round(v.efecto, 4) for k, v in est.items()} } "
                f"placebo {placebo.efecto:.4f} ({time.time() - inicio:.0f} s)",
                flush=True,
            )
        res["escenarios"][esc] = {
            "att_verdadero_medio": float(np.mean(verdades)),
            "frac_tratados": float(
                np.mean([c["n_tratados"] / c["n"] for c in corridas["ingenuo"]])
            ),
            "metodos": {
                k: {"resumen": _resumen(v, verdades), "corridas": v} for k, v in corridas.items()
            },
            "placebo_did": {
                "resumen": _resumen(placebos, [0.0] * len(placebos)),
                "rechaza_cero": float(
                    np.mean([not (p["ic95"][0] <= 0 <= p["ic95"][1]) for p in placebos])
                ),
            },
            "bosque_cate": {
                "correlacion_media": float(np.mean([c["correlacion"] for c in cate])),
                "rmse_medio": float(np.mean([c["rmse"] for c in cate])),
                "sd_verdadero_medio": float(np.mean([c["sd_verdadero"] for c in cate])),
            },
            "verdades": verdades,
        }
        if salida is not None:
            escribir_json(res, salida / "semisintetico.json")
    return res


def graficos_hito3(hs: dict, ss: dict, salida: Path) -> None:
    filas = []
    sesg = hs["experimento_sesgado"]
    for k, v in sesg["metodos"].items():
        corr = v["corridas"]
        filas.append(
            {
                "metodo": NOMBRES_METODOS[k],
                "efecto": float(np.mean([c["efecto"] for c in corr])),
                "inf": float(np.mean([c["ic95"][0] for c in corr])),
                "sup": float(np.mean([c["ic95"][1] for c in corr])),
            }
        )
    df = pd.DataFrame(filas)
    g = graficos.intervalos(
        df,
        "metodo",
        "efecto",
        "inf",
        "sup",
        titulo="Hillstrom sesgado: efecto del correo en la visita (línea = verdad)",
        eje_x="Efecto en los tratados (puntos porcentuales de visita)",
        referencia=sesg["efecto_objetivo"]["efecto"],
    )
    graficos.guardar(g, salida / "hillstrom_sesgado")

    filas = []
    for esc, e in ss["escenarios"].items():
        for k, v in e["metodos"].items():
            r = v["resumen"]
            rel = [
                (c["efecto"] - t) / abs(t)
                for c, t in zip(v["corridas"], e["verdades"], strict=True)
            ]
            filas.append(
                {
                    "escenario": {
                        "observables": "1. Selección en observables",
                        "efecto_fijo": "2. Efecto fijo no observado",
                        "tendencias": "3. Tendencias no paralelas",
                    }[esc],
                    "metodo": NOMBRES_METODOS[k],
                    "sesgo": r["sesgo_relativo"],
                    "inf": float(np.min(rel)),
                    "sup": float(np.max(rel)),
                }
            )
    df = pd.DataFrame(filas)
    g = graficos.intervalos(
        df,
        "metodo",
        "sesgo",
        "inf",
        "sup",
        fila="escenario",
        titulo="Semisintético: sesgo relativo (punto: media de 10 corridas; barra: mín. a máx.)",
        eje_x="Sesgo relativo al efecto verdadero (0 = acierta)",
    )
    graficos.guardar(g, salida / "semisintetico_sesgo")
