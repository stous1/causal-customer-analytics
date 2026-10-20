"""Hito 4: estimación causal en Santander de las preguntas preregistradas.

Se corre **después** del tag ``preregistro``. Cada análisis (``ANALISIS``) sigue el protocolo
de ``docs/preregistro.md``: Double ML (ATT) como estimador principal; emparejamiento, bosque
causal y, en la nómina, diferencias en diferencias como secundarios; refutaciones de DoWhy,
placebo de adelanto, sensibilidad a variables omitidas, consistencia entre métodos y
corrección de Holm sobre los resultados primarios.
"""

import time
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

from causal import disenos, graficos, metodos, refutaciones
from causal.util import escribir_json

MAX_FILAS_BOSQUE = 120_000
MAX_FILAS_DOWHY = 40_000
SIMULACIONES_DOWHY = 5


@dataclass
class Analisis:
    id: str
    pregunta: str  # clave del diseño
    tabla: str
    resultado: str
    primario: bool
    descripcion: str
    tabla_placebo: str | None = None
    y_pre: str | None = None  # resultado previo para diferencias en diferencias
    filtro: str = ""
    tratado: str = ""  # para el canal: qué canal es el tratado
    binario: bool = True


ANALISIS: tuple[Analisis, ...] = (
    Analisis(
        "nomina_actividad",
        "nomina",
        "d_nomina",
        "y_activo_3",
        True,
        "Iniciar la nómina -> activo en t+3",
        "d_nomina_placebo",
        y_pre="y_activo_base",
    ),
    Analisis(
        "nomina_productos",
        "nomina",
        "d_nomina",
        "y_dprod_3",
        True,
        "Iniciar la nómina -> cambio en otros productos (t-1 a t+3)",
        "d_nomina_placebo",
        binario=False,
    ),
    Analisis(
        "nomina_actividad_1",
        "nomina",
        "d_nomina",
        "y_activo_1",
        False,
        "Iniciar la nómina -> activo en t+1",
        "d_nomina_placebo",
    ),
    Analisis(
        "canal_meses_activo",
        "canal",
        "d_canal",
        "y_meses_activo_6",
        True,
        "Alta por KHM (frente a KHN) -> meses activo de alta+2 a alta+7",
        filtro="canal IN ('KHM', 'KHN')",
        tratado="KHM",
        binario=False,
    ),
    Analisis(
        "canal_activo_7",
        "canal",
        "d_canal",
        "y_activo_6",
        False,
        "Alta por KHM (frente a KHN) -> activo en alta+7",
        filtro="canal IN ('KHM', 'KHN')",
        tratado="KHM",
    ),
    Analisis(
        "canal_khq_jovenes",
        "canal",
        "d_canal",
        "y_meses_activo_6",
        False,
        "Alta por KHQ (frente a KHM), 18 a 30 años -> meses activo",
        filtro="canal IN ('KHQ', 'KHM') AND edad BETWEEN 18 AND 30",
        tratado="KHQ",
        binario=False,
    ),
) + tuple(
    a
    for p in disenos.PRODUCTOS_P3
    for a in (
        Analisis(
            f"producto_{p}",
            f"producto_{p}",
            f"d_producto_{p}",
            "y_inactivo_3",
            True,
            f"Adquirir {p} estando activo -> inactivo en t+3",
            f"d_producto_{p}_placebo",
        ),
        Analisis(
            f"producto_{p}_1",
            f"producto_{p}",
            f"d_producto_{p}",
            "y_inactivo_1",
            False,
            f"Adquirir {p} estando activo -> inactivo en t+1",
            f"d_producto_{p}_placebo",
        ),
    )
)


