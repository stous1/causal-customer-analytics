"""Contrasta las cifras del README y de las páginas de Pages con los JSON publicados.

Uso:
    uv run python scripts/verificar_cifras.py   # sale con código 1 si algo no coincide

Cada comprobación busca la línea de un documento que contiene un texto (la fila de una tabla
o una frase) y exige que aparezcan en ella (o en la línea siguiente) los valores sacados de
``docs/resultados``, formateados como en el texto (coma decimal, punto de miles).
"""

import sys

from causal.rutas import DOCS, DOCS_RESULTADOS, RAIZ
from causal.util import coma, leer_json, miles


def _j(ruta: str) -> dict:
    return leer_json(DOCS_RESULTADOS / ruta)


def pct(x: float) -> str:
    return f"{round(x * 100)} %"


def comprobaciones() -> list[tuple[str, str, list[str]]]:
    h1 = _j("hito1/exploracion.json")
    carga, inc = h1["carga"], h1["inconsistencias"]
    evo = {e["mes"]: e for e in h1["evolucion"]}
    conteos = h1["conteos_disenos"]
    vacias = h1["filas_vacias"]
    tardio = h1["registro_tardio"]
    salida = [
        (
            "docs/hito1.md",
            "Santander Product Recommendation:",
            [miles(carga["filas"]), miles(carga["clientes"])],
        ),
        (
            "docs/hito1.md",
            "**2. En julio de 2015 entran al panel",
            [
                miles(evo[6]["entran"]),
                miles(evo[6]["alta_este_mes"]),
                pct(evo[5]["tasa_actividad"]),
                pct(evo[6]["tasa_actividad"]),
            ],
        ),
        (
            "docs/hito1.md",
            "**3. Registro tardío",
            [pct(tardio["canal_alta"]), pct(tardio["segmento_alta"])],
        ),
        (
            "docs/hito1.md",
            "| Filas sin demografía",
            [miles(vacias["filas"]), miles(vacias["clientes"])],
        ),
        (
            "docs/hito1.md",
            "| La edad disminuye",
            [miles(inc["meses_consecutivos"]["edad_disminuye"])],
        ),
        (
            "docs/hito1.md",
            "| Fecha de alta posterior",
            [miles(inc["valores"]["alta_posterior_al_mes"])],
        ),
        (
            "docs/hito1.md",
            "| Marcado como fallecido y activo",
            [miles(inc["valores"]["fallecido_activo"])],
        ),
        (
            "docs/hito1.md",
            "| Menores de 18 años",
            [miles(inc["valores"]["menores_de_18"]), miles(inc["valores"]["menores_con_nomina"])],
        ),
        ("docs/hito1.md", "| Mayores de 100", [miles(inc["valores"]["mayores_de_100"])]),
        (
            "docs/hito1.md",
            "| Clientes que cambian de segmento",
            [miles(inc["por_cliente"]["cambia_segmento"])],
        ),
        ("docs/hito1.md", "| Pensión sin nómina", [miles(inc["valores"]["nom_pens_sin_nomina"])]),
        (
            "docs/hito1.md",
            "La renta falta en el",
            [pct(h1["faltantes_por_mes"][0]["renta"]), pct(h1["faltantes_por_mes"][-1]["renta"])],
        ),
        ("docs/hito1.md", "| Nómina | Inicia", [miles(conteos["d_nomina"]["tratados"])]),
        (
            "docs/hito1.md",
            "| Canal | Alta por",
            [
                miles(conteos["d_canal"]["por_canal"]["KHM"]),
                miles(conteos["d_canal"]["por_canal"]["KHN"]),
            ],
        ),
        (
            "docs/hito1.md",
            "| Débito automático |",
            [miles(conteos["d_producto_recibo"]["tratados"])],
        ),
        (
            "docs/hito1.md",
            "| Tarjeta de crédito |",
            [miles(conteos["d_producto_tjcr"]["tratados"])],
        ),
        (
            "docs/hito1.md",
            "| Cuenta electrónica |",
            [miles(conteos["d_producto_ecue"]["tratados"])],
        ),
    ]
    salida += comprobaciones_hito2()
    salida += comprobaciones_hito3()
    salida += comprobaciones_hito4()
    salida += comprobaciones_hito5()
    salida += comprobaciones_readme()
    return salida


