"""Preregistro de las preguntas causales en Santander, escrito antes de estimar efectos.

Guarda en un JSON las preguntas, el DAG supuesto, los tratamientos, resultados, ventanas,
covariables, métodos, criterios de refutación y la regla de veredicto, junto con la huella
SHA-256 del código que los implementa. Cualquier cambio posterior en esos archivos queda a la
vista y se informa como desviación.
"""

import hashlib
from dataclasses import asdict
from pathlib import Path

from causal import disenos, flujo_hito4, refutaciones
from causal.rutas import RAIZ

ARCHIVOS_HUELLA = (
    "src/causal/ingesta.py",
    "src/causal/disenos.py",
    "src/causal/metodos.py",
    "src/causal/refutaciones.py",
    "src/causal/flujo_hito4.py",
    "docs/resultados/hito1/exploracion.json",
    "docs/resultados/hito3/hillstrom.json",
    "docs/resultados/hito3/semisintetico.json",
)
TEXTO = {".json", ".md", ".py", ".csv", ".txt"}

# DAG supuesto: aristas (origen, destino). "U" son rasgos no observados.
DAG = {
    "nomina": [
        ("Demografía en t-1 (edad, sexo, renta, segmento, provincia, canal)", "Inicia nómina en t"),
        ("Demografía en t-1 (edad, sexo, renta, segmento, provincia, canal)", "Resultado en t+3"),
        ("Historia: actividad t-1..t-3, productos t-1/t-3/t-6", "Inicia nómina en t"),
        ("Historia: actividad t-1..t-3, productos t-1/t-3/t-6", "Resultado en t+3"),
        ("Mes t", "Inicia nómina en t"),
        ("Mes t", "Resultado en t+3"),
        ("Inicia nómina en t", "Resultado en t+3"),
        ("Inicia nómina en t", "Cuenta nómina (excluida del resultado)"),
        ("U: cambio de empleo (no observado)", "Inicia nómina en t"),
        ("U: cambio de empleo (no observado)", "Resultado en t+3"),
    ],
    "canal": [
        ("Perfil al entrar (edad, sexo, renta, segmento, provincia, mes)", "Canal de alta"),
        ("Perfil al entrar (edad, sexo, renta, segmento, provincia, mes)", "Meses activo"),
        ("Canal de alta", "Productos del mes de alta (mediador, no se ajusta)"),
        ("Productos del mes de alta (mediador, no se ajusta)", "Meses activo"),
        ("Canal de alta", "Meses activo"),
        ("U: motivación o necesidad del cliente (no observada)", "Canal de alta"),
        ("U: motivación o necesidad del cliente (no observada)", "Meses activo"),
    ],
    "producto": [
        ("Demografía y productos en t-1", "Adquiere el producto en t"),
        ("Demografía y productos en t-1", "Inactivo en t+3"),
        ("Historia: actividad t-3, productos t-3/t-6, nómina t-1", "Adquiere el producto en t"),
        ("Historia: actividad t-3, productos t-3/t-6, nómina t-1", "Inactivo en t+3"),
        ("Adquiere el producto en t", "Inactivo en t+3"),
        ("U: planes de dejar o concentrar el banco (no observado)", "Adquiere el producto en t"),
        ("U: planes de dejar o concentrar el banco (no observado)", "Inactivo en t+3"),
    ],
}

SUPUESTOS = [
    "Intercambiabilidad condicional: dadas las covariables de t-1 (y antes), iniciar o no el "
    "tratamiento en t es como si fuera al azar. Es el supuesto que no se puede probar; el placebo "
    "de adelanto y la sensibilidad lo ponen a prueba.",
    "Positividad: cada perfil de covariables tiene clientes tratados y no tratados. Se revisa con "
    "la distribución de la propensión.",
    "Consistencia y no interferencia: el resultado de un cliente depende solo de su tratamiento.",
    "Las covariables de t-1 no son consecuencia del tratamiento en t.",
    "Nómina (DiD): tendencias paralelas condicionales entre t-1 y t+3.",
]

LIMITACIONES = [
    "Datos observacionales: ningún método garantiza que no haya confusión no observada.",
    "La actividad (ind_actividad_cliente) no tiene definición pública: puede incluir "
    "mecánicamente el abono de la nómina o los movimientos de un débito o una tarjeta.",
    "Enero a julio de 2015 no sirven para variables no-producto (congeladas).",
    "Los códigos de canal están anonimizados.",
    "El panel termina en mayo de 2016: los resultados se miden a 3 meses (6 en el canal).",
    "Efecto de intención de tratar: algunos controles inician el tratamiento después.",
]


def _sha256(ruta: Path) -> str:
    contenido = ruta.read_bytes()
    if ruta.suffix in TEXTO:
        contenido = contenido.replace(b"\r\n", b"\n")
    return hashlib.sha256(contenido).hexdigest()


