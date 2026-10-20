<div align="center">

# Analítica de clientes causal y explicable

**¿Quién va a adquirir un producto, y a quién le cambia el resultado una acción?** Dos
preguntas que suelen confundirse, separadas sobre el panel de Santander (957 mil clientes,
17 meses) y validadas en un experimento real (Hillstrom).

[![CI](https://github.com/stous1/causal-customer-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/stous1/causal-customer-analytics/actions/workflows/ci.yml)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-sitio-2ea44f?logo=github)](https://stous1.github.io/causal-customer-analytics/)
[![Python 3.12](https://img.shields.io/badge/python-3.12-3776ab?logo=python&logoColor=white)](.python-version)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-blue)](LICENSE)

**[Sitio](https://stous1.github.io/causal-customer-analytics/)** ·
**[Preregistro](docs/preregistro.md)** ·
**[Resumen para agentes (JSON)](docs/resultados/resumen.json)**

</div>

## En un minuto

**El problema.** Un modelo que predice muy bien quién va a contratar un producto no dice qué
pasa si se lo ofrecen. Si los clientes activos son los que contratan, "el producto vuelve
activo al cliente" puede ser falso aunque el modelo acierte.

**Qué se construyó.** Un sistema local en DuckDB con dos capas:

1. **Predicción** (LightGBM, partición temporal, congelado antes de la prueba): propensión a
   adquirir 13 productos nuevos el mes siguiente. MAP@7 de **0,856** contra 0,700 de una
   referencia por segmento, edad y actividad, promediado sobre los clientes que adquieren algo;
   sobre todos los clientes, como en Kaggle, **0,0251 contra 0,0205**
   ([qué mide](docs/hito2.md#qué-mide-el-map7-y-por-qué-0856-no-se-compara-con-kaggle)).
2. **Causalidad**: tres preguntas **preregistradas con tag antes de estimar**, emuladas como
   ensayos mes a mes, con Double ML, emparejamiento, diferencias en diferencias y bosques
   causales; refutaciones de DoWhy, placebo de adelanto y sensibilidad a confusores omitidos.
   Los métodos se validaron antes donde la respuesta se conoce: en Hillstrom sesgado el
   ingenuo se equivoca 43 % y Double ML 0 %.

**Resultados en Santander** (efecto en los tratados, a 3 meses):

| Pregunta | Efecto (IC 95 %) | Veredicto |
|---|---|---|
| ¿La nómina vuelve más activo al cliente? | +8,9 pp (8,3 a 9,5) | **no separable de la selección**: quienes la traerán en 4 meses ya están 5,8 pp más activos antes |
| ¿El canal de vinculación cambia cuánto dura activo? | KHM: −0,38 meses de 6 frente a KHN | **creíble** (pasa todas las pruebas aplicables) |
| ¿Qué productos frenan el paso a inactivo? | débito, tarjeta, cuenta electrónica | **ninguno con credibilidad**: sin efecto o falla el placebo |

**Lo que predice no es lo que causa.** La actividad es lo que más predice que un cliente
adquiera un producto; adquirirlo no causa de forma creíble más actividad. Y los clientes con
más probabilidad de adquirir la tarjeta o la cuenta electrónica son aquellos en quienes su
efecto estimado es **menor**.

## Qué se puede ver

| Página | Qué muestra |
|---|---|
| [Hito 1](https://stous1.github.io/causal-customer-analytics/hito1.html) | Datos, calidad (la actividad congelada en enero-julio de 2015) y diseños |
| [Hito 2](https://stous1.github.io/causal-customer-analytics/hito2.html) | Capa predictiva y lo que predice (SHAP, no causal) |
| [Hito 3](https://stous1.github.io/causal-customer-analytics/hito3.html) | Validación de métodos en Hillstrom y en el semisintético |
| [Preregistro](docs/preregistro.md) | Preguntas, DAG, ventanas, métodos y criterios, antes de estimar |
| [Hito 4](https://stous1.github.io/causal-customer-analytics/hito4.html) | Efectos causales en Santander y sus refutaciones |
| [Hito 5](https://stous1.github.io/causal-customer-analytics/hito5.html) | Efectos heterogéneos, SHAP sobre el efecto y árboles de política |
| [Bitácora](TRABAJO_NOCTURNO.md) | Decisiones tomadas y su justificación |

## Cómo se evalúa

- **Predicción:** partición temporal; todo se elige en validación y se congela con el tag
  `hito2-congelado`; la prueba (abril y mayo de 2016) se mide una vez. Nunca exactitud.
- **Causalidad:** sin verdad en Santander, la credibilidad se construye así:
  1. métodos validados en Hillstrom y en un semisintético sobre covariables reales;
  2. preregistro (tag `preregistro`) con huellas SHA-256 del código;
  3. en Santander, placebo de adelanto, refutaciones de DoWhy, consistencia entre métodos,
     valor de robustez y corrección de Holm.
- Los SHAP predictivos se publican marcados como **predictivos**; los SHAP sobre el efecto,
  como causales condicionados al veredicto de su pregunta.

## Lo que hay que saber

- **Los datos tienen trampas.** De enero a julio de 2015 la demografía y la actividad son una
  copia de julio; en julio entran 193 mil clientes que ya existían; el canal y el segmento se
  registran un mes tarde. Todo eso cambió el diseño.
- **La actividad no tiene definición pública** y puede contar mecánicamente el abono de la
  nómina o los movimientos de un débito o una tarjeta.
- **Observacional es observacional:** "creíble" quiere decir que pasó las pruebas
  preregistradas, no que esté demostrado.

## Uso

```bash
uv sync
uv run pytest -m "not integracion"
uv run python scripts/hito1.py preparar   # requiere data/raw/train_ver2.csv (Kaggle)
```

Todos los comandos, en [CLAUDE.md](CLAUDE.md). Trabajo futuro: un agente que interprete
[`docs/resultados/resumen.json`](docs/resultados/resumen.json) sin confundir predicción con
causa.
