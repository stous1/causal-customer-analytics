"""Tablas de análisis de las tres preguntas causales: tratamiento, resultados y covariables.

Cada pregunta se arma como una **emulación de ensayo objetivo** mes a mes: en cada mes ``t``
de una ventana, los clientes que cumplen la elegibilidad se dividen entre quienes inician
el tratamiento en ``t`` y quienes no lo inician en ``t`` (aunque lo inicien después: es un
efecto de intención de tratar, ITT). Las covariables se miden en ``t - 1`` o antes y los
resultados en ``t + h``.

**Ventanas válidas.** En enero-junio de 2015 (meses 0 a 5) la demografía, la antigüedad y
la actividad del cliente son una copia de julio (mes 6): no cambian para ningún cliente
(ver ``calidad.py`` e hito 1). Los productos sí cambian mes a mes desde enero. Por eso toda
variable que no sea un producto se toma de los meses 6 a 16.

Los controles se muestrean de forma determinista (``_uniforme``) para que las tablas quepan;
con controles muestreados al azar el efecto en los tratados (ATT) no cambia.
"""

from dataclasses import asdict, dataclass, field

import duckdb
import pandas as pd

from causal.ingesta import PRODUCTOS

# Productos que no cuentan en la tenencia "otros productos": la nómina, su indicador de
# pensiones (siempre acompaña a la nómina) y la cuenta nómina (se abre con ella).
LIGADOS_A_NOMINA = ("nomina", "nom_pens", "cno")
OTROS = tuple(p for p in PRODUCTOS if p not in LIGADOS_A_NOMINA)
PRIMER_MES_DEMOGRAFIA = 6  # julio de 2015
ULTIMO_MES = 16  # mayo de 2016
DESFASES = tuple(range(-6, 5))  # t-6 ... t+4
VARIABLES_REZAGO = ("presente", "activo", "nomina", "n_otros", "n_prod", "recibo", "tjcr", "ecue")
PRODUCTOS_P3 = ("recibo", "tjcr", "ecue")
CANALES_TOP = ("KHE", "KAT", "KFC", "KHQ", "KHM", "KHN", "KHK", "KFA")
PROVINCIAS_TOP = (28, 8, 46, 41, 15, 30, 29, 50, 3, 11)


def _sufijo(k: int) -> str:
    return "t" if k == 0 else (f"m{-k}" if k < 0 else f"p{k}")


