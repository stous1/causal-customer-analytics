"""Fixtures compartidas: un mini-Santander sintético cargado en una base DuckDB temporal."""

from pathlib import Path

import duckdb
import pytest

from causal import base, disenos, ingesta, sintetico


@pytest.fixture(scope="session")
def mini_csv(tmp_path_factory: pytest.TempPathFactory) -> sintetico.MiniSantander:
    return sintetico.generar(tmp_path_factory.mktemp("raw") / "mini.csv", clientes=600, semilla=11)


@pytest.fixture(scope="session")
def ruta_base(tmp_path_factory: pytest.TempPathFactory, mini_csv: sintetico.MiniSantander) -> Path:
    """Base con ``panel``, ``rezagos`` y las tablas de diseño del mini-Santander."""
    directorio = tmp_path_factory.mktemp("base")
    ruta = directorio / "mini.duckdb"
    con = base.conectar(ruta, memoria="2GB", temporal=directorio / "tmp")
    ingesta.cargar_panel(con, mini_csv.ruta)
    disenos.crear_todos(con)
    con.close()
    return ruta


@pytest.fixture
def con(ruta_base: Path) -> duckdb.DuckDBPyConnection:
    conexion = base.conectar(
        ruta_base, solo_lectura=True, memoria="2GB", temporal=ruta_base.parent / "tmp"
    )
    yield conexion
    conexion.close()
