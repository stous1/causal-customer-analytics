"""Hito 4, análisis EXPLORATORIO (no preregistrado): nómina -> otros productos sin la cuenta
corriente.

Uso:
    uv run python scripts/hito4_exploratorio.py   # -> reports/hito4/exploratorio.json

El resultado preregistrado (cambio en otros productos) cae al iniciar la nómina porque la
cuenta corriente se reemplaza por la cuenta nómina. Aquí se descompone el cambio por producto
y se repite la estimación excluyendo también la cuenta corriente. Se informa como
exploratorio: no estaba en el preregistro.
"""

import numpy as np

from causal import base, flujo_hito4, metodos
from causal.ingesta import PRODUCTOS
from causal.rutas import reports_hito
from causal.util import escribir_json


def main() -> None:
    con = base.conectar(solo_lectura=True)
    dif = ", ".join(
        f"avg(b.{p}::INT - a.{p}::INT) FILTER (WHERE d.d = 1) - "
        f"avg(b.{p}::INT - a.{p}::INT) FILTER (WHERE d.d = 0) AS {p}"
        for p in PRODUCTOS
    )
    unir = (
        "JOIN panel a ON a.cliente = d.cliente AND a.mes = d.t - 1 "
        "JOIN panel b ON b.cliente = d.cliente AND b.mes = d.t + 3"
    )
    descomp = con.execute(f"SELECT {dif} FROM d_nomina d {unir}").df().iloc[0].to_dict()
    cambio = con.execute(
        f"""SELECT avg((a.cco = 1 AND b.cco = 0 AND b.cno = 1)::INT) FILTER (WHERE d.d = 1)
            FROM d_nomina d {unir}"""
    ).fetchone()[0]
    salida = {
        "tipo": "exploratorio (no preregistrado)",
        "descomposicion_sin_ajuste": {
            "descripcion": "Cambio t-1 a t+3 por producto: tratados menos controles, sin ajuste",
            "productos": descomp,
        },
        "frac_tratados_cambian_cuenta_corriente_por_nomina": cambio,
    }
    a = next(x for x in flujo_hito4.ANALISIS if x.id == "nomina_productos")
    for nombre, tabla in (("principal", a.tabla), ("placebo_adelanto", a.tabla_placebo)):
        df, cols = flujo_hito4.cargar(con, a, tabla)
        cco = con.execute(
            f"SELECT d.cliente, d.t, b.cco::INT - a.cco::INT AS dcco FROM {tabla} d {unir}"
        ).df()
        df = df.merge(cco, on=["cliente", "t"], how="inner")
        y = (df["y_dprod_3"] - df["dcco"]).to_numpy(dtype=float)
        est = metodos.dml_att(df[cols], df["d"].to_numpy(), y)
        salida[f"otros_sin_cuenta_corriente_{nombre}"] = est.como_dict()
        print(nombre, round(est.efecto, 4), np.round(est.ic95, 4))
    con.close()
    escribir_json(salida, reports_hito(4) / "exploratorio.json")


if __name__ == "__main__":
    main()
