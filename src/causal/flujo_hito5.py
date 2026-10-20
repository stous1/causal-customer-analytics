"""Hito 5: efectos heterogéneos, SHAP sobre el efecto causal y árboles de política.

1. **Hillstrom (con verdad):** bosque causal entrenado en una mitad del experimento; en la
   otra mitad se comprueba si los clientes con mayor efecto estimado tienen de verdad mayor
   efecto (deciles, Qini). Un árbol de política de profundidad 2 elige entre correo de hombre,
   correo de mujer o nada, con un costo por correo, y su valor se mide en la mitad de prueba
   con ponderación por la probabilidad conocida de cada brazo.
2. **Santander (sin verdad):** bosque causal sobre los diseños preregistrados; SHAP sobre el
   efecto condicional (qué hace que la acción funcione mejor en unos clientes que en otros);
   árbol de política ajustado en una mitad y evaluado en la otra con puntajes doble robustos.
   Y el contraste "lo que predice" contra "lo que causa": la propensión a adquirir (hito 2)
   frente al efecto de adquirir.

Nada de esto convierte una asociación en causa: en Santander los efectos condicionales
heredan los supuestos y el veredicto del hito 4.
"""

from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd

from causal import flujo_hito4, graficos, hillstrom, metodos
from causal.metodos import _lgb_params

COSTO_CORREO = 0.05  # visitas: supuesto ilustrativo del costo de enviar un correo
VARIABLES_POLITICA_SANTANDER = (
    "edad",
    "act_m1",
    "act_m3",
    "otros_m1",
    "log_renta",
    "antiguedad",
    "seg_universitario",
    "seg_top",
    "mujer",
    "relacion_activa",
    "x_cco",
    "x_tjcr",
    "x_recibo",
)


def _bosque(X: np.ndarray, d: np.ndarray, y: np.ndarray, semilla: int, arboles: int = 400):
    from econml.dml import CausalForestDML

    params = _lgb_params(semilla)
    cf = CausalForestDML(
        model_y=lgb.LGBMRegressor(**params),
        model_t=lgb.LGBMClassifier(**params),
        discrete_treatment=True,
        n_estimators=arboles,
        min_samples_leaf=20,
        max_samples=0.45,
        cv=3,
        random_state=semilla,
        n_jobs=8,
    )
    cf.fit(y.astype(float), d.astype(int), X=X)
    return cf


def _shap_cate(cf, X: np.ndarray, nombres: list[str], n: int = 2000, semilla: int = 0) -> list:
    rng = np.random.default_rng(semilla)
    i = np.sort(rng.choice(len(X), size=min(n, len(X)), replace=False))
    valores = cf.shap_values(X[i], feature_names=nombres, background_samples=100)
    clave_y = next(iter(valores))
    exp = valores[clave_y][next(iter(valores[clave_y]))]
    media = np.abs(exp.values).mean(axis=0)
    orden = np.argsort(-media)
    return [
        {
            "variable": nombres[j],
            "shap_medio_abs": float(media[j]),
            "correlacion_valor_shap": float(np.corrcoef(X[i][:, j], exp.values[:, j])[0, 1])
            if np.std(X[i][:, j]) > 0
            else 0.0,
        }
        for j in orden[:12]
    ]


def _deciles(cate: np.ndarray, d: np.ndarray, y: np.ndarray, grupos: int = 5) -> list[dict]:
    """Efecto real (diferencia de medias del experimento) por quintil del efecto estimado."""
    cortes = np.quantile(cate, np.linspace(0, 1, grupos + 1))
    g = np.clip(np.searchsorted(cortes, cate, side="right") - 1, 0, grupos - 1)
    salida = []
    for k in range(grupos):
        m = g == k
        y1, y0 = y[m & (d == 1)], y[m & (d == 0)]
        ee = np.sqrt(y1.var(ddof=1) / len(y1) + y0.var(ddof=1) / len(y0))
        efecto = y1.mean() - y0.mean()
        salida.append(
            {
                "grupo": k + 1,
                "cate_estimado_medio": float(cate[m].mean()),
                "efecto_real": float(efecto),
                "ic95": [float(efecto - 1.96 * ee), float(efecto + 1.96 * ee)],
                "n": int(m.sum()),
            }
        )
    return salida