def comprobaciones_hito5() -> list[tuple[str, str, list[str]]]:
    h5 = _j("hito5/heterogeneidad.json")
    m = h5["hillstrom"]["brazos"]["mujer"]
    q1, q5 = m["quintiles_prueba"][0], m["quintiles_prueba"][-1]
    pol = h5["hillstrom"]["politica"]
    sa = h5["santander"]
    salida = [
        (
            "docs/hito5.md",
            "efecto real es",
            [coma(q1["efecto_real"], 3), _ic(q1["ic95"], 3).strip("()").split(" a ")[0]],
        ),
        (
            "docs/hito5.md",
            "en el de mayor efecto,",
            [coma(q5["efecto_real"], 3), _ic(q5["ic95"], 3)],
        ),
        ("docs/hito5.md", "mujer. Qini en prueba:", [coma(m["qini_auc_prueba"], 3)]),
        (
            "docs/hito5.md",
            "hay heterogeneidad que aprovechar. Qini",
            [coma(h5["hillstrom"]["brazos"]["hombre"]["qini_auc_prueba"], 3)],
        ),
        (
            "docs/hito5.md",
            "correo): manda correo de mujer al",
            [f"{round(pol['reparto_prueba']['correo de mujer'] * 100)} %"],
        ),
        (
            "docs/hito5.md",
            "visitas por cliente) **no supera**",
            [coma(pol["valor_neto_prueba"]["todos_hombre"]["valor"], 3)],
        ),
        ("docs/hito5.md", "correo): manda", []),
    ]
    for p, ancla in (
        ("producto_tjcr", "| Tarjeta de crédito |"),
        ("producto_ecue", "| Cuenta electrónica |"),
    ):
        pc = sa[p]["predice_contra_causa"]
        qs = pc["cate_medio_por_quintil_de_propension"]
        salida.append(
            (
                "docs/hito5.md",
                ancla,
                [
                    f"+{coma(pc['correlacion_spearman'], 2)}",
                    f"{coma(qs['1'] * 100, 1)} pp".replace("-", "−"),
                    f"{coma(qs['5'] * 100, 1)} pp".replace("-", "−"),
                ],
            )
        )
    t = sa["producto_tjcr"]["politica"]["efecto_dr_mitad_prueba"]
    e = sa["producto_ecue"]["politica"]["efecto_dr_mitad_prueba"]
    salida.append(
        (
            "docs/hito5.md",
            "robusto en la mitad de prueba:",
            [
                f"{coma(t['recomendados'] * 100, 1)} pp".replace("-", "−"),
                f"{coma(e['recomendados'] * 100, 1)} pp".replace("-", "−"),
            ],
        )
    )
    salida.append(
        (
            "docs/hito5.md",
            "−0,1 pp y −0,7 pp",
            [
                f"{coma(t['no_recomendados'] * 100, 1)} pp".replace("-", "−"),
                f"{coma(e['no_recomendados'] * 100, 1)} pp".replace("-", "−"),
            ],
        )
    )
    return salida


