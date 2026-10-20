"""Hito 5: efectos heterogéneos, SHAP sobre el efecto y árboles de política.

Uso:
    uv run python scripts/hito5.py   # -> reports/hito5/heterogeneidad.json y gráficos

Requiere el hito 4 (estimaciones.json, para elegir los análisis) y, para el contraste
"predice contra causa", los modelos de ``reports/hito2/modelos/`` (hito 2, evaluar).
"""

from causal import base, flujo_hito5
from causal.rutas import reports_hito
from causal.util import escribir_json, leer_json


def main() -> None:
    salida = reports_hito(5)
    est = leer_json(reports_hito(4) / "estimaciones.json")["analisis"]
    # los análisis primarios con efecto distinto de cero
    elegidos = [
        k for k, v in est.items() if v["primario"] and v["veredicto"] != "sin efecto detectable"
    ]
    res = {"hillstrom": flujo_hito5.hillstrom_heterogeneidad(), "santander": {}}
    escribir_json(res, salida / "heterogeneidad.json")
    con = base.conectar(solo_lectura=True)
    for a in elegidos:
        r = flujo_hito5.santander_heterogeneidad(con, a, reports_hito(2) / "modelos")
        r["veredicto_hito4"] = est[a]["veredicto"]
        res["santander"][a] = r
        print(a, r["cate_tratados"], flush=True)
        escribir_json(res, salida / "heterogeneidad.json")
    con.close()
    flujo_hito5.graficos_hito5(res, salida)


if __name__ == "__main__":
    main()
