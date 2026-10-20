"""Hito 1: ingesta, calidad del dato, exploración y diseños.

Uso:
    uv run python scripts/hito1.py preparar   # CSV -> data/santander.duckdb (~2 min)
    uv run python scripts/hito1.py explorar   # -> reports/hito1/exploracion.json y gráficos
"""

import argparse

from causal import base, flujo_hito1
from causal.rutas import CSV_SANTANDER, reports_hito
from causal.util import escribir_json, leer_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paso", choices=("preparar", "explorar"))
    args = parser.parse_args()
    salida = reports_hito(1)
    con = base.conectar()
    if args.paso == "preparar":
        carga = flujo_hito1.preparar(con, CSV_SANTANDER)
        escribir_json(carga, salida / "carga.json")
        print(carga)
    else:
        ruta_carga = salida / "carga.json"
        carga = leer_json(ruta_carga) if ruta_carga.exists() else None
        res = flujo_hito1.explorar(con, carga, salida)
        print({k: v.get("tratados", v.get("por_canal")) for k, v in res["conteos_disenos"].items()})
    con.close()


if __name__ == "__main__":
    main()
