"""Estimadores causales con una salida común.

Todos reciben covariables ``X`` (DataFrame numérico, puede tener NaN), tratamiento binario
``d`` y resultado ``y`` (y, para diferencias en diferencias, el resultado previo ``y_pre``),
y devuelven un ``Estimacion`` con efecto, error estándar e intervalo de 95 %.

Estimando por defecto: **efecto en los tratados (ATT)**. En un experimento aleatorizado el
ATT y el efecto promedio (ATE) coinciden en esperanza.

- ``ingenuo``: diferencia de medias, sin ajuste (la referencia de lo que sale mal).
- ``regresion``: MCO de ``y`` sobre ``d`` y ``X`` (ajuste lineal).
- ``emparejamiento``: puntaje de propensión (regresión logística), vecino más cercano 1:1
  con reemplazo y caliper de 0,2 desviaciones del logit; error por bootstrap de pares.
- ``dml_att``: Double ML de modelo interactivo (IRM) con la función de puntaje del ATT,
  ajuste cruzado y LightGBM para las funciones auxiliares (Chernozhukov et al., 2018).
- ``did_dr``: diferencias en diferencias doble robusto para panel: el mismo puntaje del ATT
  sobre ``y - y_pre`` (Sant'Anna y Zhao, 2020). Supone tendencias paralelas condicionales.
- ``bosque_causal``: ``CausalForestDML`` de EconML; ATT = promedio del efecto condicional en
  los tratados, con el intervalo de EconML (conservador: más ancho que el real).
"""

from dataclasses import asdict, dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

Z = float(stats.norm.ppf(0.975))
RECORTE = 0.01  # propensiones recortadas a [0,01; 0,99]


@dataclass
class Estimacion:
    metodo: str
    estimando: str
    efecto: float
    ee: float
    ic95: tuple[float, float]
    n: int
    n_tratados: int
    extra: dict = field(default_factory=dict)

    def como_dict(self) -> dict:
        d = asdict(self)
        d["ic95"] = list(self.ic95)
        return d


def _est(
    metodo: str, efecto: float, ee: float, d: np.ndarray, estimando: str = "ATT", **extra
) -> Estimacion:
    return Estimacion(
        metodo=metodo,
        estimando=estimando,
        efecto=float(efecto),
        ee=float(ee),
        ic95=(float(efecto - Z * ee), float(efecto + Z * ee)),
        n=int(len(d)),
        n_tratados=int(d.sum()),
        extra=extra,
    )


def ingenuo(X: pd.DataFrame, d: np.ndarray, y: np.ndarray) -> Estimacion:
    y1, y0 = y[d == 1], y[d == 0]
    ee = np.sqrt(y1.var(ddof=1) / len(y1) + y0.var(ddof=1) / len(y0))
    return _est("ingenuo", y1.mean() - y0.mean(), ee, d, estimando="diferencia de medias")


def _matriz(X: pd.DataFrame) -> np.ndarray:
    """Imputación por mediana más indicadores de faltante, como matriz float."""
    A = X.to_numpy(dtype=float)
    falt = np.isnan(A)
    cols_falt = falt.any(axis=0)
    med = np.nanmedian(np.where(falt, np.nan, A), axis=0)
    med = np.where(np.isnan(med), 0.0, med)
    A = np.where(falt, med, A)
    return np.hstack([A, falt[:, cols_falt].astype(float)])


def regresion(X: pd.DataFrame, d: np.ndarray, y: np.ndarray) -> Estimacion:
    """MCO con errores robustos (HC1). Estima un efecto constante."""
    import statsmodels.api as sm

    A = _matriz(X)
    A = A[:, A.std(axis=0) > 0]
    M = sm.add_constant(np.column_stack([d.astype(float), A]), has_constant="add")
    r = sm.OLS(y.astype(float), M).fit(cov_type="HC1")
    return _est("regresion", r.params[1], r.bse[1], d, estimando="efecto constante (MCO)")


def propension_logistica(X: pd.DataFrame, d: np.ndarray) -> np.ndarray:
    modelo = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
        StandardScaler(),
        LogisticRegression(C=1.0, max_iter=2000),
    )
    modelo.fit(X, d)
    return modelo.predict_proba(X)[:, 1]


def diferencias_estandarizadas(
    X: pd.DataFrame, d: np.ndarray, w0: np.ndarray | None = None
) -> pd.Series:
    """Diferencia de medias estandarizada por covariable (controles ponderados por ``w0``)."""
    A = X.astype(float)
    t, c = A[d == 1], A[d == 0]
    w = np.ones(len(c)) if w0 is None else w0
    m1 = t.mean()
    m0 = (c.mul(w, axis=0)).sum() / w.sum()
    sd = np.sqrt((t.var() + c.var()) / 2).replace(0, np.nan)
    return ((m1 - m0) / sd).fillna(0.0)


