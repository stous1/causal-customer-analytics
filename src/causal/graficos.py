"""Gráficos con Altair, guardados en HTML y PNG (vl-convert)."""

from pathlib import Path

import altair as alt
import pandas as pd

AZUL = "#2f6db5"
NARANJA = "#d9822b"
GRIS = "#8a8f98"
VERDE = "#2e9e6b"
ROJO = "#c8453b"
PALETA = [AZUL, NARANJA, VERDE, ROJO, "#7b5ea7", GRIS, "#3aa6b9", "#b5892f"]

alt.data_transformers.disable_max_rows()


def guardar(grafico: alt.TopLevelMixin, ruta_sin_ext: Path) -> None:
    """Escribe ``.html`` y ``.png`` (escala 2) del gráfico."""
    ruta_sin_ext.parent.mkdir(parents=True, exist_ok=True)
    grafico.save(str(ruta_sin_ext.with_suffix(".html")))
    grafico.save(str(ruta_sin_ext.with_suffix(".png")), scale_factor=2)


def lineas(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    titulo: str = "",
    eje_x: str = "",
    eje_y: str = "",
    formato_y: str = "",
    ancho: int = 560,
    alto: int = 260,
    sombra: tuple[float, float] | None = None,
) -> alt.Chart:
    """Líneas con puntos; ``sombra`` marca un intervalo del eje x (p. ej., meses congelados)."""
    enc = {
        "x": alt.X(
            f"{x}:Q" if df[x].dtype.kind in "if" else f"{x}:T",
            title=eje_x,
            scale=alt.Scale(nice=False, zero=False),
        ),
        "y": alt.Y(
            f"{y}:Q", title=eje_y, axis=alt.Axis(format=formato_y) if formato_y else alt.Axis()
        ),
    }
    if color:
        enc["color"] = alt.Color(f"{color}:N", title=None, scale=alt.Scale(range=PALETA))
    base = alt.Chart(df).mark_line(point=True).encode(**enc)
    capas = [base]
    if sombra is not None:
        caja = pd.DataFrame({"a": [sombra[0]], "b": [sombra[1]]})
        capas.insert(
            0,
            alt.Chart(caja).mark_rect(opacity=0.12, color=GRIS).encode(x=alt.X("a:Q"), x2="b:Q"),
        )
    return alt.layer(*capas).properties(title=titulo, width=ancho, height=alto)


def barras_h(
    df: pd.DataFrame,
    x: str,
    y: str,
    titulo: str = "",
    eje_x: str = "",
    color: str | None = None,
    formato_x: str = "",
    ancho: int = 480,
) -> alt.Chart:
    """Barras horizontales ordenadas por valor."""
    enc = {
        "x": alt.X(
            f"{x}:Q", title=eje_x, axis=alt.Axis(format=formato_x) if formato_x else alt.Axis()
        ),
        "y": alt.Y(f"{y}:N", sort="-x", title=None),
    }
    if color:
        enc["color"] = alt.Color(f"{color}:N", title=None, scale=alt.Scale(range=PALETA))
    alto = max(120, 18 * df[y].nunique())
    return alt.Chart(df).mark_bar().encode(**enc).properties(title=titulo, width=ancho, height=alto)


def intervalos(
    df: pd.DataFrame,
    y: str,
    est: str,
    inf: str,
    sup: str,
    color: str | None = None,
    titulo: str = "",
    eje_x: str = "",
    referencia: float | None = 0.0,
    ancho: int = 480,
    fila: str | None = None,
) -> alt.Chart:
    """Estimaciones puntuales con intervalos de confianza (gráfico de bosque)."""
    enc_y = alt.Y(f"{y}:N", title=None, sort=None)
    col = (
        alt.Color(f"{color}:N", title=None, scale=alt.Scale(range=PALETA))
        if color
        else alt.value(AZUL)
    )
    barras = (
        alt.Chart(df)
        .mark_rule(strokeWidth=2)
        .encode(y=enc_y, x=alt.X(f"{inf}:Q", title=eje_x), x2=f"{sup}:Q", color=col)
    )
    puntos = alt.Chart(df).mark_point(filled=True, size=60).encode(y=enc_y, x=f"{est}:Q", color=col)
    capas = [barras, puntos]
    if referencia is not None:
        capas.insert(
            0,
            alt.Chart(pd.DataFrame({"r": [referencia]}))
            .mark_rule(color=GRIS, strokeDash=[4, 3])
            .encode(x="r:Q"),
        )
    if fila:
        # un panel por valor de ``fila`` (facet no filtra bien capas con datos propios)
        paneles = [
            intervalos(
                df[df[fila] == v],
                y,
                est,
                inf,
                sup,
                color=color,
                titulo=str(v),
                eje_x=eje_x,
                referencia=referencia,
                ancho=ancho,
            )
            for v in dict.fromkeys(df[fila])
        ]
        return alt.vconcat(*paneles).properties(title=titulo)
    alto = max(100, 22 * df[y].nunique())
    g = alt.layer(*capas, data=df).properties(width=ancho, height=alto)
    return g.properties(title=titulo)
