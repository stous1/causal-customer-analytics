"""Hito 2: capa predictiva (propensión a adquirir cada producto el mes siguiente).

Uso:
    uv run python scripts/hito2.py desarrollar   # validación -> reports/hito2/parametros.json
    uv run python scripts/publicar_resultados.py --hito 2 --solo-parametros  # congelar + tag
    uv run python scripts/hito2.py evaluar       # prueba, una vez, con los parámetros publicados
"""

import argparse

from causal import base, flujo_hito2
from causal.rutas import docs_hito, reports_hito


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paso", choices=("desarrollar", "evaluar"))
    args = parser.parse_args()
    # Con la tabla ``pred`` ya creada basta una conexión de solo lectura (permite correr otros
    # pasos en paralelo).
    con = base.conectar(solo_lectura=True)
    existe = con.execute(
        "SELECT count(*) FROM duckdb_tables() WHERE table_name = 'pred'"
    ).fetchone()[0]
    if not existe:
        con.close()
        con = base.conectar()
    if args.paso == "desarrollar":
        flujo_hito2.desarrollar(con, reports_hito(2))
    else:
        flujo_hito2.evaluar(con, docs_hito(2) / "parametros.json", reports_hito(2))
    con.close()


if __name__ == "__main__":
    main()