def parejas(
    X: pd.DataFrame, d: np.ndarray, caliper: float = 0.2
) -> tuple[np.ndarray, np.ndarray, float]:
    """Índices de tratados emparejados y de su control (vecino más cercano en el logit de la
    propensión, con reemplazo y caliper), y la fracción de tratados emparejados."""
    ps = np.clip(propension_logistica(X, d), 1e-6, 1 - 1e-6)
    lg = np.log(ps / (1 - ps))
    i1, i0 = np.flatnonzero(d == 1), np.flatnonzero(d == 0)
    orden = np.argsort(lg[i0], kind="stable")
    l0 = lg[i0][orden]
    pos = np.clip(np.searchsorted(l0, lg[i1]), 1, len(l0) - 1)
    izq, der = l0[pos - 1], l0[pos]
    j = np.where(np.abs(lg[i1] - izq) <= np.abs(der - lg[i1]), pos - 1, pos)
    dentro = np.abs(lg[i1] - l0[j]) <= caliper * lg.std()
    return i1[dentro], i0[orden][j[dentro]], float(dentro.mean())


def emparejamiento(
    X: pd.DataFrame,
    d: np.ndarray,
    y: np.ndarray,
    caliper: float = 0.2,
    reps: int = 200,
    semilla: int = 0,
) -> Estimacion:
    """ATT por vecino más cercano en el logit de la propensión, con reemplazo."""
    t_idx, c_idx, frac = parejas(X, d, caliper)
    i0 = np.flatnonzero(d == 0)
    dif = y[t_idx] - y[c_idx]
    rng = np.random.default_rng(semilla)
    boot = [dif[rng.integers(0, len(dif), len(dif))].mean() for _ in range(reps)]
    # balance antes y después
    pesos = np.bincount(np.searchsorted(i0, c_idx), minlength=len(i0)).astype(float)
    smd_antes = diferencias_estandarizadas(X, d)
    Xm = pd.concat([X.iloc[t_idx], X.iloc[i0]], ignore_index=True)
    dm = np.r_[np.ones(len(t_idx)), np.zeros(len(i0))]
    smd_despues = diferencias_estandarizadas(Xm, dm, w0=pesos + 1e-12)
    return _est(
        "emparejamiento",
        dif.mean(),
        np.std(boot, ddof=1),
        d,
        tratados_emparejados=frac,
        smd_max_antes=float(smd_antes.abs().max()),
        smd_max_despues=float(smd_despues.abs().max()),
        controles_distintos=int((pesos > 0).sum()),
    )


def _lgb_params(semilla: int) -> dict:
    return {
        "n_estimators": 300,
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_child_samples": 50,
        "subsample": 0.8,
        "subsample_freq": 1,
        "colsample_bytree": 0.8,
        "reg_lambda": 1.0,
        "random_state": semilla,
        "deterministic": True,
        "force_col_wise": True,
        "n_jobs": 8,
        "verbose": -1,
    }