def comprobaciones_readme() -> list[tuple[str, str, list[str]]]:
    h2 = _j("hito2/metricas.json")
    est = _j("hito4/estimaciones.json")["analisis"]
    hs = _j("hito3/hillstrom.json")["experimento_sesgado"]["metodos"]
    n = est["nomina_actividad"]
    c = est["canal_meses_activo"]
    return [
        (
            "README.md",
            "MAP@7 de **",
            [coma(h2["map7"]["modelo"], 3), coma(h2["map7"]["referencia"], 3)],
        ),
        (
            "README.md",
            "ingenuo se equivoca",
            [
                f"{round(hs['ingenuo']['resumen']['sesgo_relativo'] * 100)} %",
                f"Double ML {round(hs['dml_att']['resumen']['sesgo_relativo'] * 100)} %",
            ],
        ),
        (
            "README.md",
            "| ¿La nómina vuelve más activo al cliente? |",
            [
                f"+{coma(n['efecto'] * 100, 1)} pp",
                f"({coma(n['ic95'][0] * 100, 1)} a {coma(n['ic95'][1] * 100, 1)})",
                f"{coma(n['placebo_adelanto']['efecto'] * 100, 1)} pp",
                n["veredicto"],
            ],
        ),
        (
            "README.md",
            "| ¿El canal de vinculación",
            [f"−{coma(abs(c['efecto']), 2)} meses", c["veredicto"]],
        ),
        (
            "docs/index.md",
            "| ¿La nómina vuelve más activo al cliente? |",
            [
                f"+{coma(n['efecto'] * 100, 1)} pp",
                f"{coma(n['placebo_adelanto']['efecto'] * 100, 1)} pp",
            ],
        ),
        (
            "docs/index.md",
            "| ¿El canal de vinculación",
            [f"−{coma(abs(c['efecto']), 2)} meses", c["veredicto"]],
        ),
        (
            "docs/index.md",
            "**Predicción:** MAP@7 de",
            [coma(h2["map7"]["modelo"], 3), coma(h2["map7"]["referencia"], 3)],
        ),
    ]


def _ic(ic: list[float], d: int) -> str:
    return f"({coma(ic[0], d)} a {coma(ic[1], d)})".replace("-", "−")


def _n(x: float, d: int) -> str:
    v = coma(x, d)
    return v.replace("-", "−") if x < 0 else f"+{v}"


def comprobaciones_hito4() -> list[tuple[str, str, list[str]]]:
    est = _j("hito4/estimaciones.json")["analisis"]
    exp = _j("hito4/exploratorio.json")
    filas = {
        "nomina_actividad": ("| Iniciar la nómina -> activo en t+3 |", 3),
        "nomina_productos": ("| Iniciar la nómina -> otros productos |", 3),
        "canal_meses_activo": ("| Alta por KHM (frente a KHN) -> meses activo |", 2),
        "producto_recibo": ("| Débito automático -> inactivo en t+3 |", 4),
        "producto_tjcr": ("| Tarjeta de crédito -> inactivo en t+3 |", 4),
        "producto_ecue": ("| Cuenta electrónica -> inactivo en t+3 |", 4),
    }
    salida = []
    for k, (ancla, d) in filas.items():
        v = est[k]
        esperados = [_n(v["efecto"], d), _ic(v["ic95"], d), v["veredicto"]]
        if "placebo_adelanto" in v:
            esperados.append(_n(v["placebo_adelanto"]["efecto"], 3))
        salida.append(("docs/hito4.md", ancla, esperados))
    m = est["nomina_actividad"]["metodos"]
    salida.append(
        (
            "docs/hito4.md",
            "coinciden (emparejamiento",
            [
                coma(m["emparejamiento"]["efecto"], 3),
                coma(m["did_dr"]["efecto"], 3),
                coma(m["bosque_causal"]["efecto"], 3),
            ],
        )
    )
    salida.append(
        (
            "docs/hito4.md",
            "tres refutadores de DoWhy pasan. El ingenuo",
            [coma(m["ingenuo"]["efecto"], 3)],
        )
    )
    sin_cco = exp["otros_sin_cuenta_corriente_principal"]
    salida.append(
        (
            "docs/hito4.md",
            "cuenta corriente, el cambio es",
            [_n(sin_cco["efecto"], 3), _ic(sin_cco["ic95"], 3)],
        )
    )
    salida.append(
        (
            "docs/hito4.md",
            "(+0,075 sin ajuste); pero el placebo da",
            [_n(exp["otros_sin_cuenta_corriente_placebo_adelanto"]["efecto"], 3)],
        )
    )
    salida.append(("docs/hito4.md", "nómina. Con eso", []))
    c = est["canal_meses_activo"]
    salida.append(
        (
            "docs/hito4.md",
            "estuvieron activos **",
            [coma(abs(c["efecto"]), 2), coma(c["media_tratados"], 2)],
        )
    )
    salida.append(
        ("docs/hito4.md", "(valor de robustez", [coma(c["sensibilidad"]["valor_robustez_ic"], 3)])
    )
    return salida


