"""La página interactiva calcula lo mismo que Python (motor.js con Node) y lee JSON válidos."""

import json
import shutil
import subprocess

import pytest

from causal import demo
from causal.rutas import DOCS, DOCS_RESULTADOS
from causal.util import leer_json

MOTOR = DOCS / "demo" / "motor.js"
CELDAS = DOCS_RESULTADOS / "demo" / "hillstrom_celdas.json"


def _node(codigo: str) -> object:
    if shutil.which("node") is None:
        pytest.skip("sin Node.js")
    r = subprocess.run(
        ["node", "-e", codigo], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(r.stdout)


def test_valor_politica_igual_que_python() -> None:
    datos = leer_json(CELDAS)
    for costo in (0.0, 0.05, 0.12):
        js = _node(
            f"const M=require({json.dumps(str(MOTOR))});"
            f"const d=require({json.dumps(str(CELDAS))});"
            "const r={};for(const k in d.estrategias){"
            f"r[k]=M.valorPolitica(d.celdas,d.estrategias[k],{costo});}}"
            "console.log(JSON.stringify(r));"
        )
        for k, asig in datos["estrategias"].items():
            py = demo.valor(datos["celdas"], asig, costo)
            assert abs(js[k]["valor"] - py["valor"]) < 1e-12
            assert abs(js[k]["ee"] - py["ee"]) < 1e-12


def test_verificacion_publicada_y_arbol_coherente() -> None:
    datos = leer_json(CELDAS)
    assert datos["celdas_con_accion_mixta"] == 0
    for k, v in datos["verificacion"].items():
        py = demo.valor(datos["celdas"], datos["estrategias"][k], datos["costo_hito5"])
        assert abs(py["valor"] - v["valor"]) < 1e-12
    # el valor por estratos del árbol queda cerca del valor ponderado publicado en el hito 5
    h5 = leer_json(DOCS_RESULTADOS / "hito5" / "heterogeneidad.json")["hillstrom"]["politica"]
    for k in ("arbol", "todos_hombre", "todos_mujer", "nadie"):
        assert abs(datos["verificacion"][k]["valor"] - h5["valor_neto_prueba"][k]["valor"]) < 0.005


def test_formato_y_placebo() -> None:
    r = _node(
        f"const M=require({json.dumps(str(MOTOR))});"
        "console.log(JSON.stringify([M.coma(-0.0326,3),M.pp(0.0889),M.miles(64000),"
        "M.fraccionPlacebo({efecto:0.0889,placebo_adelanto:{efecto:0.0583}})]));"
    )
    assert r[:3] == ["−0,033", "+8,9 pp", "64.000"]
    assert abs(r[3] - 0.0583 / 0.0889) < 1e-12