def auxiliares_cruzadas(
    X: pd.DataFrame, d: np.ndarray, y: np.ndarray, pliegues: int = 3, semilla: int = 0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Predicciones fuera de pliegue de P(D=1|X), E[Y|D=0,X] y E[Y|D=1,X] (LightGBM)."""
    m = np.zeros(len(d))
    g0 = np.zeros(len(d))
    g1 = np.zeros(len(d))
    binario = set(np.unique(y)) <= {0.0, 1.0}
    kf = StratifiedKFold(pliegues, shuffle=True, random_state=semilla)
    for k, (a, b) in enumerate(kf.split(X, d)):
        clf = lgb.LGBMClassifier(**_lgb_params(semilla + k))
        clf.fit(X.iloc[a], d[a])
        m[b] = clf.predict_proba(X.iloc[b])[:, 1]
        for brazo, destino in ((0, g0), (1, g1)):
            sel = a[d[a] == brazo]
            if binario:
                reg = lgb.LGBMClassifier(**_lgb_params(semilla + 10 + k))
                reg.fit(X.iloc[sel], y[sel].astype(int))
                destino[b] = reg.predict_proba(X.iloc[b])[:, 1]
            else:
                reg = lgb.LGBMRegressor(**_lgb_params(semilla + 10 + k))
                reg.fit(X.iloc[sel], y[sel])
                destino[b] = reg.predict(X.iloc[b])
    return np.clip(m, RECORTE, 1 - RECORTE), g0, g1


def _att_irm(d: np.ndarray, y: np.ndarray, m: np.ndarray, g0: np.ndarray) -> tuple[float, float]:
    """Puntaje ortogonal del ATT y su error estándar por función de influencia."""
    p = d.mean()
    r = y - g0
    a = d * r - (1 - d) * m / (1 - m) * r
    theta = a.mean() / p
    psi = (a - d * theta) / p
    return float(theta), float(psi.std(ddof=1) / np.sqrt(len(d)))


def dml_att(
    X: pd.DataFrame, d: np.ndarray, y: np.ndarray, pliegues: int = 3, semilla: int = 0
) -> Estimacion:
    m, g0, g1 = auxiliares_cruzadas(X, d, y, pliegues, semilla)
    theta, ee = _att_irm(d, y, m, g0)
    # efecto promedio (ATE) con el puntaje AIPW, como dato adicional
    psi_ate = g1 - g0 + d * (y - g1) / m - (1 - d) * (y - g0) / (1 - m)
    return _est(
        "dml_att",
        theta,
        ee,
        d,
        ate=float(psi_ate.mean()),
        ate_ee=float(psi_ate.std(ddof=1) / np.sqrt(len(d))),
        propension_min_tratados=float(m[d == 1].min()),
        propension_max_controles=float(m[d == 0].max()),
        frac_recortada=float(((m <= RECORTE) | (m >= 1 - RECORTE)).mean()),
    )


def did_dr(
    X: pd.DataFrame,
    d: np.ndarray,
    y: np.ndarray,
    y_pre: np.ndarray,
    pliegues: int = 3,
    semilla: int = 0,
) -> Estimacion:
    """ATT por diferencias en diferencias doble robusto (puntaje del ATT sobre el cambio)."""
    cambio = y - y_pre
    m, g0, _ = auxiliares_cruzadas(X, d, cambio, pliegues, semilla)
    theta, ee = _att_irm(d, cambio, m, g0)
    ingenua = cambio[d == 1].mean() - cambio[d == 0].mean()
    return _est("did_dr", theta, ee, d, did_sin_ajuste=float(ingenua))


def bosque_causal(
    X: pd.DataFrame,
    d: np.ndarray,
    y: np.ndarray,
    semilla: int = 0,
    arboles: int = 400,
    devolver_modelo: bool = False,
) -> Estimacion | tuple[Estimacion, object]:
    """``CausalForestDML`` con auxiliares LightGBM; ATT = promedio del CATE en los tratados."""
    from econml.dml import CausalForestDML

    binario = set(np.unique(y)) <= {0.0, 1.0}
    params = _lgb_params(semilla)
    modelo_y = lgb.LGBMRegressor(**params)
    cf = CausalForestDML(
        model_y=modelo_y,
        model_t=lgb.LGBMClassifier(**params),
        discrete_treatment=True,
        n_estimators=arboles,
        min_samples_leaf=20,
        max_samples=0.45,
        cv=3,
        random_state=semilla,
        n_jobs=8,
    )
    Xa = _matriz(X)
    cf.fit(y.astype(float), d.astype(int), X=Xa)
    # ATT = promedio del efecto condicional en los tratados. Su IC (ate_inference) es una cota
    # conservadora: promedia los errores individuales. El ATT doble robusto del bosque (att_)
    # resultó más ruidoso en simulaciones y se guarda solo como dato.
    cate_t = cf.effect(Xa[d == 1])
    inf = cf.ate_inference(X=Xa[d == 1])
    lo, hi = inf.conf_int_mean(alpha=0.05)
    est = Estimacion(
        metodo="bosque_causal",
        estimando="ATT",
        efecto=float(np.mean(cate_t)),
        ee=float(inf.stderr_mean),
        ic95=(float(np.ravel(lo)[0]), float(np.ravel(hi)[0])),
        n=int(len(d)),
        n_tratados=int(d.sum()),
        extra={
            "resultado_binario": binario,
            "cate_sd_tratados": float(np.std(cate_t)),
            "att_dr": float(np.ravel(cf.att_(T=1))[0]),
            "att_dr_ee": float(np.ravel(cf.att_stderr_(T=1))[0]),
            "ic_conservador": True,
        },
    )
    return (est, cf) if devolver_modelo else est


def matriz_bosque(X: pd.DataFrame) -> np.ndarray:
    """La misma matriz que recibe el bosque (para predecir efectos condicionales después)."""
    return _matriz(X)


def todos(
    X: pd.DataFrame,
    d: np.ndarray,
    y: np.ndarray,
    y_pre: np.ndarray | None = None,
    semilla: int = 0,
    con_bosque: bool = True,
) -> dict[str, Estimacion]:
    """Corre todos los estimadores aplicables."""
    res = {
        "ingenuo": ingenuo(X, d, y),
        "regresion": regresion(X, d, y),
        "emparejamiento": emparejamiento(X, d, y, semilla=semilla),
        "dml_att": dml_att(X, d, y, semilla=semilla),
    }
    if y_pre is not None:
        res["did_dr"] = did_dr(X, d, y, y_pre, semilla=semilla)
    if con_bosque:
        res["bosque_causal"] = bosque_causal(X, d, y, semilla=semilla)
    return res
