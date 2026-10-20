"""Refutaciones, sensibilidad a variables omitidas y criterios de aprobación.

- **DoWhy** (``refutar_dowhy``): placebo de tratamiento (permutación), causa común aleatoria y
  subconjuntos de datos, sobre el estimador ``LinearDML`` de EconML llamado desde DoWhy.
- **Sensibilidad** (``sensibilidad``): valor de robustez de Cinelli y Hazlett (2020) a partir
  de la regresión lineal, comparado con la covariable observada más fuerte; y valor E
  (VanderWeele y Ding, 2017) para resultados binarios.
- **Criterios** (``CRITERIOS``): las reglas de aprobación preregistradas.
"""

import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
import statsmodels.api as sm

from causal.metodos import _lgb_params, _matriz

CRITERIOS = {
    "significativo": "El IC 95 % del estimador principal (Double ML, ATT) excluye el cero.",
    "placebo_permutacion": "Con el tratamiento permutado, |efecto| <= 25 % del efecto estimado.",
    "causa_comun_aleatoria": "Al agregar una covariable aleatoria, el efecto cambia <= 10 %.",
    "subconjunto": "En subconjuntos del 80 %, el efecto medio cambia <= 10 %.",
    "placebo_adelanto": "En el placebo de adelanto (tratamiento 4 meses después, resultado "
    "antes), |efecto| <= 25 % del efecto estimado.",
    "consistencia": "Emparejamiento, Double ML y bosque causal (y DiD si aplica) dan el mismo "
    "signo y el mayor no supera el doble del menor en valor absoluto.",
    "sensibilidad": "Informativo: valor de robustez frente al R² parcial de la covariable "
    "observada más fuerte. 'Robusto' si un confusor omitido tendría que ser más fuerte que "
    "esa covariable para anular el efecto.",
}


def _modelo_dowhy(df: pd.DataFrame, cols: list[str], resultado: str):
    from dowhy import CausalModel

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        modelo = CausalModel(
            data=df[cols + ["d", resultado]].assign(d=lambda x: x["d"].astype(bool)),
            treatment="d",
            outcome=resultado,
            common_causes=cols,
        )
        identificado = modelo.identify_effect(proceed_when_unidentifiable=True)
    return modelo, identificado


def _estimar_dowhy(modelo, identificado, semilla: int):

    params = _lgb_params(semilla) | {"n_estimators": 200}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return modelo.estimate_effect(
            identificado,
            method_name="backdoor.econml.dml.LinearDML",
            method_params={
                "init_params": {
                    "model_y": lgb.LGBMRegressor(**params),
                    "model_t": lgb.LGBMClassifier(**params),
                    "discrete_treatment": True,
                    "cv": 3,
                    "random_state": semilla,
                },
                "fit_params": {},
            },
        )


def refutar_dowhy(
    df: pd.DataFrame,
    cols: list[str],
    resultado: str,
    simulaciones: int = 5,
    semilla: int = 0,
) -> dict:
    """Estimación con DoWhy + LinearDML y tres refutadores de DoWhy."""
    datos = df.copy()
    datos[cols] = pd.DataFrame(
        _matriz(datos[cols])[:, : len(cols)], columns=cols, index=datos.index
    )
    modelo, identificado = _modelo_dowhy(datos, cols, resultado)
    est = _estimar_dowhy(modelo, identificado, semilla)
    efecto = float(est.value)
    salida: dict = {"efecto_dowhy_lineardml": efecto, "refutadores": {}}
    configuraciones = {
        "placebo_permutacion": ("placebo_treatment_refuter", {"placebo_type": "permute"}),
        "causa_comun_aleatoria": ("random_common_cause", {}),
        "subconjunto": ("data_subset_refuter", {"subset_fraction": 0.8}),
    }
    for nombre, (metodo, extra) in configuraciones.items():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = modelo.refute_estimate(
                identificado,
                est,
                method_name=metodo,
                num_simulations=simulaciones,
                random_seed=semilla,
                n_jobs=1,
                **extra,
            )
        nuevo = float(r.new_effect)
        p = r.refutation_result.get("p_value") if r.refutation_result else None
        if nombre == "placebo_permutacion":
            pasa = abs(nuevo) <= 0.25 * abs(efecto)
        else:
            pasa = abs(nuevo - efecto) <= 0.10 * abs(efecto)
        salida["refutadores"][nombre] = {
            "efecto_original": efecto,
            "efecto_nuevo": nuevo,
            "p_valor": None if p is None else float(p),
            "simulaciones": simulaciones,
            "pasa": bool(pasa),
            "criterio": CRITERIOS[nombre],
        }
    return salida


