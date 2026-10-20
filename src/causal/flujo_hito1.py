"""Hito 1: ingesta, calidad del dato, exploración y diseños (sin mirar ningún efecto)."""

from pathlib import Path

import duckdb
import pandas as pd

from causal import calidad, disenos, graficos, ingesta
from causal.ingesta import PRODUCTOS
from causal.util import escribir_json

FECHAS = pd.date_range("2015-01-01", periods=17, freq="MS")


def preparar(con: duckdb.DuckDBPyConnection, csv: Path) -> dict:
    """CSV -> ``panel``, ``rezagos`` y las tablas de diseño."""
    carga = ingesta.cargar_panel(con, csv)
    disenos.crear_todos(con)
    con.execute("CHECKPOINT")
    return carga


def _con_fecha(filas: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(filas)
    df["fecha"] = [FECHAS[m] for m in df["mes"]]
    return df


def graficos_hito1(res: dict, salida: Path) -> None:
    """Gráficos de evolución, congelamiento, faltantes y tratamientos."""
    cambios = _con_fecha(res["cambios_mes_a_mes"])
    nombres = {
        "activo": "Actividad",
        "edad": "Edad",
        "segmento": "Segmento",
        "nomina": "Nómina",
        "tjcr": "Tarjeta de crédito",
        "recibo": "Débito automático",
    }
    largo = cambios.melt(["mes", "fecha"], list(nombres), "variable", "frac")
    largo["variable"] = largo["variable"].map(nombres)
    largo["mes"] = largo["mes"].astype(float)
    g = graficos.lineas(
        largo,
        "mes",
        "frac",
        color="variable",
        titulo="Clientes cuyo valor cambia respecto del mes anterior (sombreado: nadie cambia)",
        eje_x="Mes del panel (1 = febrero de 2015, 6 = julio de 2015, 16 = mayo de 2016)",
        eje_y="Fracción de clientes",
        formato_y="%",
        sombra=(0.5, 6.5),
    )
    graficos.guardar(g, salida / "congelamiento")

    evo = _con_fecha(res["evolucion"])
    evo["mes"] = evo["mes"].astype(float)
    a = graficos.lineas(
        evo,
        "mes",
        "clientes",
        titulo="Clientes en el panel",
        eje_x="Mes",
        eje_y="Clientes",
        alto=200,
        sombra=(-0.5, 5.5),
    )
    b = graficos.lineas(
        evo,
        "mes",
        "tasa_actividad",
        titulo="Tasa de actividad (meses 0 a 5: copia de julio)",
        eje_x="Mes",
        eje_y="Activos",
        formato_y="%",
        alto=200,
        sombra=(-0.5, 5.5),
    )
    graficos.guardar((a & b), salida / "evolucion")

    falt = _con_fecha(res["faltantes_por_mes"])
    falt["mes"] = falt["mes"].astype(float)
    nombres_f = {"renta": "Renta", "canal": "Canal", "segmento": "Segmento", "edad": "Edad"}
    lf = falt.melt(["mes", "fecha"], list(nombres_f), "variable", "frac")
    lf["variable"] = lf["variable"].map(nombres_f)
    g = graficos.lineas(
        lf,
        "mes",
        "frac",
        color="variable",
        titulo="Faltantes por mes",
        eje_x="Mes",
        eje_y="Fracción de filas",
        formato_y="%",
    )
    graficos.guardar(g, salida / "faltantes")

    ten = pd.DataFrame(res["tenencia_por_mes"])
    ultimo = ten.iloc[-1].drop("mes")
    df_t = pd.DataFrame(
        {"producto": [PRODUCTOS[p][1] for p in ultimo.index], "frac": ultimo.to_numpy()}
    )
    g = graficos.barras_h(
        df_t,
        "frac",
        "producto",
        titulo="Tenencia por producto, mayo de 2016",
        eje_x="Clientes con el producto",
        formato_x="%",
    )
    graficos.guardar(g, salida / "tenencia")


def explorar(con: duckdb.DuckDBPyConnection, carga: dict | None, salida: Path) -> dict:
    """Calidad, exploración y conteos de los diseños -> ``exploracion.json`` y gráficos."""
    res = calidad.resumen_completo(con)
    res["conteos_disenos"] = disenos.conteos(con)
    res["disenos"] = {
        "nomina": disenos.DISENO_NOMINA.como_dict(),
        "canal": disenos.DISENO_CANAL.como_dict(),
        **{f"producto_{p}": disenos.diseno_producto(p).como_dict() for p in disenos.PRODUCTOS_P3},
    }
    if carga is not None:
        res["carga"] = carga
    escribir_json(res, salida / "exploracion.json")
    graficos_hito1(res, salida)
    return res
