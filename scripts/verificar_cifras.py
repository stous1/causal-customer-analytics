"""Contrasta las cifras del README y de las páginas de Pages con los JSON publicados.

Uso:
    uv run python scripts/verificar_cifras.py   # sale con código 1 si algo no coincide

Cada comprobación busca la línea de un documento que contiene un texto (la fila de una tabla
o una frase) y exige que aparezcan en ella (o en la línea siguiente) los valores sacados de
``docs/resultados``, formateados como en el texto (coma decimal, punto de miles).
"""

import sys

from causal.rutas import DOCS, DOCS_RESULTADOS, RAIZ
from causal.util import leer_json, miles


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
    return salida


def main() -> int:
    fallas = []
    lista = comprobaciones()
    for archivo, ancla, esperados in lista:
        ruta = RAIZ / archivo if not archivo.startswith("docs/") else DOCS / archivo[5:]
        texto = ruta.read_text(encoding="utf-8").splitlines()
        posiciones = [i for i, x in enumerate(texto) if ancla in x]
        if not posiciones:
            fallas.append(f"{archivo}: no se encontró «{ancla}»")
            continue
        linea = " ".join(texto[posiciones[0] : posiciones[0] + 2])
        faltan = [e for e in esperados if e not in linea]
        if faltan:
            fallas.append(f"{archivo}: «{ancla}» no tiene {faltan}\n    {linea}")
    print(f"{len(lista)} comprobaciones, {len(fallas)} fallas")
    for x in fallas:
        print(" -", x)
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
