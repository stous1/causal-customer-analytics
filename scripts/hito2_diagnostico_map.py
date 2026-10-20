"""Diagnóstico del MAP@7 del hito 2 (no cambia el modelo congelado).

Uso:
    uv run python scripts/hito2_diagnostico_map.py   # -> reports/hito2/diagnostico_map.json

Reentrena con ``docs/resultados/hito2/parametros.json`` exactamente como ``evaluar``
(LightGBM determinista) y comprueba que la AP de prueba de cada producto coincide con la
publicada: es el mismo modelo. Sobre esas mismas predicciones calcula el MAP@7 con varias
definiciones, para saber qué mide la cifra publicada y cuánto se compara con Kaggle:

- ``publicada``: clientes-mes con al menos una adquisición entre los 13 productos modelados.
- ``24_productos``: clientes-mes con al menos una adquisición de cualquiera de los 24; las de
  productos no modelados cuentan como no acertadas.
- ``todos_los_clientes``: promedio sobre todos los clientes-mes con etiqueta, con AP = 0 para
  quien no adquiere nada (como la tabla de posiciones de Kaggle).
- ``nuevo_estricto``: solo cuenta como adquisición un producto que el cliente no tenía ni en t
  ni en t-1 (las nóminas que van y vienen dejan de contar).
"""

import numpy as np
import pandas as pd

from causal import base, prediccion
from causal.ingesta import PRODUCTOS
from causal.prediccion import Configuracion
from causal.rutas import docs_hito, reports_hito
from causal.util import escribir_json, leer_json


def main() -> None:
    par = leer_json(docs_hito(2) / "parametros.json")
    publicadas = leer_json(docs_hito(2) / "metricas.json")
    cols = par["variables"]
    t0, t1 = par["entrenamiento_final"]
    p0, p1 = par["prueba"]
    con = base.conectar(solo_lectura=True)
    todos = list(PRODUCTOS)
    base_df = con.execute(
        f"SELECT cliente, t, {', '.join(todos)}, {', '.join(p + '_ant' for p in todos)}, "
        f"{', '.join('y_' + p for p in todos)} FROM pred WHERE t BETWEEN {p0} AND {p1} "
        "ORDER BY t, cliente"
    ).df()
    indice = pd.MultiIndex.from_frame(base_df[["cliente", "t"]])
    verdad = pd.DataFrame(
        {p: base_df[f"y_{p}"].astype(float).to_numpy() for p in todos}, index=indice
    )
    modelo = pd.DataFrame(np.nan, index=indice, columns=todos)
    referencia = modelo.copy()
    coincide = {}
    for p, elegido in par["productos"].items():
        conf = Configuracion(**par["configuraciones"][elegido["configuracion"]])
        conf.rondas = elegido["rondas"]
        X, y, w = prediccion.cargar(con, p, t0, t1, cols, par["frac_negativos"])
        Xp, yp, _ = prediccion.cargar(con, p, p0, p1, cols)
        idx = pd.MultiIndex.from_frame(Xp[["cliente", "t"]])
        X, Xp = X[cols], Xp[cols]
        s = prediccion.entrenar(X, y, w, conf).predict(Xp)
        ref = prediccion.referencia_ajustar(X, y, w)
        modelo[p] = pd.Series(s, index=idx).reindex(indice)
        referencia[p] = pd.Series(prediccion.referencia_puntuar(ref, Xp), index=idx).reindex(indice)
        ap = prediccion.metricas(yp, s)["ap"]
        coincide[p] = abs(ap - publicadas["productos"][p]["modelo"]["ap"]) < 1e-9
        print(p, round(ap, 4), coincide[p], flush=True)
    con.close()

    modelados = list(par["productos"])
    # comprobación de la definición: nadie tiene etiqueta en un producto que ya tenía en t
    tenia = base_df[todos].to_numpy() == 1
    etiqueta_con_tenencia = int((~np.isnan(verdad.to_numpy()) & tenia).sum())
    puntaje_con_tenencia = int(
        (
            ~np.isnan(modelo[modelados].to_numpy()) & tenia[:, [todos.index(p) for p in modelados]]
        ).sum()
    )
    tenia_ant = base_df[[p + "_ant" for p in todos]].fillna(0).to_numpy() == 1
    estricta = verdad.where(~tenia_ant, 0.0)
    altas = np.nan_to_num(verdad.to_numpy()) == 1
    vuelven = {
        p: float((altas[:, i] & tenia_ant[:, i]).sum() / max(altas[:, i].sum(), 1))
        for i, p in enumerate(todos)
        if p in modelados
    }

    def resumen(puntajes: pd.DataFrame) -> dict:
        solo13 = prediccion.ap_por_fila(puntajes[modelados], verdad[modelados])
        con24 = prediccion.ap_por_fila(puntajes, verdad)
        etiquetadas = ~np.isnan(verdad.to_numpy()).all(axis=1)
        estr = prediccion.ap_por_fila(puntajes, estricta)
        return {
            "publicada": {
                "map7": float(np.nanmean(solo13)),
                "clientes_mes": int((~np.isnan(solo13)).sum()),
            },
            "24_productos": {
                "map7": float(np.nanmean(con24)),
                "clientes_mes": int((~np.isnan(con24)).sum()),
            },
            "todos_los_clientes": {
                "map7": float(np.nan_to_num(con24)[etiquetadas].mean()),
                "clientes_mes": int(etiquetadas.sum()),
            },
            "nuevo_estricto": {
                "map7": float(np.nanmean(estr)),
                "clientes_mes": int((~np.isnan(estr)).sum()),
            },
        }

    # referencia trivial: popularidad global de cada producto en entrenamiento
    popularidad = {
        p: float(par_pos)
        for p, par_pos in zip(
            modelados,
            [publicadas["productos"][p]["referencia"]["tasa_base"] for p in modelados],
            strict=True,
        )
    }
    pop = modelo.copy()
    for p in modelados:
        pop[p] = np.where(modelo[p].isna(), np.nan, popularidad[p])
    salida = {
        "tipo": "diagnóstico (el modelo congelado no cambia)",
        "mismo_modelo": {"ap_coincide_con_publicada": coincide, "todos": all(coincide.values())},
        "definicion": {
            "etiqueta": "1 si el cliente no tenía el producto en t y lo tiene en t+1",
            "etiquetas_en_productos_ya_tenidos": etiqueta_con_tenencia,
            "puntajes_en_productos_ya_tenidos": puntaje_con_tenencia,
            "conclusion": "Solo productos nuevos respecto de t, como en Kaggle.",
        },
        "frac_altas_que_vuelven_tras_tenerlo_en_t_menos_1": vuelven,
        "map7": {
            "modelo": resumen(modelo),
            "referencia": resumen(referencia),
            "popularidad_global": resumen(pop),
        },
    }
    escribir_json(salida, reports_hito(2) / "diagnostico_map.json")
    print(salida["definicion"], salida["map7"])


if __name__ == "__main__":
    main()
