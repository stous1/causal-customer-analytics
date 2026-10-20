"""Hito 2: capa predictiva con partición temporal, congelada antes de medir en prueba.

- Desarrollo: entrenamiento con t = 6 ... 11 (etiquetas de agosto de 2015 a enero de 2016) y
  validación con t = 12 y 13. Ahí se eligen los productos, la configuración y las rondas.
- Se congela ``parametros.json`` (tag ``hito2-congelado``).
- Prueba: se reentrena con t = 6 ... 13 y se mide **una sola vez** en t = 14 y 15 (etiquetas
  de abril y mayo de 2016).
"""

import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shap

from causal import graficos, prediccion
from causal.ingesta import PRODUCTOS
from causal.prediccion import Configuracion
from causal.util import escribir_json, leer_json

ENTRENAMIENTO = (6, 11)
VALIDACION = (12, 13)
ENTRENAMIENTO_FINAL = (6, 13)
PRUEBA = (14, 15)
MIN_POSITIVOS = 1000
MIN_POSITIVOS_VAL = 100  # deco y deme dejan de venderse en 2016
FRAC_NEGATIVOS = 0.1
CONFIGURACIONES = {
    "hojas31": Configuracion(num_leaves=31, min_data_in_leaf=100),
    "hojas127": Configuracion(num_leaves=127, min_data_in_leaf=300),
}
PRODUCTOS_SHAP = ("nomina", "recibo", "tjcr", "ecue")

NOMBRES_VARIABLES = {
    "edad": "Edad",
    "antiguedad": "Antigüedad (meses)",
    "log_renta": "Renta (log)",
    "renta_faltante": "Renta faltante",
    "activo": "Activo en t",
    "activo_ant": "Activo en t-1",
    "n_productos": "Número de productos",
    "n_productos_t3": "Productos en t-3",
    "altas_3m": "Altas en 3 meses",
    "bajas_3m": "Bajas en 3 meses",
    "seg_universitario": "Segmento universitario",
    "seg_top": "Segmento top",
    "relacion_activa": "Relación activa (tiprel A)",
    "mujer": "Mujer",
    "nuevo": "Cliente nuevo",
    "extranjero": "Extranjero",
    "empleado_banco": "Empleado del banco",
}


def nombre_variable(v: str) -> str:
    if v in NOMBRES_VARIABLES:
        return NOMBRES_VARIABLES[v]
    if v.endswith("_ant") and v[:-4] in PRODUCTOS:
        return f"{PRODUCTOS[v[:-4]][1]} en t-1"
    if v in PRODUCTOS:
        return f"Tiene {PRODUCTOS[v][1].lower()}"
    if v.startswith("canal_"):
        return f"Canal {v[6:].upper()}"
    if v.startswith("prov_"):
        return f"Provincia {v[5:]}"
    return v


