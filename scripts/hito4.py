"""Hito 4: estimación causal en Santander (solo después del tag ``preregistro``).

Uso:
    uv run python scripts/hito4.py estimar             # -> reports/hito4/estimaciones.json
    uv run python scripts/hito4.py estimar --solo nomina_actividad
    uv run python scripts/hito4.py graficos
"""

import argparse
import subprocess

from causal import base, flujo_hito4
from causal.rutas import RAIZ, reports_hito
from causal.util import leer_json


def _hay_preregistro() -> bool:
    r = subprocess.run(
        ["git", "rev-parse", "--verify", "refs/tags/preregistro"], cwd=RAIZ, capture_output=True
    )
    return r.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paso", choices=("estimar", "graficos"))
    parser.add_argument("--solo", nargs="*")
    args = parser.parse_args()
    salida = reports_hito(4)
    if args.paso == "estimar":
        if not _hay_preregistro():
            raise SystemExit("Falta el tag 'preregistro': no se estima nada antes de preregistrar.")
        con = base.conectar(solo_lectura=True)
        res = flujo_hito4.ejecutar(con, salida, args.solo)
        con.close()
        flujo_hito4.graficos_hito4(res, salida)
    else:
        flujo_hito4.graficos_hito4(leer_json(salida / "estimaciones.json"), salida)


if __name__ == "__main__":
    main()