def _reglas(arbol, nombres: list[str], acciones: list[str]) -> list[str]:
    """Hojas de un árbol de política como reglas legibles."""
    t = arbol.policy_model_.tree_
    reglas = []

    def recorrer(nodo: int, condiciones: list[str]) -> None:
        if t.children_left[nodo] == -1:
            valor = np.ravel(t.value[nodo])
            accion = acciones[int(np.argmax(valor))] if len(valor) == len(acciones) else str(valor)
            reglas.append(" y ".join(condiciones or ["todos"]) + f" -> {accion}")
            return
        f, u = nombres[t.feature[nodo]], t.threshold[nodo]
        recorrer(t.children_left[nodo], condiciones + [f"{f} <= {u:.2f}"])
        recorrer(t.children_right[nodo], condiciones + [f"{f} > {u:.2f}"])

    recorrer(0, [])
    return reglas


def _valor_ipw(
    y: np.ndarray,
    t: np.ndarray,
    accion: np.ndarray,
    prob: float,
    costo: np.ndarray,
    reps: int = 300,
    semilla: int = 0,
) -> dict:
    """Valor neto de una política con la probabilidad conocida de cada brazo (experimento)."""
    v = (t == accion) * (y - costo) / prob
    rng = np.random.default_rng(semilla)
    boot = [v[rng.integers(0, len(v), len(v))].mean() for _ in range(reps)]
    return {
        "valor": float(v.mean()),
        "ic95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
    }


def hillstrom_heterogeneidad(semilla: int = 0) -> dict:
    df = hillstrom.cargar()
    X = hillstrom.covariables(df)
    nombres = list(X.columns)
    t = (
        df["segment"]
        .map({hillstrom.CONTROL: 0, hillstrom.BRAZOS["hombre"]: 1, hillstrom.BRAZOS["mujer"]: 2})
        .to_numpy()
    )
    y = df["visit"].to_numpy(dtype=float)
    rng = np.random.default_rng(semilla)
    prueba = rng.random(len(df)) < 0.5
    A, B = ~prueba, prueba
    res: dict = {"particion": {"entrenamiento": int(A.sum()), "prueba": int(B.sum())}, "brazos": {}}
    from sklift.metrics import qini_auc_score

    for k, nombre in ((1, "hombre"), (2, "mujer")):
        sel_a, sel_b = A & np.isin(t, [0, k]), B & np.isin(t, [0, k])
        d_a, d_b = (t[sel_a] == k).astype(int), (t[sel_b] == k).astype(int)
        Xa, Xb = X[sel_a].to_numpy(), X[sel_b].to_numpy()
        cf = _bosque(Xa, d_a, y[sel_a], semilla)
        cate_b = cf.effect(Xb)
        res["brazos"][nombre] = {
            "quintiles_prueba": _deciles(cate_b, d_b, y[sel_b]),
            "qini_auc_prueba": float(qini_auc_score(y[sel_b], cate_b, d_b)),
            "cate_sd": float(np.std(cate_b)),
            "shap_efecto": _shap_cate(cf, Xb, nombres, semilla=semilla),
        }
    # árbol de política: nada, hombre o mujer, con costo por correo
    from econml.policy import DRPolicyTree

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
    arbol.fit(y[A] - costo[A], t[A], X=X[A].to_numpy())
    accion_b = arbol.predict(X[B].to_numpy())
    acciones = ["sin correo", "correo de hombre", "correo de mujer"]
    politicas = {
        "arbol": accion_b,
        "todos_hombre": np.ones(B.sum(), dtype=int),
        "todos_mujer": np.full(B.sum(), 2),
        "nadie": np.zeros(B.sum(), dtype=int),
    }
    valores = {k: _valor_ipw(y[B], t[B], v, 1 / 3, costo[B]) for k, v in politicas.items()}
    res["politica"] = {
        "costo_por_correo_en_visitas": COSTO_CORREO,
        "reglas": _reglas(arbol, nombres, acciones),
        "reparto_prueba": {acciones[i]: float((accion_b == i).mean()) for i in range(3)},
        "valor_neto_prueba": valores,
        "nota": "Valor neto por cliente = visitas menos costo de los correos enviados, "
        "estimado en la mitad de prueba con la probabilidad conocida de cada brazo (1/3).",
    }
    return res


