"""Ingesta del panel de Santander Product Recommendation en DuckDB.

El CSV tiene trampas que se resuelven aquí y en ningún otro lugar:

- Todo se lee como texto (``all_varchar``): varias columnas mezclan tipos (``indrel_1mes``
  trae ``1``, ``1.0`` y ``P``; ``age`` y ``antiguedad`` traen espacios a la izquierda y
  ``NA``; ``antiguedad`` usa ``-999999`` como faltante).
- La codificación es UTF-8 (``CORUÑA, A`` viene como ``C3 91``); se verifica que no haya
  caracteres de reemplazo.
- Los productos se renombran a nombres cortos (``ind_tjcr_fin_ult1`` -> ``tjcr``).
"""

from pathlib import Path

import duckdb

# Código corto, columna original y nombre en español de los 24 productos.
PRODUCTOS: dict[str, tuple[str, str]] = {
    "ahor": ("ind_ahor_fin_ult1", "Cuenta de ahorros"),
    "aval": ("ind_aval_fin_ult1", "Avales"),
    "cco": ("ind_cco_fin_ult1", "Cuenta corriente"),
    "cder": ("ind_cder_fin_ult1", "Cuenta derivados"),
    "cno": ("ind_cno_fin_ult1", "Cuenta nómina"),
    "ctju": ("ind_ctju_fin_ult1", "Cuenta joven"),
    "ctma": ("ind_ctma_fin_ult1", "Cuenta más particulares"),
    "ctop": ("ind_ctop_fin_ult1", "Cuenta particulares"),
    "ctpp": ("ind_ctpp_fin_ult1", "Cuenta particulares plus"),
    "deco": ("ind_deco_fin_ult1", "Depósito a corto plazo"),
    "deme": ("ind_deme_fin_ult1", "Depósito a mediano plazo"),
    "dela": ("ind_dela_fin_ult1", "Depósito a largo plazo"),
    "ecue": ("ind_ecue_fin_ult1", "Cuenta electrónica"),
    "fond": ("ind_fond_fin_ult1", "Fondos"),
    "hip": ("ind_hip_fin_ult1", "Hipoteca"),
    "plan": ("ind_plan_fin_ult1", "Plan de pensiones"),
    "pres": ("ind_pres_fin_ult1", "Préstamo"),
    "reca": ("ind_reca_fin_ult1", "Impuestos"),
    "tjcr": ("ind_tjcr_fin_ult1", "Tarjeta de crédito"),
    "valo": ("ind_valo_fin_ult1", "Valores"),
    "viv": ("ind_viv_fin_ult1", "Cuenta hogar"),
    "nomina": ("ind_nomina_ult1", "Nómina"),
    "nom_pens": ("ind_nom_pens_ult1", "Pensiones (nómina)"),
    "recibo": ("ind_recibo_ult1", "Débito automático"),
}

COLUMNAS_CSV: tuple[str, ...] = (
    "fecha_dato",
    "ncodpers",
    "ind_empleado",
    "pais_residencia",
    "sexo",
    "age",
    "fecha_alta",
    "ind_nuevo",
    "antiguedad",
    "indrel",
    "ult_fec_cli_1t",
    "indrel_1mes",
    "tiprel_1mes",
    "indresi",
    "indext",
    "conyuemp",
    "canal_entrada",
    "indfall",
    "tipodom",
    "cod_prov",
    "nomprov",
    "ind_actividad_cliente",
    "renta",
    "segmento",
) + tuple(c for c, _ in PRODUCTOS.values())

FALTANTES_TEXTO = ("", "NA", "nan", "NaN")


def _txt(c: str) -> str:
    """Texto recortado, con los marcadores de faltante convertidos en NULL."""
    lista = ", ".join(f"'{x}'" for x in FALTANTES_TEXTO)
    return f"CASE WHEN trim({c}) IN ({lista}) THEN NULL ELSE trim({c}) END"


def _entero(c: str) -> str:
    return f"TRY_CAST({_txt(c)} AS INTEGER)"