def desarrollar(con: duckdb.DuckDBPyConnection, salida: Path) -> dict:
    """Selección de productos, configuración y rondas en validación."""
    if not con.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = 'pred'").fetchone()[
        0
    ]:
        prediccion.crear_tabla(con)
    cols = prediccion.variables(con)
    pos = prediccion.positivos_por_mes(con).set_index("t")
    en_train = pos.loc[ENTRENAMIENTO[0] : ENTRENAMIENTO[1]].sum()
    en_val = pos.loc[VALIDACION[0] : VALIDACION[1]].sum()
    productos = [
        p for p in PRODUCTOS if en_train[p] >= MIN_POSITIVOS and en_val[p] >= MIN_POSITIVOS_VAL
    ]
    resultados: dict = {}
    elegidos: dict = {}
    for p in productos:
        inicio = time.time()
        X, y, w = prediccion.cargar(con, p, *ENTRENAMIENTO, cols, FRAC_NEGATIVOS)
        Xv, yv, _ = prediccion.cargar(con, p, *VALIDACION, cols)
        X, Xv = X[cols], Xv[cols]
        ref = prediccion.referencia_ajustar(X, y, w)
        res_p = {
            "referencia": prediccion.metricas(yv, prediccion.referencia_puntuar(ref, Xv)),
            "positivos_entrenamiento": int(y.sum()),
        }
        mejor = None
        for nombre, conf in CONFIGURACIONES.items():
            modelo = prediccion.entrenar(X, y, w, conf, validacion=(Xv, yv))
            m = prediccion.metricas(yv, modelo.predict(Xv, num_iteration=modelo.best_iteration))
            m["rondas"] = int(modelo.best_iteration)
            res_p[nombre] = m
            if mejor is None or m["ap"] > res_p[mejor]["ap"]:
                mejor = nombre
        elegidos[p] = {"configuracion": mejor, "rondas": max(res_p[mejor]["rondas"], 20)}
        resultados[p] = res_p
        print(
            f"{p}: {mejor} AP val {res_p[mejor]['ap']:.4f} "
            f"(ref {res_p['referencia']['ap']:.4f}) {time.time() - inicio:.0f} s",
            flush=True,
        )
    desarrollo = {
        "ventanas": {"entrenamiento": ENTRENAMIENTO, "validacion": VALIDACION},
        "positivos_por_mes": pos.reset_index().to_dict(orient="records"),
        "productos": resultados,
        "nota": "Métricas de validación: con ellas se eligió la configuración (optimistas).",
    }
    parametros = {
        "productos": elegidos,
        "variables": cols,
        "configuraciones": {k: v.__dict__ for k, v in CONFIGURACIONES.items()},
        "frac_negativos": FRAC_NEGATIVOS,
        "min_positivos": MIN_POSITIVOS,
        "min_positivos_validacion": MIN_POSITIVOS_VAL,
        "entrenamiento_final": ENTRENAMIENTO_FINAL,
        "prueba": PRUEBA,
        "referencia": "Tasa de adquisición por celda (segmento, tramo de edad, actividad) "
        "en el entrenamiento.",
    }
    escribir_json(desarrollo, salida / "desarrollo.json")
    escribir_json(parametros, salida / "parametros.json")
    return parametros


def evaluar(con: duckdb.DuckDBPyConnection, parametros_congelados: Path, salida: Path) -> dict:
    """Reentrena con la configuración congelada y mide una sola vez en prueba."""
    par = leer_json(parametros_congelados)
    cols = par["variables"]
    confs = {k: Configuracion(**v) for k, v in par["configuraciones"].items()}
    t0, t1 = par["entrenamiento_final"]
    p0, p1 = par["prueba"]
    claves = con.execute(
        f"SELECT cliente, t FROM pred WHERE t BETWEEN {p0} AND {p1} ORDER BY t, cliente"
    ).df()
    indice = pd.MultiIndex.from_frame(claves)
    puntajes = pd.DataFrame(index=indice, columns=list(par["productos"]), dtype=float)
    puntajes_ref = puntajes.copy()
    verdad = puntajes.copy()
    resultados: dict = {}
    importancias: dict = {}
    for p, elegido in par["productos"].items():
        conf = confs[elegido["configuracion"]]
        conf.rondas = elegido["rondas"]
        X, y, w = prediccion.cargar(con, p, t0, t1, cols, par["frac_negativos"])
        Xp, yp, _ = prediccion.cargar(con, p, p0, p1, cols)
        idx = pd.MultiIndex.from_frame(Xp[["cliente", "t"]])
        X, Xp = X[cols], Xp[cols]
        modelo = prediccion.entrenar(X, y, w, conf)
        s = modelo.predict(Xp)
        ref = prediccion.referencia_ajustar(X, y, w)
        s_ref = prediccion.referencia_puntuar(ref, Xp)
        m, mr = prediccion.metricas(yp, s), prediccion.metricas(yp, s_ref)
        m["ap_ic95"] = prediccion.ic_ap(yp, s)
        mr["ap_ic95"] = prediccion.ic_ap(yp, s_ref)
        resultados[p] = {"modelo": m, "referencia": mr, "nombre": PRODUCTOS[p][1]}
        puntajes[p] = pd.Series(s, index=idx).reindex(indice)
        puntajes_ref[p] = pd.Series(s_ref, index=idx).reindex(indice)
        verdad[p] = pd.Series(yp.astype(float), index=idx).reindex(indice)
        if p in PRODUCTOS_SHAP:
            importancias[p] = importancia_shap(modelo, Xp, cols)
            # el hito 5 compara esta propensión con el efecto causal (no se versiona)
            (salida / "modelos").mkdir(parents=True, exist_ok=True)
            modelo.save_model(str(salida / "modelos" / f"{p}.txt"))
        print(f"{p}: AP prueba {m['ap']:.4f} (ref {mr['ap']:.4f})", flush=True)
    map_m, n_map = prediccion.map_k(puntajes, verdad)
    map_r, _ = prediccion.map_k(puntajes_ref, verdad)
    res = {
        "tipo": "predictivo",
        "ventanas": {"entrenamiento": [t0, t1], "prueba": [p0, p1]},
        "productos": resultados,
        "map7": {"modelo": map_m, "referencia": map_r, "clientes": n_map},
        "shap": importancias,
        "advertencia": "Importancias SHAP de un modelo predictivo: dicen qué variables usa el "
        "modelo para anticipar una adquisición, no qué la causa.",
    }
    escribir_json(res, salida / "metricas.json")
    graficos_hito2(res, salida)
    return res