def _puntajes_dr(X: pd.DataFrame, d: np.ndarray, y: np.ndarray, semilla: int) -> np.ndarray:
    """Puntaje doble robusto individual del efecto (AIPW), con ajuste cruzado."""
    m, g0, g1 = metodos.auxiliares_cruzadas(X, d, y, semilla=semilla)
    return g1 - g0 + d * (y - g1) / m - (1 - d) * (y - g0) / (1 - m)


def santander_heterogeneidad(
    con: duckdb.DuckDBPyConnection, analisis_id: str, modelos_hito2: Path | None, semilla: int = 0
) -> dict:
    a = next(x for x in flujo_hito4.ANALISIS if x.id == analisis_id)
    df, cols = flujo_hito4.cargar(con, a)
    df = flujo_hito4._submuestra(df, flujo_hito4.MAX_FILAS_BOSQUE, semilla)
    X, d, y = df[cols], df["d"].to_numpy(), df[a.resultado].to_numpy(dtype=float)
    Xm = metodos.matriz_bosque(X)
    nombres = cols + [f"{c}_faltante" for c in cols if X[c].isna().any()]
    cf = _bosque(Xm, d, y, semilla)
    cate = cf.effect(Xm)
    tratados = d == 1
    res: dict = {
        "analisis": analisis_id,
        "descripcion": a.descripcion,
        "cate_tratados": {
            "media": float(cate[tratados].mean()),
            "p10": float(np.percentile(cate[tratados], 10)),
            "p50": float(np.percentile(cate[tratados], 50)),
            "p90": float(np.percentile(cate[tratados], 90)),
        },
        "shap_efecto": _shap_cate(cf, Xm[tratados], nombres, semilla=semilla),
        "tipo": "causal (efecto condicional)",
    }
    # grupos por quintil del CATE con su efecto doble robusto (mitad no usada para ordenar)
    rng = np.random.default_rng(semilla)
    mitad = rng.random(len(df)) < 0.5
    dr = _puntajes_dr(X, d, y, semilla)
    cf_a = _bosque(Xm[~mitad], d[~mitad], y[~mitad], semilla + 1, arboles=200)
    cate_b = cf_a.effect(Xm[mitad])
    cortes = np.quantile(cate_b, np.linspace(0, 1, 6))
    g = np.clip(np.searchsorted(cortes, cate_b, side="right") - 1, 0, 4)
    quint = []
    for k in range(5):
        v = dr[mitad][g == k]
        quint.append(
            {
                "grupo": k + 1,
                "cate_estimado_medio": float(cate_b[g == k].mean()),
                "efecto_dr": float(v.mean()),
                "ic95": [
                    float(v.mean() - 1.96 * v.std(ddof=1) / np.sqrt(len(v))),
                    float(v.mean() + 1.96 * v.std(ddof=1) / np.sqrt(len(v))),
                ],
            }
        )
    res["quintiles_mitad_independiente"] = quint
    # árbol de política: aplicar la acción solo donde el efecto supera el promedio (ATT)
    from econml.policy import PolicyTree

    vp = [c for c in VARIABLES_POLITICA_SANTANDER if c in X.columns]
    att = float(dr[d == 1].mean())
    beneficio = dr - att
    arbol = PolicyTree(max_depth=2, min_samples_leaf=2000, honest=True, random_state=semilla)
    Xp = X[vp].fillna(X[vp].median()).to_numpy()
    arbol.fit(Xp[~mitad], np.column_stack([np.zeros((~mitad).sum()), beneficio[~mitad]]))
    hoja_b = arbol.predict(Xp[mitad])
    res["politica"] = {
        "variables": vp,
        "umbral": "efecto mayor que el promedio (ATT doble robusto)",
        "att_dr": att,
        "reglas": _reglas_policy(arbol, vp),
        "efecto_dr_mitad_prueba": {
            "recomendados": float(dr[mitad][hoja_b == 1].mean()) if (hoja_b == 1).any() else None,
            "no_recomendados": float(dr[mitad][hoja_b == 0].mean())
            if (hoja_b == 0).any()
            else None,
            "frac_recomendados": float((hoja_b == 1).mean()),
        },
    }
    if modelos_hito2 is not None and analisis_id.startswith("producto_"):
        res["predice_contra_causa"] = predice_contra_causa(
            con, df, cate, analisis_id, modelos_hito2
        )
    return res