def _sql_tipado(origen: str) -> str:
    productos = ",\n    ".join(
        f"TRY_CAST({_txt(col)} AS UTINYINT) AS {corto}" for corto, (col, _) in PRODUCTOS.items()
    )
    return f"""
SELECT
    CAST({_txt("fecha_dato")} AS DATE) AS fecha,
    -- índice del mes: 0 = enero de 2015, 16 = mayo de 2016
    CAST((year(CAST({_txt("fecha_dato")} AS DATE)) - 2015) * 12
         + month(CAST({_txt("fecha_dato")} AS DATE)) - 1 AS SMALLINT) AS mes,
    {_entero("ncodpers")} AS cliente,
    {_txt("ind_empleado")} AS empleado,
    {_txt("pais_residencia")} AS pais,
    {_txt("sexo")} AS sexo,
    {_entero("age")} AS edad,
    TRY_CAST({_txt("fecha_alta")} AS DATE) AS fecha_alta,
    {_entero("ind_nuevo")} AS nuevo,
    CASE WHEN {_entero("antiguedad")} < 0 THEN NULL ELSE {_entero("antiguedad")} END
        AS antiguedad,
    {_entero("indrel")} AS indrel,
    TRY_CAST({_txt("ult_fec_cli_1t")} AS DATE) AS ult_fec_primario,
    -- '1' y '1.0' son el mismo valor; 'P' (potencial) se conserva
    CASE WHEN {_txt("indrel_1mes")} = 'P' THEN 'P'
         ELSE CAST(TRY_CAST({_txt("indrel_1mes")} AS DOUBLE) AS INTEGER)::VARCHAR
    END AS tipo_cliente_mes,
    {_txt("tiprel_1mes")} AS relacion_mes,
    {_txt("indresi")} AS residente,
    {_txt("indext")} AS extranjero,
    {_txt("conyuemp")} AS conyuge_empleado,
    {_txt("canal_entrada")} AS canal,
    {_txt("indfall")} AS fallecido,
    {_entero("tipodom")} AS tipodom,
    {_entero("cod_prov")} AS cod_prov,
    {_txt("nomprov")} AS provincia,
    {_entero("ind_actividad_cliente")} AS activo,
    TRY_CAST({_txt("renta")} AS DOUBLE) AS renta,
    {_txt("segmento")} AS segmento,
    {productos}
FROM {origen}
"""


def leer_crudo(con: duckdb.DuckDBPyConnection, csv: Path, tabla: str = "crudo") -> int:
    """Carga el CSV completo como texto, con nombres de columna explícitos."""
    columnas = ", ".join(f"'{c}': 'VARCHAR'" for c in COLUMNAS_CSV)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {tabla} AS
        SELECT * FROM read_csv('{csv.as_posix()}', header = true, columns = {{{columnas}}},
                               encoding = 'utf-8', quote = '"')
        """
    )
    return con.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0]


def cargar_panel(con: duckdb.DuckDBPyConnection, csv: Path) -> dict:
    """CSV -> tabla ``crudo`` (texto) y tabla ``panel`` (tipada, una fila por cliente y mes).

    Devuelve un resumen de la carga: filas, duplicados y caracteres de reemplazo.
    """
    filas = leer_crudo(con, csv)
    con.execute(f"CREATE OR REPLACE TABLE panel AS {_sql_tipado('crudo')} ORDER BY fecha, cliente")
    duplicados = con.execute(
        "SELECT count(*) FROM (SELECT cliente, fecha FROM panel GROUP BY ALL HAVING count(*) > 1)"
    ).fetchone()[0]
    reemplazo = con.execute(
        "SELECT count(*) FROM panel WHERE provincia LIKE '%' || chr(65533) || '%'"
    ).fetchone()[0]
    crudo = calidad_crudo(con)
    con.execute("DROP TABLE crudo")
    meses = con.execute("SELECT count(DISTINCT fecha) FROM panel").fetchone()[0]
    clientes = con.execute("SELECT count(DISTINCT cliente) FROM panel").fetchone()[0]
    return {
        "filas": filas,
        "meses": meses,
        "clientes": clientes,
        "duplicados_cliente_mes": duplicados,
        "caracteres_reemplazo": reemplazo,
        "crudo": crudo,
    }


def calidad_crudo(con: duckdb.DuckDBPyConnection, tabla: str = "crudo") -> dict:
    """Problemas de formato del CSV antes de tipar: marcadores de faltante, mezcla de tipos."""
    na = {}
    for c in COLUMNAS_CSV:
        n = con.execute(
            f"SELECT count(*) FILTER (WHERE {c} IS NULL OR trim({c}) IN "
            f"({', '.join(repr(x) for x in FALTANTES_TEXTO)})) FROM {tabla}"
        ).fetchone()[0]
        if n:
            na[c] = n
    formas = con.execute(
        f"SELECT indrel_1mes, count(*) FROM {tabla} GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    especiales = con.execute(
        f"""SELECT
            count(*) FILTER (WHERE trim(antiguedad) = '-999999'),
            count(*) FILTER (WHERE age <> trim(age)),
            count(*) FILTER (WHERE TRY_CAST(trim(renta) AS DOUBLE) IS NULL AND renta IS NOT NULL
                             AND trim(renta) <> 'NA')
        FROM {tabla}"""
    ).fetchone()
    return {
        "faltantes_por_columna": na,
        "formas_indrel_1mes": {str(k): v for k, v in formas},
        "antiguedad_menos_999999": especiales[0],
        "edad_con_espacios": especiales[1],
        "renta_no_numerica": especiales[2],
    }
