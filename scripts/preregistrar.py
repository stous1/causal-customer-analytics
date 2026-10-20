"""Escribe el preregistro de las preguntas causales (antes de estimar en Santander).

Uso:
    uv run python scripts/preregistrar.py   # -> docs/resultados/preregistro.json

Lee los conteos del hito 1 y el resumen de la validación del hito 3, calcula la positividad
de cada diseño (sin leer resultados) y guarda la huella SHA-256 del código.
"""

from causal import base, preregistro
from causal.rutas import DOCS_RESULTADOS, docs_hito
from causal.util import escribir_json, leer_json


def _resumen_validacion() -> dict:
    hs = leer_json(docs_hito(3) / "hillstrom.json")["experimento_sesgado"]
    ss = leer_json(docs_hito(3) / "semisintetico.json")["escenarios"]
    return {
        "hillstrom_sesgado": {k: v["resumen"] for k, v in hs["metodos"].items()},
        "semisintetico": {
            esc: {k: v["resumen"] for k, v in e["metodos"].items()} for esc, e in ss.items()
        },
    }


def main() -> None:
    conteos = leer_json(docs_hito(1) / "exploracion.json")["conteos_disenos"]
    contenido = preregistro.construir(conteos, _resumen_validacion())
    con = base.conectar(solo_lectura=True)
    contenido["positividad"] = preregistro.positividad(con)
    con.close()
    escribir_json(contenido, DOCS_RESULTADOS / "preregistro.json")
    print("Huellas:", contenido["huellas_sha256"])


if __name__ == "__main__":
    main()
