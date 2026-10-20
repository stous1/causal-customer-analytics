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
    return salida


def pct_signo(x: float) -> str:
    v = round(x * 100)
    return f"+{v} %" if v > 0 else (f"−{abs(v)} %" if v < 0 or x < 0 else "+0 %")


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
    salida.append(
        (
            "docs/hito2.md",
            "**MAP@7:**",
            [
                coma(h2["map7"]["modelo"], 3),
                coma(h2["map7"]["referencia"], 3),
                miles(h2["map7"]["clientes"]),
            ],
        )
    )
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