def crear_rezagos(con: duckdb.DuckDBPyConnection) -> None:
    """Tabla ``rezagos``: por cliente y mes, cada variable en t-6 ... t+4 (NULL si falta el mes).

    Usa marcos ``RANGE`` sobre el índice del mes, así un hueco en el panel da NULL y no el
    valor de otro mes.
    """
    suma_otros = " + ".join(f"coalesce({p}, 0)" for p in OTROS)
    suma_prod = " + ".join(f"coalesce({p}, 0)" for p in PRODUCTOS)
    cols = []
    for v in VARIABLES_REZAGO:
        for k in DESFASES:
            if k == 0:
                cols.append(f"{v} AS {v}_t")
                continue
            lado = "PRECEDING" if k < 0 else "FOLLOWING"
            cols.append(
                f"first({v}) OVER (PARTITION BY cliente ORDER BY mes "
                f"RANGE BETWEEN {abs(k)} {lado} AND {abs(k)} {lado}) AS {v}_{_sufijo(k)}"
            )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE rezagos AS
        WITH b AS (
            SELECT cliente, mes, 1 AS presente,
                   -- la actividad de los meses congelados no se usa
                   CASE WHEN mes >= {PRIMER_MES_DEMOGRAFIA} THEN activo END::INTEGER AS activo,
                   nomina::INTEGER AS nomina, recibo::INTEGER AS recibo,
                   tjcr::INTEGER AS tjcr, ecue::INTEGER AS ecue,
                   ({suma_otros})::INTEGER AS n_otros, ({suma_prod})::INTEGER AS n_prod
            FROM panel
        )
        SELECT cliente, mes, {", ".join(cols)} FROM b
        """
    )


def _uniforme(semilla: int, alias: str = "r") -> str:
    """Número en [0, 1) determinista por cliente, mes y semilla (no depende del orden)."""
    return f"(hash({alias}.cliente, {alias}.mes, {semilla}) % 1000000) / 1000000.0"


def _covariables_sql(alias: str = "x") -> str:
    """Covariables demográficas y de tenencia de la fila ``alias`` (un mes del panel)."""
    canales = ", ".join(
        f"({alias}.canal = '{c}')::UTINYINT AS canal_{c.lower()}" for c in CANALES_TOP
    )
    provincias = ", ".join(
        f"({alias}.cod_prov = {p})::UTINYINT AS prov_{p}" for p in PROVINCIAS_TOP
    )
    productos = ", ".join(f"coalesce({alias}.{p}, 0)::UTINYINT AS x_{p}" for p in PRODUCTOS)
    return f"""
        {alias}.edad::DOUBLE AS edad,
        ({alias}.sexo = 'H')::UTINYINT AS mujer,
        ln(coalesce({alias}.renta, 1.0))::DOUBLE AS log_renta,
        ({alias}.renta IS NULL)::UTINYINT AS renta_faltante,
        coalesce({alias}.antiguedad, 0)::DOUBLE AS antiguedad,
        ({alias}.segmento = '01 - TOP')::UTINYINT AS seg_top,
        ({alias}.segmento = '03 - UNIVERSITARIO')::UTINYINT AS seg_universitario,
        ({alias}.extranjero = 'S')::UTINYINT AS extranjero,
        ({alias}.residente = 'S')::UTINYINT AS residente,
        ({alias}.empleado <> 'N')::UTINYINT AS empleado_banco,
        ({alias}.relacion_mes = 'A')::UTINYINT AS relacion_activa,
        ({alias}.nuevo = 1)::UTINYINT AS nuevo,
        {canales},
        ({alias}.canal IS NULL)::UTINYINT AS canal_faltante,
        {provincias},
        {productos}
    """


@dataclass
class Diseno:
    """Descripción de un diseño: se copia tal cual al preregistro."""

    nombre: str
    pregunta: str
    tratamiento: str
    control: str
    elegibilidad: list[str]
    resultados: dict[str, str]
    meses_t: list[int]
    covariables: str
    razon_controles: int
    placebo: str = ""
    notas: list[str] = field(default_factory=list)

    def como_dict(self) -> dict:
        return asdict(self)


DISENO_NOMINA = Diseno(
    nombre="nomina",
    pregunta=(
        "¿Empezar a recibir la nómina en el banco vuelve más activo al cliente y aumenta su "
        "tenencia de otros productos, o los más activos son los que la traen?"
    ),
    tratamiento="Inicia la nómina en t: nomina_t = 1 con nomina = 0 en t-1, t-2 y t-3.",
    control="No inicia la nómina en t (nomina_t = 0); puede iniciarla después (ITT).",
    elegibilidad=[
        "Presente en el panel en t-3 ... t+3",
        "Sin nómina en t-1, t-2 y t-3",
        "Edad >= 18 en t-1, no fallecido, actividad conocida en t-1",
    ],
    resultados={
        "y_activo_3": "Activo en t+3 (ind_actividad_cliente)",
        "y_dprod_3": "Cambio en otros productos entre t-1 y t+3 (sin nómina, pensiones ni "
        "cuenta nómina)",
        "y_activo_1": "Activo en t+1 (secundario)",
    },
    meses_t=list(range(9, 14)),
    covariables="Demografía y los 24 productos en t-1; actividad en t-1, t-2 y t-3; otros "
    "productos en t-1, t-3 y t-6; mes t.",
    razon_controles=20,
    placebo="Adelanto: entre elegibles sin nómina en t ... t+3, inician en t+4 contra no "
    "inician en t+4; resultados en t+3, antes del inicio (efecto verdadero = 0).",
    notas=[
        "La actividad puede incluir mecánicamente el abono de la nómina: un efecto sobre "
        "actividad puede ser de definición.",
        "Cohortes t = 9 ... 13 para tener actividad real en t-3 (mes >= 6).",
    ],
)

DISENO_CANAL = Diseno(
    nombre="canal",
    pregunta="¿El canal de vinculación influye en cuánto tiempo se mantiene activo el cliente?",
    tratamiento="Canal de vinculación KHM (tratado) frente a KHN (referencia).",
    control="Canal KHN.",
    elegibilidad=[
        "Alta (fecha_alta) en julio a octubre de 2015 (meses 6 a 9)",
        "Primer mes en el panel = mes de alta (covariables medidas al entrar)",
        "Presente en el panel de alta+1 a alta+7",
        "Edad >= 18 al entrar",
    ],
    resultados={
        "y_meses_activo_6": "Meses activo entre alta+2 y alta+7 (0 a 6)",
        "y_activo_6": "Activo en alta+7",
    },
    meses_t=list(range(6, 10)),
    covariables="Al entrar (canal, segmento y renta en alta+1, porque se registran con un mes "
    "de retraso): edad, sexo, renta, segmento, extranjero, residente, empleado del "
    "banco, provincia y mes de alta. Los productos del mes de alta no se ajustan: pueden ser "
    "parte del efecto del canal (mediadores).",
    razon_controles=0,
    placebo="No hay un placebo de diseño limpio: el canal se fija al entrar.",
    notas=[
        "Contraste secundario: KHQ frente a KHM con edad 18 a 30 (positividad débil: KHQ es "
        "el canal universitario).",
        "Los códigos de canal están anonimizados: no se sabe qué canal es cada uno.",
    ],
)


def diseno_producto(p: str) -> Diseno:
    """Pregunta 3 para el producto ``p``: ¿adquirirlo frena el paso de activo a inactivo?"""
    nombre = PRODUCTOS[p][1]
    return Diseno(
        nombre=f"producto_{p}",
        pregunta=f"¿Adquirir {nombre.lower()} frena el paso de activo a inactivo?",
        tratamiento=f"Adquiere {p} en t: {p}_t = 1 con {p} = 0 en t-1, t-2 y t-3.",
        control=f"No adquiere {p} en t; puede adquirirlo después (ITT).",
        elegibilidad=[
            "Presente en t-3 ... t+3",
            "Activo en t-1 y t-2",
            f"Sin {p} en t-1, t-2 y t-3",
            "Edad >= 18 en t-1, no fallecido",
        ],
        resultados={
            "y_inactivo_3": "Inactivo en t+3",
            "y_inactivo_1": "Inactivo en t+1 (secundario)",
        },
        meses_t=list(range(9, 14)),
        covariables="Demografía y los 24 productos en t-1; actividad en t-3; otros productos en "
        "t-1, t-3 y t-6; nómina en t-1; mes t.",
        razon_controles=20,
        placebo=f"Adelanto: elegibles sin {p} en t ... t+3; adquieren en t+4 contra no; "
        "resultados en t+3.",
        notas=[
            "Un débito automático o una tarjeta generan movimientos: parte del efecto puede "
            "ser mecánico sobre la definición de actividad."
        ],
    )


def _comunes_x() -> str:
    return f"""
        {_covariables_sql("x")},
        r.activo_m1::DOUBLE AS act_m1, r.activo_m2::DOUBLE AS act_m2,
        r.activo_m3::DOUBLE AS act_m3,
        r.n_otros_m1::DOUBLE AS otros_m1, r.n_otros_m3::DOUBLE AS otros_m3,
        coalesce(r.n_otros_m6, r.n_otros_m3)::DOUBLE AS otros_m6,
        (r.n_otros_m6 IS NULL)::UTINYINT AS sin_m6,
        r.mes AS t
    """


def crear_diseno_nomina(con: duckdb.DuckDBPyConnection, semilla: int = 1) -> None:
    """Tablas ``d_nomina`` (principal) y ``d_nomina_placebo`` (adelanto de 4 meses)."""
    d = DISENO_NOMINA
    frac = 1.0 / d.razon_controles
    base = """
        FROM rezagos r JOIN panel x ON x.cliente = r.cliente AND x.mes = r.mes - 1
        WHERE r.mes BETWEEN {t0} AND {t1}
          AND r.presente_m3 = 1 AND r.presente_m2 = 1 AND r.presente_p1 = 1
          AND r.presente_p2 = 1 AND r.presente_p3 = 1
          AND r.nomina_m1 = 0 AND r.nomina_m2 = 0 AND r.nomina_m3 = 0
          AND x.edad >= 18 AND coalesce(x.fallecido, 'N') = 'N' AND r.activo_m1 IS NOT NULL
    """
    resultados = (
        """
        r.activo_p3::DOUBLE AS y_activo_3,
        (r.n_otros_p3 - r.n_otros_m1)::DOUBLE AS y_dprod_3,
        r.activo_p1::DOUBLE AS y_activo_1,
        r.activo_m1::DOUBLE AS y_activo_base,
        -- trayectorias para el estudio de eventos (diferencias en diferencias)
    """
        + ",\n".join(
            f"r.n_otros_{_sufijo(k)}::DOUBLE AS ev_otros_{_sufijo(k)}" for k in DESFASES if k <= 3
        )
        + ",\n"
        + ",\n".join(
            f"r.activo_{_sufijo(k)}::DOUBLE AS ev_activo_{_sufijo(k)}" for k in range(-3, 4)
        )
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE d_nomina AS
        SELECT r.cliente, r.nomina_t::UTINYINT AS d, {resultados}, {_comunes_x()}
        {base.format(t0=d.meses_t[0], t1=d.meses_t[-1])}
          AND (r.nomina_t = 1 OR {_uniforme(semilla)} < {frac})
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE d_nomina_placebo AS
        SELECT r.cliente, r.nomina_p4::UTINYINT AS d, {resultados}, {_comunes_x()}
        {base.format(t0=d.meses_t[0], t1=d.meses_t[-1] - 1)}
          AND r.nomina_t = 0 AND r.nomina_p1 = 0 AND r.nomina_p2 = 0 AND r.nomina_p3 = 0
          AND r.nomina_p4 IS NOT NULL
          AND (r.nomina_p4 = 1 OR {_uniforme(semilla + 1)} < {frac})
        """
    )


