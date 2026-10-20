"""Resumen estructurado de todo el proyecto para un agente intérprete (trabajo futuro).

Uso:
    uv run python scripts/resumen.py   # -> docs/resultados/resumen.json

Junta en un solo JSON, sin texto libre ambiguo, lo que un agente necesita para explicar los
resultados sin confundir predicción con causa: cada afirmación lleva su ``tipo``
("predictivo" o "causal"), su veredicto, las pruebas que pasó y sus limitaciones.
"""

from causal.ingesta import PRODUCTOS
from causal.preregistro import LIMITACIONES, SUPUESTOS
from causal.rutas import DOCS_RESULTADOS, docs_hito
from causal.util import escribir_json, leer_json

EXPLORATORIOS = {
    "canal_khq_jovenes": "Positividad mala (86 % de tratados con propensión > 0,95); "
    "declarado exploratorio en el preregistro: no se interpreta como causal.",
}


def main() -> None:
    h2 = leer_json(docs_hito(2) / "metricas.json")
    h4 = leer_json(docs_hito(4) / "estimaciones.json")
    exp = leer_json(docs_hito(4) / "exploratorio.json")
    h5 = leer_json(docs_hito(5) / "heterogeneidad.json")
    prereg = leer_json(DOCS_RESULTADOS / "preregistro.json")
    causal = {}
    for k, v in h4["analisis"].items():
        causal[k] = {
            "tipo": "causal",
            "pregunta": v["descripcion"],
            "primario": v["primario"],
            "estimando": v["estimando"],
            "metodo": v["metodo_principal"],
            "efecto": v["efecto"],
            "ic95": v["ic95"],
            "p_holm": v.get("p_holm"),
            "veredicto_regla": v["veredicto"],
            "veredicto_publicado": "exploratorio" if k in EXPLORATORIOS else v["veredicto"],
            "nota": EXPLORATORIOS.get(k),
            "pruebas": v["pruebas"],
            "placebo_adelanto": v.get("placebo_adelanto", {}).get("efecto"),
            "valor_robustez_ic": v["sensibilidad"]["valor_robustez_ic"],
            "n_tratados": v["n_tratados"],
        }
    predictivo = {
        p: {
            "tipo": "predictivo",
            "producto": PRODUCTOS[p][1],
            "ap_prueba": r["modelo"]["ap"],
            "ap_referencia": r["referencia"]["ap"],
            "lo_que_mas_predice": [x["nombre"] for x in h2["shap"].get(p, {}).get("variables", [])][
                :5
            ],
            "advertencia": h2["advertencia"],
        }
        for p, r in h2["productos"].items()
    }
    resumen = {
        "proyecto": "Analítica de clientes causal y explicable (Santander + Hillstrom)",
        "como_leer": {
            "predictivo": "Dice quién va a adquirir un producto. Nunca dice por qué.",
            "causal": "Dice cuánto cambia un resultado por una acción, bajo supuestos. Solo "
            "'creíble' pasó todas las pruebas preregistradas.",
            "veredictos": prereg["veredicto"],
        },
        "predictivo": {"map7": h2["map7"], "productos": predictivo},
        "causal": causal,
        "exploratorio": {"nomina_otros_productos_sin_cuenta_corriente": exp},
        "heterogeneidad": {
            "hillstrom_validado": {
                k: {
                    "qini_auc_prueba": b["qini_auc_prueba"],
                    "quintiles_prueba": b["quintiles_prueba"],
                }
                for k, b in h5["hillstrom"]["brazos"].items()
            },
            "hillstrom_politica": h5["hillstrom"]["politica"],
            "santander": {
                k: {
                    "veredicto_hito4": v.get("veredicto_hito4"),
                    "lo_que_modula_el_efecto": [x["variable"] for x in v["shap_efecto"][:5]],
                    "quintiles_mitad_independiente": v["quintiles_mitad_independiente"],
                    "politica": v["politica"],
                    "predice_contra_causa": v.get("predice_contra_causa"),
                }
                for k, v in h5["santander"].items()
            },
        },
        "supuestos": SUPUESTOS,
        "limitaciones": LIMITACIONES,
    }
    escribir_json(resumen, DOCS_RESULTADOS / "resumen.json")
    print("docs/resultados/resumen.json")


if __name__ == "__main__":
    main()