def pct_signo(x: float) -> str:
    v = round(x * 100)
    return f"+{v} %" if v > 0 else (f"−{abs(v)} %" if v < 0 or x < 0 else "+0 %")


def comprobaciones_diagnostico_map() -> list[tuple[str, str, list[str]]]:
    dm = _j("hito2/diagnostico_map.json")
    h2 = _j("hito2/metricas.json")
    m = dm["map7"]
    filas = {
        "publicada": ("| Publicada: con alguna adquisición", 3),
        "24_productos": ("| Con alguna adquisición entre los 24", 3),
        "todos_los_clientes": ("| Todos los clientes-mes", 4),
        "nuevo_estricto": ('| "Nuevo estricto"', 3),
    }
    salida = []
    for k, (ancla, d) in filas.items():
        salida.append(
            (
                "docs/hito2.md",
                ancla,
                [
                    miles(m["modelo"][k]["clientes_mes"]),
                    *[
                        coma(m[q][k]["map7"], d)
                        for q in ("modelo", "referencia", "popularidad_global")
                    ],
                ],
            )
        )
    v = dm["frac_altas_que_vuelven_tras_tenerlo_en_t_menos_1"]
    pub = {q: m[q]["publicada"]["map7"] for q in ("modelo", "referencia")}
    tod = {q: m[q]["todos_los_clientes"]["map7"] for q in ("modelo", "referencia")}
    salida += [
        (
            "docs/hito2.md",
            "(45 % de las altas de nómina",
            [
                f"{round(v['nomina'] * 100)} %",
                f"{round(v['recibo'] * 100)} %",
                f"{round(v['tjcr'] * 100)} %",
            ],
        ),
        (
            "docs/hito2.md",
            "clientes-mes con adquisición se queda",
            [
                miles(m["modelo"]["publicada"]["clientes_mes"]),
                miles(m["modelo"]["nuevo_estricto"]["clientes_mes"]),
            ],
        ),
        ("docs/hito2.md", "no se compara con Kaggle", []),
        (
            "docs/hito2.md",
            "(+0,16 sobre la referencia",
            [
                f"+{coma(pub['modelo'] - pub['referencia'], 2)}",
                f"+{round((tod['modelo'] / tod['referencia'] - 1) * 100)} %",
            ],
        ),
        (
            "README.md",
            "MAP@7 de **",
            [coma(h2["map7"]["modelo"], 3), coma(h2["map7"]["referencia"], 3)],
        ),
        (
            "README.md",
            "sobre todos los clientes, como en Kaggle, **",
            [
                coma(m["modelo"]["todos_los_clientes"]["map7"], 4),
                coma(m["referencia"]["todos_los_clientes"]["map7"], 4),
            ],
        ),
        (
            "docs/index.md",
            "cada cliente que adquiere algo; sobre todos",
            [
                coma(m["modelo"]["todos_los_clientes"]["map7"], 4),
                coma(m["referencia"]["todos_los_clientes"]["map7"], 4),
            ],
        ),
    ]
    assert dm["mismo_modelo"]["todos"], "el diagnóstico no reprodujo el modelo congelado"
    assert dm["definicion"]["etiquetas_en_productos_ya_tenidos"] == 0
    return salida


