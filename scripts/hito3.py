"""Hito 3: validación de métodos causales en Hillstrom y en el semisintético.

Uso:
    uv run python scripts/hito3.py hillstrom      # -> reports/hito3/hillstrom.json
    uv run python scripts/hito3.py semisintetico  # -> reports/hito3/semisintetico.json
    uv run python scripts/hito3.py graficos       # gráficos a partir de los dos JSON
"""

import argparse

from causal import base, flujo_hito3
from causal.rutas import reports_hito
from causal.util import leer_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paso", choices=("hillstrom", "semisintetico", "graficos"))
    parser.add_argument("--reps", type=int, default=10)
    args = parser.parse_args()
    salida = reports_hito(3)
    if args.paso == "hillstrom":
        flujo_hito3.validar_hillstrom(args.reps, salida)
    elif args.paso == "semisintetico":
        con = base.conectar(solo_lectura=True)
        flujo_hito3.validar_semisintetico(con, args.reps, salida=salida)
        con.close()
    else:
        flujo_hito3.graficos_hito3(
            leer_json(salida / "hillstrom.json"), leer_json(salida / "semisintetico.json"), salida
        )


if __name__ == "__main__":
    main()
