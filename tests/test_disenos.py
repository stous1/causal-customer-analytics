"""Diseños: definición de tratamiento, rezagos sin saltar huecos y ventanas válidas."""

import pandas as pd

from causal import base, disenos


def test_rezagos_respetan_huecos(tmp_path) -> None:
    c = base.conectar(":memory:", memoria="1GB", temporal=tmp_path / "tmp")
    filas = []
    for mes in (5, 6, 7, 9, 10):  # falta el mes 8
        fila = {p: 0 for p in disenos.PRODUCTOS}
        fila.update({"cliente": 1, "mes": mes, "activo": mes % 2, "nomina": int(mes >= 9)})
        filas.append(fila)
    panel = pd.DataFrame(filas)
    c.register("p", panel)
    c.execute("CREATE TABLE panel AS SELECT * FROM p")
    disenos.crear_rezagos(c)
    r = c.execute("SELECT mes, activo_m1, nomina_m1, activo_t FROM rezagos ORDER BY mes").df()
    fila9 = r[r.mes == 9].iloc[0]
    assert pd.isna(fila9.activo_m1)  # el mes 8 no existe: no se toma el 7
    assert r[r.mes == 7].iloc[0].activo_m1 == 0  # mes 6 -> activo 0
    # la actividad de los meses congelados (< 6) no se usa
    assert pd.isna(r[r.mes == 5].iloc[0].activo_t)


def test_tratamiento_nomina(con) -> None:
    df = con.execute(
        """SELECT d.d, r.nomina_t, r.nomina_m1, r.nomina_m2, r.nomina_m3, d.t, d.act_m3
           FROM d_nomina d JOIN rezagos r ON r.cliente = d.cliente AND r.mes = d.t"""
    ).df()
    assert len(df) > 0 and df.d.sum() > 0
    assert (df.nomina_m1 == 0).all() and (df.nomina_m2 == 0).all() and (df.nomina_m3 == 0).all()
    assert (df.d == df.nomina_t).all()
    assert df.t.between(9, 13).all()
    assert df.act_m3.notna().all()  # actividad real: t-3 >= 6


def test_placebo_es_previo_al_inicio(con) -> None:
    df = con.execute(
        """SELECT d.d, r.nomina_t, r.nomina_p3, r.nomina_p4
           FROM d_nomina_placebo d JOIN rezagos r ON r.cliente = d.cliente AND r.mes = d.t"""
    ).df()
    assert (df.nomina_t == 0).all() and (df.nomina_p3 == 0).all()
    assert (df.d == df.nomina_p4).all()


def test_productos_elegibles_activos(con) -> None:
    for p in disenos.PRODUCTOS_P3:
        df = con.execute(f"SELECT * FROM d_producto_{p}").df()
        assert (df.act_m1 == 1).all() and (df.act_m2 == 1).all()
        assert (df[f"x_{p}"] == 0).all()


def test_canal_covariables_sin_mediadores(con) -> None:
    df = disenos.leer(con, "d_canal")
    cols = disenos.columnas_x(df, "canal")
    assert not any(c.startswith(("x_", "canal_")) for c in cols)
    assert "relacion_activa" not in cols
    assert set(df.canal) <= {"KHM", "KHN", "KHQ"}


def test_columnas_x_sin_resultados(con) -> None:
    df = disenos.leer(con, "d_nomina")
    cols = disenos.columnas_x(df, "nomina")
    assert not any(c.startswith(("y_", "ev_")) for c in cols) and "d" not in cols
