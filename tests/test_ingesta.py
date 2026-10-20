"""Ingesta: tipos, marcadores de faltante y codificación."""

from causal import base, ingesta, sintetico


def test_carga_tipada(con) -> None:
    tipos = dict(con.execute("SELECT column_name, column_type FROM (DESCRIBE panel)").fetchall())
    assert tipos["fecha"] == "DATE"
    assert tipos["cliente"] == "INTEGER"
    assert tipos["edad"] == "INTEGER"
    assert tipos["renta"] == "DOUBLE"
    assert all(tipos[p] == "UTINYINT" for p in ingesta.PRODUCTOS)
    assert con.execute("SELECT min(mes), max(mes) FROM panel").fetchone() == (0, 16)


def test_formatos_mezclados(con) -> None:
    formas = {r[0] for r in con.execute("SELECT DISTINCT tipo_cliente_mes FROM panel").fetchall()}
    assert "1.0" not in formas and "1" in formas
    assert con.execute("SELECT count(*) FROM panel WHERE antiguedad < 0").fetchone()[0] == 0
    # las filas vacías del generador quedan con NULL, no con texto 'NA'
    assert con.execute("SELECT count(*) FROM panel WHERE edad IS NULL").fetchone()[0] > 0


def test_codificacion_utf8(con) -> None:
    provincias = {r[0] for r in con.execute("SELECT DISTINCT provincia FROM panel").fetchall()}
    assert "CORUÑA, A" in provincias


def test_resumen_de_carga(tmp_path) -> None:
    mini = sintetico.generar(tmp_path / "m.csv", clientes=50, semilla=3)
    c = base.conectar(":memory:", memoria="1GB", temporal=tmp_path / "tmp")
    r = ingesta.cargar_panel(c, mini.ruta)
    assert r["filas"] == mini.filas
    assert r["duplicados_cliente_mes"] == 0
    assert r["caracteres_reemplazo"] == 0
    assert r["crudo"]["formas_indrel_1mes"].get("1.0", 0) > 0
    assert (
        c.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = 'crudo'").fetchone()[0]
        == 0
    )