def construir(conteos: dict, validacion: dict) -> dict:
    """Contenido del preregistro (``conteos``: del hito 1; ``validacion``: resumen del hito 3)."""
    preguntas = {
        "nomina": disenos.DISENO_NOMINA.como_dict(),
        "canal": disenos.DISENO_CANAL.como_dict(),
        **{f"producto_{p}": disenos.diseno_producto(p).como_dict() for p in disenos.PRODUCTOS_P3},
    }
    return {
        "titulo": "Preregistro de las preguntas causales en Santander",
        "estado": "Escrito antes de estimar cualquier efecto en Santander (tag preregistro).",
        "preguntas": preguntas,
        "analisis": [asdict(a) for a in flujo_hito4.ANALISIS],
        "primarios": [a.id for a in flujo_hito4.ANALISIS if a.primario],
        "dag": {k: [{"desde": a, "hacia": b} for a, b in v] for k, v in DAG.items()},
        "metodos": {
            "principal": "dml_att: Double ML (modelo interactivo, puntaje del ATT, ajuste "
            "cruzado de 3 pliegues, LightGBM), sobre todas las filas del diseño.",
            "secundarios": [
                "emparejamiento por propensión (logística, 1:1 con reemplazo, caliper 0,2 sd)",
                f"bosque causal (CausalForestDML) sobre hasta {flujo_hito4.MAX_FILAS_BOSQUE} filas",
                "diferencias en diferencias doble robusto (solo nómina -> actividad; en "
                "nómina -> productos el resultado ya es un cambio)",
                "regresión lineal e ingenuo, como referencia",
            ],
            "refutaciones": {
                "dowhy": f"placebo por permutación, causa común aleatoria y subconjunto del 80 % "
                f"({flujo_hito4.SIMULACIONES_DOWHY} simulaciones, LinearDML, hasta "
                f"{flujo_hito4.MAX_FILAS_DOWHY} filas)",
                "placebo_adelanto": "mismo estimador sobre la tabla placebo del diseño",
                "sensibilidad": "valor de robustez (Cinelli y Hazlett) y valor E",
                "consistencia": "entre métodos",
            },
            "multiplicidad": "Holm-Bonferroni sobre los p-valores de los análisis primarios.",
            "validacion": validacion,
        },
        "criterios": refutaciones.CRITERIOS,
        "veredicto": {
            "sin efecto detectable": "El IC del estimador principal incluye el cero.",
            "creíble": "Significativo; pasan placebo de adelanto, consistencia y los tres "
            "refutadores de DoWhy; robusto en sensibilidad.",
            "creíble pero sensible": "Como 'creíble', pero un confusor omitido más débil que la "
            "covariable observada más fuerte bastaría para anularlo.",
            "no separable de la selección": "Falla el placebo de adelanto.",
            "frágil": "Falla la consistencia entre métodos o algún refutador de DoWhy.",
        },
        "supuestos": SUPUESTOS,
        "limitaciones": LIMITACIONES,
        "conteos_disenos": conteos,
        "desviaciones": "Cualquier cambio en los archivos con huella después del tag se "
        "informa en docs/preregistro.md como desviación, con su motivo.",
        "huellas_sha256": {r: _sha256(RAIZ / r) for r in ARCHIVOS_HUELLA if (RAIZ / r).exists()},
    }


def positividad(con) -> dict:
    """Distribución de la propensión (logística) en cada diseño. No lee resultados."""
    import numpy as np

    from causal.metodos import propension_logistica

    salida = {}
    for a in flujo_hito4.ANALISIS:
        if not a.primario and a.id != "canal_khq_jovenes":
            continue
        nombres = [
            r[0] for r in con.execute(f"SELECT column_name FROM (DESCRIBE {a.tabla})").fetchall()
        ]
        diseno = "canal" if a.pregunta == "canal" else a.pregunta
        cols = disenos.nombres_x(nombres, diseno)
        extra = ", canal" if "canal" in nombres else ""
        where = f"WHERE {a.filtro}" if a.filtro else ""
        df = con.execute(f"SELECT d{extra}, {', '.join(cols)} FROM {a.tabla} {where}").df()
        if a.tratado:
            df["d"] = (df["canal"] == a.tratado).astype(int)
        cols = [c for c in cols if df[c].nunique(dropna=False) > 1]
        d = df["d"].to_numpy()
        ps = propension_logistica(df[cols], d)
        q = [0.01, 0.05, 0.5, 0.95, 0.99]
        salida[a.id] = {
            "tratados": int(d.sum()),
            "controles": int((1 - d).sum()),
            "cuantiles_tratados": dict(
                zip(map(str, q), np.quantile(ps[d == 1], q).tolist(), strict=True)
            ),
            "cuantiles_controles": dict(
                zip(map(str, q), np.quantile(ps[d == 0], q).tolist(), strict=True)
            ),
            "frac_tratados_propension_mayor_0_95": float((ps[d == 1] > 0.95).mean()),
            "frac_controles_propension_menor_0_001": float((ps[d == 0] < 0.001).mean()),
        }
    return salida