def comprobaciones_hito3() -> list[tuple[str, str, list[str]]]:
    hs = _j("hito3/hillstrom.json")
    ss = _j("hito3/semisintetico.json")["escenarios"]
    comp = hs["experimento_completo"]
    salida = []
    for clave, ancla in (
        ("mujer_visit", "| Correo de mujer, visita |"),
        ("hombre_visit", "| Correo de hombre, visita |"),
    ):
        v = comp[clave]
        t = v["verdad_experimento"]
        salida.append(
            (
                "docs/hito3.md",
                ancla,
                [
                    f"{coma(t['efecto'], 4)} ({coma(t['ic95'][0], 4)} a {coma(t['ic95'][1], 4)})",
                    *[
                        coma(v["metodos"][m]["efecto"], 4)
                        for m in ("emparejamiento", "dml_att", "bosque_causal")
                    ],
                ],
            )
        )
    ses = hs["experimento_sesgado"]
    obj = ses["efecto_objetivo"]
    salida.append(
        (
            "docs/hito3.md",
            "tratados es **",
            [coma(obj["efecto"], 4), f"{coma(obj['ic95'][0], 4)} a {coma(obj['ic95'][1], 4)}"],
        )
    )
    nombres = {
        "ingenuo": "| Ingenuo |",
        "regresion": "| Regresión lineal |",
        "emparejamiento": "| Emparejamiento |",
        "dml_att": "| Double ML (ATT) | ",
        "bosque_causal": "| Bosque causal |",
    }
    for m, ancla in nombres.items():
        r = ses["metodos"][m]["resumen"]
        n = r["repeticiones"]
        salida.append(
            (
                "docs/hito3.md",
                ancla,
                [pct_signo(r["sesgo_relativo"]), f"{round(r['cobertura'] * n)} de {n}"],
            )
        )
    filas = {
        "ingenuo": "| Ingenuo | +",
        "dml_att": "| Double ML (ATT) | −",
        "dml_att_rezago": "| Double ML con resultados previos |",
        "did_dr": "| Diferencias en diferencias (DR) |",
        "bosque_causal": "| Bosque causal | +",
    }
    for m, ancla in filas.items():
        salida.append(
            (
                "docs/hito3.md",
                ancla,
                [
                    pct_signo(ss[e]["metodos"][m]["resumen"]["sesgo_relativo"])
                    for e in ("observables", "efecto_fijo", "tendencias")
                ],
            )
        )
    salida.append(
        (
            "docs/hito3.md",
            "los clientes por su efecto (correlación de",
            [coma(ss["observables"]["bosque_cate"]["correlacion_media"], 2)],
        )
    )
    pl = {e: round(ss[e]["placebo_did"]["rechaza_cero"] * 10) for e in ss}
    salida.append(
        (
            "docs/hito3.md",
            "(donde el efecto verdadero es cero) rechaza",
            [f"{pl['tendencias']} de 10", f"{pl['efecto_fijo']} de 10"],
        )
    )
    return salida


def comprobaciones_hito2() -> list[tuple[str, str, list[str]]]:
    h2 = _j("hito2/metricas.json")
    salida = []
    for p in ("cno", "nom_pens", "cco", "ecue", "nomina", "recibo", "tjcr"):
        r = h2["productos"][p]
        m, ref = r["modelo"], r["referencia"]
        salida.append(
            (
                "docs/hito2.md",
                f"| {r['nombre']} |",
                [
                    f"{coma(m['ap'], 3)} ({coma(m['ap_ic95'][0], 3)} a {coma(m['ap_ic95'][1], 3)})",
                    coma(ref["ap"], 3),
                    miles(m["positivos"]),
                ],
            )
        )
    salida += comprobaciones_diagnostico_map()
    return salida


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    fallas = []
    lista = comprobaciones()
    for archivo, ancla, esperados in lista:
        ruta = RAIZ / archivo if not archivo.startswith("docs/") else DOCS / archivo[5:]
        texto = ruta.read_text(encoding="utf-8").splitlines()
        posiciones = [i for i, x in enumerate(texto) if ancla in x]
        if not posiciones:
            fallas.append(f"{archivo}: no se encontró «{ancla}»")
            continue
        # la línea del ancla y la siguiente (las frases se cortan a 100 columnas); si el ancla
        # aparece varias veces, basta con que una de sus apariciones tenga todos los valores
        lineas = [" ".join(texto[i : i + 2]) for i in posiciones]
        if not any(all(e in linea for e in esperados) for linea in lineas):
            faltan = [e for e in esperados if e not in lineas[0]]
            fallas.append(f"{archivo}: «{ancla}» no tiene {faltan} -> {lineas[0]}")
    print(f"{len(lista)} comprobaciones, {len(fallas)} fallas")
    for x in fallas:
        print(" -", x)
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