def _r2_parcial(t: float, gl: int) -> float:
    return t**2 / (t**2 + gl)


def valor_robustez(t: float, gl: int, q: float = 1.0) -> float:
    """Valor de robustez RV_q (Cinelli y Hazlett, 2020): fuerza mínima (R² parcial con el
    tratamiento y con el resultado) de un confusor omitido para reducir el efecto en q·100 %."""
    f = q * abs(t) / np.sqrt(gl)
    return float(0.5 * (np.sqrt(f**4 + 4 * f**2) - f**2))


def sensibilidad(df: pd.DataFrame, cols: list[str], resultado: str) -> dict:
    """Valor de robustez de la regresión lineal y R² parciales de las covariables observadas."""
    A = _matriz(df[cols])
    A = A[:, : len(cols)]
    var = A.std(axis=0) > 0
    nombres = [c for c, v in zip(cols, var, strict=True) if v]
    A = A[:, var]
    d = df["d"].to_numpy(dtype=float)
    y = df[resultado].to_numpy(dtype=float)
    M = sm.add_constant(np.column_stack([d, A]), has_constant="add")
    r = sm.OLS(y, M).fit()
    gl = int(r.df_resid)
    t_d = float(r.tvalues[1])
    # R² parcial de cada covariable con el resultado (dado d y el resto) y con el tratamiento
    r2_y = {n: _r2_parcial(float(r.tvalues[2 + i]), gl) for i, n in enumerate(nombres)}
    rd = sm.OLS(d, sm.add_constant(A, has_constant="add")).fit()
    r2_d = {
        n: _r2_parcial(float(rd.tvalues[1 + i]), int(rd.df_resid)) for i, n in enumerate(nombres)
    }
    fuerte = max(nombres, key=lambda n: min(r2_y[n], r2_d[n]))
    rv = valor_robustez(t_d, gl)
    rv_ic = valor_robustez(max(abs(t_d) - 1.96, 0.0), gl)
    return {
        "efecto_mco": float(r.params[1]),
        "t": t_d,
        "r2_parcial_tratamiento_resultado": _r2_parcial(t_d, gl),
        "valor_robustez": rv,
        "valor_robustez_ic": rv_ic,
        "covariable_mas_fuerte": fuerte,
        "r2_parcial_y_mas_fuerte": r2_y[fuerte],
        "r2_parcial_d_mas_fuerte": r2_d[fuerte],
        "max_r2_parcial_y": max(r2_y.values()),
        "max_r2_parcial_d": max(r2_d.values()),
        "robusto": bool(rv_ic > min(r2_y[fuerte], r2_d[fuerte])),
        "interpretacion": "Un confusor omitido que explique más de valor_robustez de la "
        "varianza residual del tratamiento y del resultado anularía el efecto; con "
        "valor_robustez_ic, el IC dejaría de excluir el cero.",
    }


def valor_e(riesgo_tratados: float, riesgo_control: float) -> dict:
    """Valor E para un cociente de riesgos (resultado binario)."""
    rr = riesgo_tratados / riesgo_control if riesgo_control > 0 else np.inf
    rr_ = rr if rr >= 1 else 1 / rr
    return {"cociente_riesgos": float(rr), "valor_e": float(rr_ + np.sqrt(rr_ * (rr_ - 1)))}


def consistencia(estimaciones: dict[str, float]) -> dict:
    """Mismo signo y razón máx/mín <= 2 entre métodos."""
    v = np.array(list(estimaciones.values()))
    mismo_signo = bool((v > 0).all() or (v < 0).all())
    razon = float(np.abs(v).max() / np.abs(v).min()) if (np.abs(v) > 0).all() else np.inf
    return {
        "estimaciones": estimaciones,
        "mismo_signo": mismo_signo,
        "razon_max_min": razon,
        "pasa": bool(mismo_signo and razon <= 2.0),
        "criterio": CRITERIOS["consistencia"],
    }


def holm(p_valores: dict[str, float]) -> dict[str, float]:
    """p-valores ajustados por Holm-Bonferroni."""
    claves = sorted(p_valores, key=p_valores.get)
    m = len(claves)
    ajust, previo = {}, 0.0
    for i, k in enumerate(claves):
        previo = max(previo, min(1.0, (m - i) * p_valores[k]))
        ajust[k] = previo
    return ajust