def cargar(
    con: duckdb.DuckDBPyConnection, a: Analisis, tabla: str | None = None
) -> tuple[pd.DataFrame, list[str]]:
    """Datos del análisis con ``d`` ya definido y la lista de covariables."""
    tabla = tabla or a.tabla
    where = f"WHERE {a.filtro}" if a.filtro else ""
    df = con.execute(f"SELECT * FROM {tabla} {where} ORDER BY t, cliente").df()
    if a.tratado:
        df["d"] = (df["canal"] == a.tratado).astype(np.int8)
    diseno = "canal" if a.pregunta == "canal" else a.pregunta
    cols = disenos.columnas_x(df, diseno)
    # sin variación no aportan y rompen la regresión lineal
    cols = [c for c in cols if df[c].nunique(dropna=False) > 1]
    df = df[df[a.resultado].notna()].reset_index(drop=True)
    return df, cols


def _submuestra(df: pd.DataFrame, maximo: int, semilla: int) -> pd.DataFrame:
    """Todos los tratados (hasta la mitad del máximo) y controles al azar hasta ``maximo``."""
    if len(df) <= maximo:
        return df
    rng = np.random.default_rng(semilla)
    t = np.flatnonzero(df["d"].to_numpy() == 1)
    c = np.flatnonzero(df["d"].to_numpy() == 0)
    t = np.sort(rng.choice(t, size=min(len(t), maximo // 2), replace=False))
    c = np.sort(rng.choice(c, size=min(len(c), maximo - len(t)), replace=False))
    return df.iloc[np.sort(np.r_[t, c])].reset_index(drop=True)


def _p(est: metodos.Estimacion) -> float:
    return float(2 * (1 - stats.norm.cdf(abs(est.efecto / est.ee)))) if est.ee > 0 else 0.0


def estudio_eventos(
    df: pd.DataFrame, cols: list[str], prefijo: str, base: str, desfases: list[str], reps: int = 200
) -> list[dict]:
    """Diferencia media tratados-controles emparejados de Y_k - Y_base, por desfase k."""
    X, d = df[cols], df["d"].to_numpy()
    t_idx, c_idx, _ = metodos.parejas(X, d)
    rng = np.random.default_rng(0)
    salida = []
    for k in desfases:
        col = f"{prefijo}_{k}"
        dif = (df[col].to_numpy()[t_idx] - df[base].to_numpy()[t_idx]) - (
            df[col].to_numpy()[c_idx] - df[base].to_numpy()[c_idx]
        )
        dif = dif[~np.isnan(dif)]
        boot = [dif[rng.integers(0, len(dif), len(dif))].mean() for _ in range(reps)]
        salida.append(
            {
                "desfase": k,
                "efecto": float(dif.mean()),
                "ic95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                "n": int(len(dif)),
            }
        )
    return salida


def analizar(con: duckdb.DuckDBPyConnection, a: Analisis, semilla: int = 0) -> dict:
    inicio = time.time()
    df, cols = cargar(con, a)
    X, d, y = df[cols], df["d"].to_numpy(), df[a.resultado].to_numpy(dtype=float)
    est: dict[str, metodos.Estimacion] = {
        "ingenuo": metodos.ingenuo(X, d, y),
        "regresion": metodos.regresion(X, d, y),
        "emparejamiento": metodos.emparejamiento(X, d, y, semilla=semilla),
        "dml_att": metodos.dml_att(X, d, y, semilla=semilla),
    }
    if a.y_pre:
        est["did_dr"] = metodos.did_dr(X, d, y, df[a.y_pre].to_numpy(dtype=float), semilla=semilla)
    sub = _submuestra(df, MAX_FILAS_BOSQUE, semilla)
    est["bosque_causal"] = metodos.bosque_causal(
        sub[cols], sub["d"].to_numpy(), sub[a.resultado].to_numpy(dtype=float), semilla=semilla
    )
    principal = est["dml_att"]
    res: dict = {
        "id": a.id,
        "descripcion": a.descripcion,
        "diseno": a.pregunta,
        "resultado": a.resultado,
        "primario": a.primario,
        "metodo_principal": "dml_att",
        "estimando": "ATT (efecto en los tratados, intención de tratar)",
        "efecto": principal.efecto,
        "ic95": list(principal.ic95),
        "p_valor": _p(principal),
        "n": principal.n,
        "n_tratados": principal.n_tratados,
        "media_tratados": float(y[d == 1].mean()),
        "metodos": {k: v.como_dict() for k, v in est.items()},
        "covariables": cols,
    }
    # placebo de adelanto
    if a.tabla_placebo:
        dp, cp = cargar(con, a, a.tabla_placebo)
        pl = metodos.dml_att(
            dp[cp], dp["d"].to_numpy(), dp[a.resultado].to_numpy(dtype=float), semilla=semilla
        )
        res["placebo_adelanto"] = {
            **pl.como_dict(),
            "pasa": bool(abs(pl.efecto) <= 0.25 * abs(principal.efecto)),
            "ic_contiene_cero": bool(pl.ic95[0] <= 0 <= pl.ic95[1]),
            "criterio": refutaciones.CRITERIOS["placebo_adelanto"],
        }
    # DoWhy
    dsub = _submuestra(df, MAX_FILAS_DOWHY, semilla + 1)
    res["dowhy"] = refutaciones.refutar_dowhy(dsub, cols, a.resultado, SIMULACIONES_DOWHY, semilla)
    res["sensibilidad"] = refutaciones.sensibilidad(df, cols, a.resultado)
    if a.binario:
        riesgo_t = float(y[d == 1].mean())
        res["valor_e"] = refutaciones.valor_e(riesgo_t, riesgo_t - principal.efecto)
    comparables = {k: est[k].efecto for k in ("emparejamiento", "dml_att", "bosque_causal")}
    if "did_dr" in est:
        comparables["did_dr"] = est["did_dr"].efecto
    res["consistencia"] = refutaciones.consistencia(comparables)
    if a.id == "nomina_actividad":
        res["estudio_eventos"] = {
            "actividad": estudio_eventos(
                df, cols, "ev_activo", "ev_activo_m1", ["m3", "m2", "m1", "t", "p1", "p2", "p3"]
            ),
            "otros_productos": estudio_eventos(
                df,
                cols,
                "ev_otros",
                "ev_otros_m1",
                ["m6", "m5", "m4", "m3", "m2", "m1", "t", "p1", "p2", "p3"],
            ),
        }
    res["pruebas"] = _pruebas(res)
    res["segundos"] = round(time.time() - inicio)
    return res


def _pruebas(res: dict) -> dict:
    p = {
        "significativo": not (res["ic95"][0] <= 0 <= res["ic95"][1]),
        **{k: v["pasa"] for k, v in res["dowhy"]["refutadores"].items()},
        "consistencia": res["consistencia"]["pasa"],
        "sensibilidad_robusto": res["sensibilidad"]["robusto"],
    }
    if "placebo_adelanto" in res:
        p["placebo_adelanto"] = res["placebo_adelanto"]["pasa"]
    return p


def veredicto(res: dict) -> str:
    """Regla preregistrada de veredicto."""
    p = res["pruebas"]
    if not p["significativo"]:
        return "sin efecto detectable"
    diseno_ok = p.get("placebo_adelanto", True) and p["consistencia"]
    refut_ok = p["placebo_permutacion"] and p["causa_comun_aleatoria"] and p["subconjunto"]
    if diseno_ok and refut_ok:
        return "creíble" if p["sensibilidad_robusto"] else "creíble pero sensible"
    if not p.get("placebo_adelanto", True):
        return "no separable de la selección"
    return "frágil"


def ejecutar(con: duckdb.DuckDBPyConnection, salida: Path, solo: list[str] | None = None) -> dict:
    resultados = {}
    ruta = salida / "estimaciones.json"
    for a in ANALISIS:
        if solo and a.id not in solo:
            continue
        r = analizar(con, a)
        resultados[a.id] = r
        print(
            f"{a.id}: {r['efecto']:.4f} {[round(x, 4) for x in r['ic95']]} "
            f"pruebas {r['pruebas']} ({r['segundos']} s)",
            flush=True,
        )
        escribir_json({"analisis": resultados}, ruta)
    primarios = {k: v["p_valor"] for k, v in resultados.items() if v["primario"]}
    ajustados = refutaciones.holm(primarios) if primarios else {}
    for k, v in resultados.items():
        v["p_holm"] = ajustados.get(k)
        v["veredicto"] = veredicto(v)
    salida_json = {
        "analisis": resultados,
        "definiciones": {a.id: asdict(a) for a in ANALISIS},
        "criterios": refutaciones.CRITERIOS,
        "tipo": "causal",
    }
    escribir_json(salida_json, ruta)
    return salida_json


NOMBRES = {
    "ingenuo": "Ingenuo",
    "regresion": "Regresión lineal",
    "emparejamiento": "Emparejamiento",
    "dml_att": "Double ML (principal)",
    "did_dr": "Dif. en dif. (DR)",
    "bosque_causal": "Bosque causal",
}


def graficos_hito4(res: dict, salida: Path) -> None:
    filas = []
    for k, r in res["analisis"].items():
        for m, e in r["metodos"].items():
            filas.append(
                {
                    "analisis": r["descripcion"],
                    "metodo": NOMBRES[m],
                    "efecto": e["efecto"],
                    "inf": e["ic95"][0],
                    "sup": e["ic95"][1],
                    "id": k,
                }
            )
        if "placebo_adelanto" in r:
            pl = r["placebo_adelanto"]
            filas.append(
                {
                    "analisis": r["descripcion"],
                    "metodo": "Placebo de adelanto",
                    "efecto": pl["efecto"],
                    "inf": pl["ic95"][0],
                    "sup": pl["ic95"][1],
                    "id": k,
                }
            )
    df = pd.DataFrame(filas)
    primarios = [k for k, r in res["analisis"].items() if r["primario"]]
    g = graficos.intervalos(
        df[df["id"].isin(primarios)],
        "metodo",
        "efecto",
        "inf",
        "sup",
        fila="analisis",
        titulo="Efectos estimados en Santander (resultados primarios), IC 95 %",
        eje_x="Efecto en los tratados",
        ancho=420,
    )
    graficos.guardar(g, salida / "efectos")
    ev = res["analisis"].get("nomina_actividad", {}).get("estudio_eventos")
    if ev:
        orden = {
            "m6": -6,
            "m5": -5,
            "m4": -4,
            "m3": -3,
            "m2": -2,
            "m1": -1,
            "t": 0,
            "p1": 1,
            "p2": 2,
            "p3": 3,
        }
        filas = []
        for nombre, serie in (
            ("Activo", ev["actividad"]),
            ("Otros productos", ev["otros_productos"]),
        ):
            for e in serie:
                filas.append(
                    {
                        "serie": nombre,
                        "k": orden[e["desfase"]],
                        "efecto": e["efecto"],
                        "inf": e["ic95"][0],
                        "sup": e["ic95"][1],
                    }
                )
        d = pd.DataFrame(filas)
        import altair as alt

        paneles = []
        for nombre in dict.fromkeys(d["serie"]):
            base = alt.Chart(d[d["serie"] == nombre]).encode(
                x=alt.X("k:Q", title="Meses respecto del inicio de la nómina")
            )
            paneles.append(
                alt.layer(
                    alt.Chart(pd.DataFrame({"r": [-0.5]}))
                    .mark_rule(strokeDash=[4, 3], color=graficos.NARANJA)
                    .encode(x="r:Q"),
                    base.mark_rule(color=graficos.GRIS).encode(y="inf:Q", y2="sup:Q"),
                    base.mark_line(point=True, color=graficos.AZUL).encode(
                        y=alt.Y("efecto:Q", title="Tratados - controles emparejados")
                    ),
                ).properties(width=260, height=200, title=nombre)
            )
        g = alt.hconcat(*paneles).properties(
            title="Estudio de eventos de la nómina (diferencia respecto de t-1)"
        )
        graficos.guardar(g, salida / "estudio_eventos")
