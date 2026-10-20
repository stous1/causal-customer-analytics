"""Calidad del dato: el diagnóstico corre y detecta el congelamiento."""

import pandas as pd

from causal import base, calidad


def test_resumen_completo(con) -> None:
    res = calidad.resumen_completo(con)
    for clave in (
        "faltantes_por_mes",
        "inconsistencias",
        "evolucion",
        "cambios_mes_a_mes",
        "registro_tardio",
        "inicios_nomina",
    ):
        assert clave in res
    assert res["filas_vacias"]["filas"] > 0


def test_detecta_congelamiento(tmp_path) -> None:
    c = base.conectar(":memory:", memoria="1GB", temporal=tmp_path / "tmp")
    filas = []
    for cliente in range(20):
        for mes in range(10):
            congelado = mes < 6
            filas.append(
                {
                    "cliente": cliente,
                    "mes": mes,
                    "activo": 1 if congelado else (cliente + mes) % 2,
                    "antiguedad": 10 if congelado else 10 + mes,
                    "edad": 30,
                    "segmento": "02",
                    "relacion_mes": "A",
                    "nomina": (cliente + mes) % 3 == 0,
                    "tjcr": 0,
                    "recibo": mes % 2,
                    "cco": 1,
                }
            )
    c.register("p", pd.DataFrame(filas))
    c.execute("CREATE TABLE panel AS SELECT * FROM p")
    cambios = pd.DataFrame(calidad.cambios_mes_a_mes(c)).set_index("mes")
    assert (cambios.loc[1:5, "activo"] == 0).all()
    assert (cambios.loc[7:, "activo"] > 0).all()
    assert (cambios.loc[1:5, "recibo"] > 0).all()
