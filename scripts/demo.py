"""Datos de la página interactiva ``docs/demo.html``.

Uso:
    uv run python scripts/demo.py   # -> docs/resultados/demo/hillstrom_celdas.json (~1 min)
"""

from causal import demo
from causal.rutas import DOCS_RESULTADOS
from causal.util import escribir_json


def main() -> None:
    datos = demo.celdas_hillstrom()
    if datos["celdas_con_accion_mixta"]:
        raise SystemExit("El árbol no es constante dentro de las celdas: revisar los cortes.")
    escribir_json(datos, DOCS_RESULTADOS / "demo" / "hillstrom_celdas.json")
    print({k: round(v["valor"], 4) for k, v in datos["verificacion"].items()})
    print(round(datos["corte_historia_usd"], 2), [c["accion_arbol"] for c in datos["celdas"]])


if __name__ == "__main__":
    main()