def crear_diseno_producto(con: duckdb.DuckDBPyConnection, p: str, semilla: int = 3) -> None:
    """Tablas ``d_producto_{p}`` y ``d_producto_{p}_placebo``."""
    d = diseno_producto(p)
    frac = 1.0 / d.razon_controles
    u = _uniforme(semilla)
    u2 = _uniforme(semilla + 1)
    base = f"""
        FROM rezagos r JOIN panel x ON x.cliente = r.cliente AND x.mes = r.mes - 1
        WHERE r.mes BETWEEN {{t0}} AND {{t1}}
          AND r.presente_m3 = 1 AND r.presente_m2 = 1 AND r.presente_p1 = 1
          AND r.presente_p2 = 1 AND r.presente_p3 = 1
          AND r.activo_m1 = 1 AND r.activo_m2 = 1
          AND r.{p}_m1 = 0 AND r.{p}_m2 = 0 AND r.{p}_m3 = 0
          AND x.edad >= 18 AND coalesce(x.fallecido, 'N') = 'N'
    """
    resultados = """
        (1 - r.activo_p3)::DOUBLE AS y_inactivo_3,
        (1 - r.activo_p1)::DOUBLE AS y_inactivo_1,
        coalesce(r.nomina_m1, 0)::DOUBLE AS nomina_m1
    """
    con.execute(
        f"""
        CREATE OR REPLACE TABLE d_producto_{p} AS
        SELECT r.cliente, r.{p}_t::UTINYINT AS d, {resultados}, {_comunes_x()}
        {base.format(t0=d.meses_t[0], t1=d.meses_t[-1])}
          AND (r.{p}_t = 1 OR {u} < {frac})
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE d_producto_{p}_placebo AS
        SELECT r.cliente, r.{p}_p4::UTINYINT AS d, {resultados}, {_comunes_x()}
        {base.format(t0=d.meses_t[0], t1=d.meses_t[-1] - 1)}
          AND r.{p}_t = 0 AND r.{p}_p1 = 0 AND r.{p}_p2 = 0 AND r.{p}_p3 = 0
          AND r.{p}_p4 IS NOT NULL
          AND (r.{p}_p4 = 1 OR {u2} < {frac})
        """
    )


