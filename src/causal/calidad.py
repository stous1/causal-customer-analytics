"""Calidad del dato del panel: faltantes, inconsistencias demográficas y cambios en el tiempo.

Todas las funciones leen la tabla ``panel`` y devuelven estructuras serializables a JSON.
En este módulo **no se cruza ningún tratamiento con ningún resultado**: describir la
asociación entre nómina y actividad antes del preregistro sería mirar el efecto.
"""

import duckdb

from causal.ingesta import PRODUCTOS

DEMOGRAFIA = (
    "empleado",
    "pais",
    "sexo",
    "edad",
    "fecha_alta",
    "antiguedad",
    "tipo_cliente_mes",
    "relacion_mes",
    "canal",
    "cod_prov",
    "activo",
    "renta",
    "segmento",
)


def _filas(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    cur = con.execute(sql)
    nombres = [d[0] for d in cur.description]
    return [dict(zip(nombres, f, strict=True)) for f in cur.fetchall()]


def _uno(con: duckdb.DuckDBPyConnection, sql: str) -> dict:
    return _filas(con, sql)[0]


def faltantes_por_mes(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Fracción de faltantes de cada variable demográfica y de nómina, por mes."""
    cols = list(DEMOGRAFIA) + ["nomina", "nom_pens"]
    exprs = ", ".join(f"round(avg(({c} IS NULL)::INT), 5) AS {c}" for c in cols)
    return _filas(con, f"SELECT mes, count(*) AS filas, {exprs} FROM panel GROUP BY 1 ORDER BY 1")


def filas_vacias(con: duckdb.DuckDBPyConnection) -> dict:
    """Filas sin demografía (sin fecha de alta, sexo ni actividad)."""
    base = "fecha_alta IS NULL AND activo IS NULL AND edad IS NULL"
    resumen = _uno(
        con,
        f"""
        SELECT count(*) AS filas, count(DISTINCT cliente) AS clientes,
               max(mes) AS ultimo_mes,
               count(*) FILTER (WHERE {" + ".join(PRODUCTOS)} > 0) AS con_productos
        FROM panel WHERE {base}
        """,
    )
    resumen["por_mes"] = _filas(
        con, f"SELECT mes, count(*) AS filas FROM panel WHERE {base} GROUP BY 1 ORDER BY 1"
    )
    resumen["clientes_siempre_vacios"] = con.execute(
        f"""
        SELECT count(*) FROM (
            SELECT cliente FROM panel GROUP BY 1 HAVING bool_and({base})
        )"""
    ).fetchone()[0]
    return resumen


def inconsistencias(con: duckdb.DuckDBPyConnection) -> dict:
    """Contradicciones de un mismo cliente entre meses y valores imposibles."""
    por_cliente = _uno(
        con,
        """
        WITH c AS (
            SELECT cliente,
                   count(DISTINCT sexo) AS sexos,
                   count(DISTINCT fecha_alta) AS altas,
                   count(DISTINCT canal) AS canales,
                   count(DISTINCT segmento) AS segmentos,
                   count(DISTINCT round(renta, 2)) AS rentas,
                   count(DISTINCT cod_prov) AS provincias,
                   max(edad) - min(edad) AS rango_edad,
                   max(mes) - min(mes) AS rango_mes
            FROM panel GROUP BY 1
        )
        SELECT count(*) AS clientes,
               count(*) FILTER (WHERE sexos > 1) AS cambia_sexo,
               count(*) FILTER (WHERE altas > 1) AS cambia_fecha_alta,
               count(*) FILTER (WHERE canales > 1) AS cambia_canal,
               count(*) FILTER (WHERE segmentos > 1) AS cambia_segmento,
               count(*) FILTER (WHERE rentas > 1) AS cambia_renta,
               count(*) FILTER (WHERE provincias > 1) AS cambia_provincia,
               count(*) FILTER (WHERE rango_edad > rango_mes / 12 + 1) AS edad_salta_imposible
        FROM c
        """,
    )
    consecutivas = _uno(
        con,
        """
        WITH l AS (
            SELECT cliente, mes, edad, antiguedad, activo,
                   lag(edad) OVER w AS edad_ant, lag(antiguedad) OVER w AS antig_ant,
                   lag(mes) OVER w AS mes_ant
            FROM panel WINDOW w AS (PARTITION BY cliente ORDER BY mes)
        )
        SELECT count(*) FILTER (WHERE edad < edad_ant) AS edad_disminuye,
               count(*) FILTER (WHERE antiguedad < antig_ant) AS antiguedad_disminuye,
               count(*) FILTER (WHERE mes - mes_ant > 1) AS huecos
        FROM l
        """,
    )
    valores = _uno(
        con,
        """
        SELECT count(*) FILTER (WHERE edad < 18) AS menores_de_18,
               count(*) FILTER (WHERE edad < 18 AND nomina = 1) AS menores_con_nomina,
               count(*) FILTER (WHERE edad > 100) AS mayores_de_100,
               count(*) FILTER (WHERE fecha_alta > fecha) AS alta_posterior_al_mes,
               count(*) FILTER (WHERE fecha_alta < DATE '1995-01-01') AS alta_antes_de_1995,
               count(*) FILTER (WHERE abs(antiguedad - date_diff('month', fecha_alta, fecha)) > 1)
                   AS antiguedad_no_cuadra_con_alta,
               count(*) FILTER (WHERE fallecido = 'S' AND activo = 1) AS fallecido_activo,
               count(*) FILTER (WHERE fallecido = 'S') AS fallecido,
               count(*) FILTER (WHERE segmento = '03 - UNIVERSITARIO' AND edad > 60)
                   AS universitario_mayor_de_60,
               count(*) FILTER (WHERE nomina = 1 AND nom_pens = 0) AS nomina_sin_nom_pens,
               count(*) FILTER (WHERE nomina = 0 AND nom_pens = 1) AS nom_pens_sin_nomina,
               count(*) FILTER (WHERE relacion_mes = 'A' AND activo = 0) AS relacion_a_inactivo,
               count(*) FILTER (WHERE renta IS NOT NULL AND renta < 1000) AS renta_menor_1000,
               count(*) AS filas
        FROM panel
        """,
    )
    return {"por_cliente": por_cliente, "meses_consecutivos": consecutivas, "valores": valores}


def evolucion(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Por mes: clientes, entradas y salidas del panel, actividad y tenencia media."""
    suma = " + ".join(f"coalesce({p}, 0)" for p in PRODUCTOS)
    return _filas(
        con,
        f"""
        WITH p AS (
            SELECT *, min(mes) OVER (PARTITION BY cliente) AS primero,
                      max(mes) OVER (PARTITION BY cliente) AS ultimo
            FROM panel
        )
        SELECT mes, min(fecha) AS fecha, count(*) AS clientes,
               count(*) FILTER (WHERE mes = primero) AS entran,
               count(*) FILTER (WHERE mes = ultimo) AS ultimo_mes_en_panel,
               count(*) FILTER (WHERE date_trunc('month', fecha_alta) = date_trunc('month', fecha))
                   AS alta_este_mes,
               round(avg(activo), 4) AS tasa_actividad,
               round(avg({suma}), 4) AS productos_medios,
               round(avg(nomina), 4) AS tasa_nomina,
               round(avg((renta IS NULL)::INT), 4) AS renta_faltante,
               round(avg((segmento = '03 - UNIVERSITARIO')::INT), 4) AS frac_universitario,
               round(avg((edad < 25)::INT), 4) AS frac_menor_25
        FROM p GROUP BY 1 ORDER BY 1
        """,
    )


def tenencia_por_mes(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Fracción de clientes con cada producto, por mes."""
    exprs = ", ".join(f"round(avg({p}), 5) AS {p}" for p in PRODUCTOS)
    return _filas(con, f"SELECT mes, {exprs} FROM panel GROUP BY 1 ORDER BY 1")


def altas_productos_por_mes(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Altas (0 -> 1 entre meses consecutivos) y bajas de cada producto, por mes."""
    lags = ", ".join(f"lag({p}) OVER w AS {p}_ant" for p in PRODUCTOS)
    altas = ", ".join(f"count(*) FILTER (WHERE {p} = 1 AND {p}_ant = 0) AS {p}" for p in PRODUCTOS)
    return _filas(
        con,
        f"""
        WITH l AS (
            SELECT mes, {", ".join(PRODUCTOS)}, lag(mes) OVER w AS mes_ant, {lags}
            FROM panel WINDOW w AS (PARTITION BY cliente ORDER BY mes)
        )
        SELECT mes, count(*) AS clientes_con_mes_anterior, {altas}
        FROM l WHERE mes_ant = mes - 1 GROUP BY 1 ORDER BY 1
        """,
    )


def transiciones_actividad(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Paso de activo a inactivo y de inactivo a activo entre meses consecutivos."""
    return _filas(
        con,
        """
        WITH l AS (
            SELECT mes, activo, lag(activo) OVER w AS ant, lag(mes) OVER w AS mes_ant
            FROM panel WINDOW w AS (PARTITION BY cliente ORDER BY mes)
        )
        SELECT mes,
               count(*) FILTER (WHERE ant = 1) AS activos_mes_anterior,
               round(avg((activo = 0)::INT) FILTER (WHERE ant = 1), 5) AS tasa_activo_a_inactivo,
               round(avg((activo = 1)::INT) FILTER (WHERE ant = 0), 5) AS tasa_inactivo_a_activo
        FROM l WHERE mes_ant = mes - 1 GROUP BY 1 ORDER BY 1
        """,
    )


def canales(con: duckdb.DuckDBPyConnection, top: int = 12) -> dict:
    """Canales de vinculación: todos los clientes y los que se dan de alta durante el panel."""
    total = _filas(
        con,
        f"""
        SELECT canal, count(*) AS clientes FROM (
            SELECT cliente, arg_max(canal, mes) AS canal FROM panel GROUP BY 1
        ) GROUP BY 1 ORDER BY 2 DESC LIMIT {top}
        """,
    )
    nuevos = _filas(
        con,
        f"""
        SELECT canal, count(*) AS clientes, round(avg(edad), 1) AS edad_media,
               round(avg((segmento = '03 - UNIVERSITARIO')::INT), 3) AS frac_universitario
        FROM (
            SELECT cliente, arg_min(canal, mes) AS canal, arg_min(edad, mes) AS edad,
                   arg_min(segmento, mes) AS segmento, min(fecha_alta) AS alta, min(fecha) AS f0
            FROM panel GROUP BY 1
        ) WHERE alta >= DATE '2015-02-01' GROUP BY 1 ORDER BY 2 DESC LIMIT {top}
        """,
    )
    return {"todos": total, "altas_en_el_panel": nuevos}


def inicios_nomina(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Clientes que empiezan a recibir la nómina cada mes (sin nómina los 3 meses anteriores).

    Solo cuenta tratados; no mira ningún resultado.
    """
    return _filas(
        con,
        """
        WITH l AS (
            SELECT cliente, mes, nomina,
                   lag(nomina, 1) OVER w AS n1, lag(nomina, 2) OVER w AS n2,
                   lag(nomina, 3) OVER w AS n3, lag(mes, 3) OVER w AS m3
            FROM panel WINDOW w AS (PARTITION BY cliente ORDER BY mes)
        )
        SELECT mes,
               count(*) FILTER (WHERE m3 = mes - 3 AND n1 = 0 AND n2 = 0 AND n3 = 0) AS elegibles,
               count(*) FILTER (WHERE m3 = mes - 3 AND n1 = 0 AND n2 = 0 AND n3 = 0
                                AND nomina = 1) AS inician
        FROM l GROUP BY 1 HAVING elegibles > 0 ORDER BY 1
        """,
    )


def cambios_mes_a_mes(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Fracción de clientes cuyo valor cambia respecto del mes anterior, por variable y mes.

    Muestra el congelamiento de enero a julio de 2015: la demografía y la actividad no
    cambian para nadie, mientras los productos sí.
    """
    variables = (
        "activo",
        "antiguedad",
        "edad",
        "segmento",
        "relacion_mes",
        "nomina",
        "tjcr",
        "recibo",
        "cco",
    )
    lags = ", ".join(f"lag({v}) OVER w AS {v}_ant" for v in variables)
    exprs = ", ".join(
        f"round(avg(({v} IS DISTINCT FROM {v}_ant)::INT), 5) AS {v}" for v in variables
    )
    return _filas(
        con,
        f"""
        WITH l AS (
            SELECT mes, {", ".join(variables)}, lag(mes) OVER w AS mes_ant, {lags}
            FROM panel WINDOW w AS (PARTITION BY cliente ORDER BY mes)
        )
        SELECT mes, count(*) AS clientes, {exprs}
        FROM l WHERE mes_ant = mes - 1 GROUP BY 1 ORDER BY 1
        """,
    )


def registro_tardio(con: duckdb.DuckDBPyConnection) -> dict:
    """Variables que faltan en el mes de alta de los clientes nuevos y aparecen al mes siguiente."""
    cols = ("canal", "segmento", "relacion_mes", "renta", "cod_prov", "sexo", "edad")
    alta = ", ".join(f"round(avg((x.{c} IS NULL)::INT), 4) AS {c}_alta" for c in cols)
    sig = ", ".join(f"round(avg((y.{c} IS NULL)::INT), 4) AS {c}_siguiente" for c in cols)
    return _uno(
        con,
        f"""
        WITH primeros AS (SELECT cliente, min(mes) AS m0 FROM panel GROUP BY 1)
        SELECT count(*) AS clientes_nuevos, {alta}, {sig}
        FROM primeros pr
        JOIN panel x ON x.cliente = pr.cliente AND x.mes = pr.m0
        JOIN panel y ON y.cliente = pr.cliente AND y.mes = pr.m0 + 1
        WHERE pr.m0 >= 6
          AND (year(x.fecha_alta) - 2015) * 12 + month(x.fecha_alta) - 1 = pr.m0
        """,
    )


def resumen_completo(con: duckdb.DuckDBPyConnection) -> dict:
    """Todo el diagnóstico del hito 1 en un solo diccionario."""
    return {
        "faltantes_por_mes": faltantes_por_mes(con),
        "filas_vacias": filas_vacias(con),
        "inconsistencias": inconsistencias(con),
        "evolucion": evolucion(con),
        "tenencia_por_mes": tenencia_por_mes(con),
        "altas_productos_por_mes": altas_productos_por_mes(con),
        "transiciones_actividad": transiciones_actividad(con),
        "canales": canales(con),
        "inicios_nomina": inicios_nomina(con),
        "cambios_mes_a_mes": cambios_mes_a_mes(con),
        "registro_tardio": registro_tardio(con),
    }
