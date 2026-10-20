"""Mini-Santander sintético: el mismo formato del CSV real, con sus trampas, para pruebas y CI.

Genera un panel mensual (enero de 2015 a mayo de 2016) con clientes que entran durante el
panel, actividad que depende de la tenencia, inicios de nómina y altas de productos. Las
reglas no pretenden parecerse a Santander: solo sirven para que el código corra sin los
datos reales. Reproduce los formatos del original: espacios a la izquierda en ``age`` y
``antiguedad``, ``NA``, ``-999999``, ``indrel_1mes`` con ``1`` y ``1.0``, provincias con eñe.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from causal.ingesta import COLUMNAS_CSV, PRODUCTOS

MESES = pd.date_range("2015-01-01", periods=17, freq="MS") + pd.Timedelta(days=27)
CANALES = ("KHE", "KAT", "KFC", "KHQ", "RED")
PROVINCIAS = ((28, "MADRID"), (8, "BARCELONA"), (15, "CORUÑA, A"), (46, "VALENCIA"))
SEGMENTOS = ("01 - TOP", "02 - PARTICULARES", "03 - UNIVERSITARIO")


@dataclass
class MiniSantander:
    ruta: Path
    clientes: int
    filas: int


def generar(ruta: Path, clientes: int = 400, semilla: int = 11) -> MiniSantander:
    """Escribe el CSV sintético en ``ruta`` y devuelve su resumen."""
    rng = np.random.default_rng(semilla)
    codigos = list(PRODUCTOS)
    filas: list[list[str]] = []
    for i in range(clientes):
        cod = 1_000_000 + i
        canal = CANALES[rng.integers(len(CANALES))]
        edad0 = int(rng.integers(18, 80)) if canal != "KHE" else int(rng.integers(19, 26))
        sexo = "H" if rng.random() < 0.45 else "V"
        cod_prov, prov = PROVINCIAS[rng.integers(len(PROVINCIAS))]
        segmento = SEGMENTOS[2] if edad0 < 25 else SEGMENTOS[int(rng.random() < 0.9) + 0]
        renta = rng.lognormal(11.5, 0.5)
        alta_mes = int(rng.integers(-60, 14))  # meses respecto de enero de 2015
        alta = (pd.Timestamp("2015-01-01") + pd.DateOffset(months=alta_mes)).normalize()
        alta = alta + pd.Timedelta(days=int(rng.integers(0, 27)))
        tiene = {c: 0 for c in codigos}
        tiene["cco"] = 1
        inicio_nomina = int(rng.integers(3, 30))  # mes del panel en que trae la nómina
        afinidad = rng.normal()
        sale = int(rng.integers(8, 40))  # mes en que abandona el panel
        for t, fecha in enumerate(MESES):
            if fecha < alta or t >= sale:
                continue
            if t == inicio_nomina:
                tiene["nomina"] = tiene["nom_pens"] = 1
                tiene["cno"] = 1
            for c in ("recibo", "tjcr", "ecue", "dela", "reca"):
                p = 0.02 + 0.03 * tiene["nomina"] + 0.01 * (afinidad > 0)
                if not tiene[c] and rng.random() < p:
                    tiene[c] = 1
                elif tiene[c] and rng.random() < 0.03:
                    tiene[c] = 0
            n_prod = sum(tiene.values())
            logit = -1.0 + 0.6 * n_prod + 0.8 * afinidad + 0.7 * tiene["nomina"]
            activo = int(rng.random() < 1 / (1 + np.exp(-logit)))
            antig = (fecha.year - alta.year) * 12 + fecha.month - alta.month
            edad = edad0 + (t // 12)
            vacia = rng.random() < 0.01 and t < 6  # filas de los primeros meses sin demografía
            antig_txt = "-999999" if rng.random() < 0.005 else f"{antig:>7d}"
            fila = {
                "fecha_dato": fecha.strftime("%Y-%m-%d"),
                "ncodpers": f"{cod:>7d}",
                "ind_empleado": "N",
                "pais_residencia": "ES",
                "sexo": sexo,
                "age": f"{edad:>3d}",
                "fecha_alta": alta.strftime("%Y-%m-%d"),
                "ind_nuevo": " 1" if antig < 6 else " 0",
                "antiguedad": antig_txt,
                "indrel": " 1",
                "ult_fec_cli_1t": "",
                "indrel_1mes": "1.0" if t < 6 else "1",
                "tiprel_1mes": "A" if activo else "I",
                "indresi": "S",
                "indext": "N",
                "conyuemp": "",
                "canal_entrada": canal,
                "indfall": "N",
                "tipodom": " 1",
                "cod_prov": f"{cod_prov:>2d}",
                "nomprov": prov,
                "ind_actividad_cliente": f" {activo}",
                "renta": "" if rng.random() < 0.2 else f"{renta:.2f}",
                "segmento": segmento,
            }
            if vacia:
                for k in ("ind_empleado", "pais_residencia", "sexo", "fecha_alta", "indresi"):
                    fila[k] = ""
                fila["age"] = fila["antiguedad"] = fila["ind_nuevo"] = "NA"
                fila["ind_actividad_cliente"] = fila["indrel"] = "NA"
            for corto, (col, _) in PRODUCTOS.items():
                v = tiene[corto]
                fila[col] = f" {v}" if corto in ("nomina", "nom_pens") else str(v)
            filas.append([fila[c] for c in COLUMNAS_CSV])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writerow(COLUMNAS_CSV)
        w.writerows(filas)
    return MiniSantander(ruta=ruta, clientes=clientes, filas=len(filas))