def _reglas_policy(arbol, nombres: list[str]) -> list[str]:
    t = arbol.tree_
    reglas = []

    def recorrer(nodo: int, cond: list[str]) -> None:
        if t.children_left[nodo] == -1:
            valor = np.ravel(t.value[nodo])
            reglas.append(
                " y ".join(cond or ["todos"])
                + (" -> aplicar" if np.argmax(valor) == 1 else " -> no aplicar")
            )
            return
        f, u = nombres[t.feature[nodo]], t.threshold[nodo]
        recorrer(t.children_left[nodo], cond + [f"{f} <= {u:.2f}"])
        recorrer(t.children_right[nodo], cond + [f"{f} > {u:.2f}"])

    recorrer(0, [])
    return reglas


def predice_contra_causa(
    con: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    cate: np.ndarray,
    analisis_id: str,
    modelos: Path,
) -> dict:
    """Propensión a adquirir el producto (modelo del hito 2, en t-1) frente al efecto
    estimado de adquirirlo, en los mismos clientes del diseño."""
    from scipy.stats import spearmanr

    p = analisis_id.removeprefix("producto_")
    ruta = modelos / f"{p}.txt"
    if not ruta.exists():
        return {"nota": f"falta {ruta}: correr el hito 2 (evaluar) antes"}
    booster = lgb.Booster(model_file=str(ruta))
    cols = booster.feature_name()
    claves = df[["cliente", "t"]].copy()
    con.register("claves_pc", claves)
    feats = con.execute(
        f"SELECT k.cliente, k.t, {', '.join('p.' + c for c in cols)} FROM claves_pc k "
        "JOIN pred p ON p.cliente = k.cliente AND p.t = k.t - 1"
    ).df()
    con.unregister("claves_pc")
    unido = claves.assign(cate=cate).merge(feats, on=["cliente", "t"], how="inner")
    prop = booster.predict(unido[cols])
    rho = spearmanr(prop, unido["cate"]).statistic
    q = pd.qcut(prop, 5, labels=False, duplicates="drop")
    por_q = unido.assign(q=q).groupby("q")["cate"].mean()
    return {
        "correlacion_spearman": float(rho),
        "cate_medio_por_quintil_de_propension": {int(k) + 1: float(v) for k, v in por_q.items()},
        "n": int(len(unido)),
        "lectura": "Si la correlación es baja, los clientes que más probablemente adquieren el "
        "producto no son aquellos en quienes adquirirlo más cambia el resultado.",
    }


def graficos_hito5(res: dict, salida: Path) -> None:
    filas = []
    for nombre, b in res["hillstrom"]["brazos"].items():
        for q in b["quintiles_prueba"]:
            filas.append(
                {
                    "brazo": f"Correo de {nombre}",
                    "grupo": f"Q{q['grupo']}",
                    "efecto": q["efecto_real"],
                    "inf": q["ic95"][0],
                    "sup": q["ic95"][1],
                }
            )
    g = graficos.intervalos(
        pd.DataFrame(filas),
        "grupo",
        "efecto",
        "inf",
        "sup",
        color="brazo",
        titulo="Hillstrom, mitad de prueba: efecto real por quintil del efecto estimado",
        eje_x="Efecto real en la visita (diferencia del experimento)",
    )
    graficos.guardar(g, salida / "hillstrom_quintiles")
    filas = []
    for s in res["santander"].values():
        for v in s["shap_efecto"][:8]:
            filas.append(
                {
                    "analisis": s["descripcion"],
                    "variable": v["variable"],
                    "shap": v["shap_medio_abs"],
                }
            )
    if filas:
        import altair as alt

        g = (
            alt.Chart(pd.DataFrame(filas))
            .mark_bar(color=graficos.VERDE)
            .encode(
                x=alt.X("shap:Q", title="SHAP medio absoluto sobre el efecto"),
                y=alt.Y("variable:N", sort="-x", title=None),
            )
            .properties(width=300, height=160)
            .facet(row=alt.Row("analisis:N", title=None))
            .resolve_scale(y="independent")
            .properties(
                title="Qué hace que el EFECTO sea mayor o menor (SHAP sobre el bosque causal)"
            )
        )
        graficos.guardar(g, salida / "shap_efecto")