def crear_diseno_canal(con: duckdb.DuckDBPyConnection) -> None:
    """Tabla ``d_canal``: altas de julio a octubre de 2015 con su canal y su actividad.

    En el mes de alta el canal y el segmento faltan casi siempre (99,5 % y 100 %) y la renta
    en el 64 %: se registran el mes siguiente. Por eso esas tres variables se toman de
    alta+1 y la actividad se mide de alta+2 a alta+7.
    """
    d = DISENO_CANAL
    con.execute(
        f"""
        CREATE OR REPLACE TABLE d_canal AS
        WITH primeros AS (
            SELECT cliente, min(mes) AS m0 FROM panel GROUP BY 1
        ),
        e AS (
            SELECT x.* REPLACE (y.canal AS canal, y.segmento AS segmento, y.renta AS renta)
            FROM primeros pr
            JOIN panel x ON x.cliente = pr.cliente AND x.mes = pr.m0
            JOIN panel y ON y.cliente = pr.cliente AND y.mes = pr.m0 + 1
            WHERE pr.m0 BETWEEN {d.meses_t[0]} AND {d.meses_t[-1]}
              AND (year(x.fecha_alta) - 2015) * 12 + month(x.fecha_alta) - 1 = pr.m0
              AND x.edad >= 18 AND y.canal IN ('KHM', 'KHN', 'KHQ')
        ),
        seguimiento AS (
            SELECT e.cliente, sum(z.activo) AS meses_activo, count(*) AS meses,
                   max(z.activo) FILTER (WHERE z.mes = e.mes + 7) AS activo_7
            FROM e JOIN panel z ON z.cliente = e.cliente
                               AND z.mes BETWEEN e.mes + 2 AND e.mes + 7
            GROUP BY 1
        )
        SELECT e.cliente, e.canal,
               (e.canal = 'KHM')::UTINYINT AS d,
               s.meses_activo::DOUBLE AS y_meses_activo_6,
               s.activo_7::DOUBLE AS y_activo_6,
               {_covariables_sql("e")},
               e.mes AS t
        FROM e JOIN seguimiento s ON s.cliente = e.cliente AND s.meses = 6
        """
    )


