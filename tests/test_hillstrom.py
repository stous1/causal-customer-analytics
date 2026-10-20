"""Hillstrom: verdad del experimento y del experimento sesgado (datos simulados)."""

import numpy as np
import pandas as pd

from causal import hillstrom


def _falso(n: int = 20000) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    df = pd.DataFrame(
        {
            "recency": rng.integers(1, 13, n),
            "history": rng.lognormal(5, 1, n),
            "mens": rng.integers(0, 2, n),
            "womens": rng.integers(0, 2, n),
            "zip_code": rng.choice(["Urban", "Rural", "Surburban"], n),
            "newbie": rng.integers(0, 2, n),
            "channel": rng.choice(["Web", "Phone", "Multichannel"], n),
            "segment": rng.choice(["Womens E-Mail", "Mens E-Mail", "No E-Mail"], n),
        }
    )
    d = (df.segment != "No E-Mail").astype(int)
    df["visit"] = (rng.random(n) < 0.1 + 0.05 * d).astype(int)
    df["conversion"] = 0
    df["spend"] = 0.0
    return df


def test_efecto_y_sesgo() -> None:
    datos = hillstrom.brazo(_falso(), "mujer")
    X = hillstrom.covariables(datos)
    verdad = hillstrom.efecto_experimento(datos, "visit")
    assert abs(verdad["efecto"] - 0.05) < 0.02
    objetivo = hillstrom.efecto_objetivo_sesgado(datos, X, "visit")
    assert abs(objetivo["efecto"] - 0.05) < 0.02  # efecto constante: mismo ATT
    idx = hillstrom.sesgar(datos, X, semilla=1)
    quedan = datos.iloc[idx]
    assert (quedan.d == 0).sum() == (datos.d == 0).sum()
    assert (quedan.d == 1).sum() < (datos.d == 1).sum()