def importancia_shap(modelo, Xp: pd.DataFrame, cols: list[str], n: int = 20000) -> dict:
    """Media del valor SHAP absoluto (escala log-odds) sobre una muestra fija de prueba."""
    rng = np.random.default_rng(11)
    i = np.sort(rng.choice(len(Xp), size=min(n, len(Xp)), replace=False))
    muestra = Xp.iloc[i]
    valores = shap.TreeExplainer(modelo).shap_values(muestra)
    if isinstance(valores, list):
        valores = valores[1]
    media = np.abs(valores).mean(axis=0)
    signo = [
        float(np.corrcoef(muestra[c].fillna(0), valores[:, j])[0, 1])
        if muestra[c].nunique() > 1
        else 0.0
        for j, c in enumerate(cols)
    ]
    orden = np.argsort(-media)[:15]
    return {
        "tipo": "predictivo",
        "muestra": int(len(muestra)),
        "variables": [
            {
                "variable": cols[j],
                "nombre": nombre_variable(cols[j]),
                "shap_medio_abs": float(media[j]),
                "correlacion_valor_shap": signo[j],
            }
            for j in orden
        ],
    }


def graficos_hito2(res: dict, salida: Path) -> None:
    filas = []
    for r in res["productos"].values():
        for quien, clave in (("Modelo (LightGBM)", "modelo"), ("Referencia simple", "referencia")):
            filas.append(
                {
                    "producto": r["nombre"],
                    "quien": quien,
                    "ap": r[clave]["ap"],
                    "inf": r[clave]["ap_ic95"][0],
                    "sup": r[clave]["ap_ic95"][1],
                }
            )
    df = pd.DataFrame(filas)
    g = graficos.intervalos(
        df,
        "producto",
        "ap",
        "inf",
        "sup",
        color="quien",
        titulo="Precisión promedio en prueba (abril y mayo de 2016), IC 95 %",
        eje_x="Precisión promedio (AP)",
        referencia=None,
    )
    graficos.guardar(g, salida / "ap_productos")
    for p, imp in res["shap"].items():
        d = pd.DataFrame(imp["variables"])
        g = graficos.barras_h(
            d,
            "shap_medio_abs",
            "nombre",
            titulo=f"Lo que PREDICE la adquisición de {PRODUCTOS[p][1].lower()} (SHAP, no causal)",
            eje_x="Valor SHAP absoluto medio (log-odds)",
        )
        graficos.guardar(g, salida / f"shap_{p}")