def crear_todos(con: duckdb.DuckDBPyConnection) -> None:
    """Rezagos y las tablas de los tres diseños."""
    crear_rezagos(con)
    crear_diseno_nomina(con)
    for p in PRODUCTOS_P3:
        crear_diseno_producto(con, p)
    crear_diseno_canal(con)


TABLAS = ("d_nomina", "d_nomina_placebo", "d_canal") + tuple(
    f"d_producto_{p}{s}" for p in PRODUCTOS_P3 for s in ("", "_placebo")
)


def conteos(con: duckdb.DuckDBPyConnection) -> dict:
    """Tratados y controles por cohorte de cada diseño. No mira resultados."""
    salida = {}
    for tabla in TABLAS:
        if tabla == "d_canal":
            filas = con.execute(
                "SELECT canal, t, count(*) FROM d_canal GROUP BY ALL ORDER BY ALL"
            ).fetchall()
            salida[tabla] = {
                "por_mes": [{"canal": c, "t": t, "clientes": n} for c, t, n in filas],
                "por_canal": {
                    c: sum(n for c2, _, n in filas if c2 == c)
                    for c in sorted({f[0] for f in filas})
                },
            }
            continue
        filas = con.execute(
            f"SELECT t, count(*) FILTER (WHERE d = 1), count(*) FILTER (WHERE d = 0) "
            f"FROM {tabla} GROUP BY 1 ORDER BY 1"
        ).fetchall()
        salida[tabla] = {
            "por_mes": [{"t": t, "tratados": a, "controles": b} for t, a, b in filas],
            "tratados": sum(a for _, a, _ in filas),
            "controles": sum(b for _, _, b in filas),
        }
    return salida


def leer(con: duckdb.DuckDBPyConnection, tabla: str) -> pd.DataFrame:
    """Tabla de diseño como DataFrame, ordenada de forma estable."""
    return con.execute(f"SELECT * FROM {tabla} ORDER BY t, cliente").df()


def columnas_x(df: pd.DataFrame, diseno: str) -> list[str]:
    """Covariables de ajuste del diseño (las del preregistro).

    En ``canal`` se excluyen los productos y la relación del mes de alta (posibles
    mediadores), los indicadores de canal (son el tratamiento) y lo que es constante al entrar.
    """
    fuera = {"cliente", "d", "canal"}
    cols = [c for c in df.columns if c not in fuera and not c.startswith(("y_", "ev_"))]
    if diseno == "canal":
        excluir = {"relacion_activa", "nuevo", "antiguedad", "canal_faltante"}
        cols = [c for c in cols if not c.startswith(("x_", "canal_")) and c not in excluir]
    return cols
