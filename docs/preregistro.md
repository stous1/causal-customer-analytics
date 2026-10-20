# Preregistro de las preguntas causales

[← Volver a la portada](index.md) ·
[JSON con huellas SHA-256](resultados/preregistro.json)

Escrito **antes de estimar cualquier efecto en Santander** y fijado con el tag `preregistro`.
Lo único que se miró de Santander antes de este documento son conteos, faltantes y la
distribución de la propensión (que no usa resultados). Los métodos se eligieron con
Hillstrom y con el semisintético ([hito 3](hito3.md)).

## Preguntas, tratamientos y resultados

Todas se arman como una **emulación de ensayo objetivo** mes a mes: en cada mes `t`, los
clientes elegibles que inician el tratamiento contra los que no lo inician en `t` (aunque lo
hagan después). Covariables en `t-1` o antes; resultados en `t+3`. Estimando: **efecto en los
tratados (ATT), por intención de tratar**.

| Análisis | Tratamiento | Control | Resultado | Primario |
|---|---|---|---|---|
| `nomina_actividad` | Inicia la nómina en t (sin nómina en t-1, t-2, t-3) | No la inicia en t | Activo en t+3 | sí |
| `nomina_productos` | ídem | ídem | Cambio en otros productos, t-1 a t+3 | sí |
| `nomina_actividad_1` | ídem | ídem | Activo en t+1 | no |
| `canal_meses_activo` | Alta por el canal KHM | Alta por KHN | Meses activo de alta+2 a alta+7 | sí |
| `canal_activo_7` | ídem | ídem | Activo en alta+7 | no |
| `canal_khq_jovenes` | Alta por KHQ, 18 a 30 años | Alta por KHM, 18 a 30 años | Meses activo | no |
| `producto_recibo` | Adquiere débito automático, activo en t-1 y t-2 | No lo adquiere en t | Inactivo en t+3 | sí |
| `producto_tjcr` | Adquiere tarjeta de crédito, ídem | ídem | Inactivo en t+3 | sí |
| `producto_ecue` | Adquiere cuenta electrónica, ídem | ídem | Inactivo en t+3 | sí |
| `producto_*_1` | ídem | ídem | Inactivo en t+1 | no |

**Ventanas.** Cohortes `t = 9 ... 13` (octubre de 2015 a febrero de 2016) en nómina y
productos, para tener actividad real en `t-3` (la demografía y la actividad de enero a julio
de 2015 están congeladas, ver [hito 1](hito1.md)). Canal: altas de julio a octubre de 2015.

**"Otros productos"** excluye la nómina, la pensión (siempre acompaña a la nómina) y la cuenta
nómina (se abre con ella): contarlos haría el efecto mecánico.

**Covariables.** Nómina y productos: demografía y los 24 productos en `t-1`; actividad en
`t-1`, `t-2` y `t-3`; otros productos en `t-1`, `t-3` y `t-6`; mes. Canal: perfil al entrar
(edad, sexo, renta, segmento, provincia, mes de alta), con canal, segmento y renta tomados de
alta+1 por el registro tardío. **No se ajustan** los productos del mes de alta: pueden ser
parte del efecto del canal.

## DAG supuesto

Nómina (los demás diseños, en el JSON):

```
Demografía (t-1) ──────────────┐
Historia: actividad y productos ┼──► Inicia nómina (t) ──► Activo / otros productos (t+3)
Mes t ──────────────────────────┘          │                      ▲
                                           └► Cuenta nómina       │
U: cambio de empleo (no observado) ──► Inicia nómina, y ──────────┘
```

La amenaza principal es **U**: un cambio de trabajo puede traer la nómina y, a la vez, cambiar
la actividad. No se observa. Por eso cada diseño tiene un placebo de adelanto y un análisis
de sensibilidad.

## Métodos

- **Principal:** Double ML con el puntaje del ATT (modelo interactivo, 3 pliegues de ajuste
  cruzado, LightGBM), sobre todas las filas del diseño. Los resultados previos (actividad y
  tenencia) entran como covariables.
- **Secundarios:** emparejamiento por propensión, bosque causal y, para nómina -> actividad,
  diferencias en diferencias doble robusto. En nómina -> productos el resultado ya es un
  cambio, así que Double ML sobre él es una diferencia en diferencias.
- **Por qué:** en el [hito 3](hito3.md), con selección en observables todos los métodos que
  ajustan recuperan el efecto (el ingenuo no); con un efecto fijo no observado solo
  diferencias en diferencias lo hace; con tendencias no paralelas fallan todos, pero el
  placebo con un período previo lo delata. Por eso: Double ML con resultados previos como
  covariables, DiD como contraste y placebo de adelanto obligatorio.

## Refutaciones y criterios (fijados antes de mirar)

| Prueba | Pasa si |
|---|---|
| Significativo | El IC 95 % del estimador principal excluye el cero |
| Placebo por permutación (DoWhy) | Con el tratamiento permutado, \|efecto\| ≤ 25 % del estimado |
| Causa común aleatoria (DoWhy) | El efecto cambia ≤ 10 % |
| Subconjunto del 80 % (DoWhy) | El efecto medio cambia ≤ 10 % |
| Placebo de adelanto | Clientes que inician 4 meses después, resultado medido antes: \|efecto\| ≤ 25 % del estimado |
| Consistencia | Emparejamiento, Double ML y bosque causal (y DiD) con el mismo signo y razón máx/mín ≤ 2 |
| Sensibilidad | Informativa: valor de robustez de Cinelli y Hazlett frente a la covariable observada más fuerte; valor E en resultados binarios |

Multiplicidad: Holm-Bonferroni sobre los seis análisis primarios.

**Veredicto:**

- *sin efecto detectable*: el IC incluye el cero;
- *creíble*: significativo y pasa todo, robusto en sensibilidad;
- *creíble pero sensible*: como el anterior, pero un confusor omitido más débil que la
  covariable observada más fuerte bastaría para anularlo;
- *no separable de la selección*: falla el placebo de adelanto;
- *frágil*: falla la consistencia o algún refutador.

## Supuestos y limitaciones

- **Intercambiabilidad condicional:** dadas las covariables, iniciar o no en `t` es como si
  fuera al azar. No se puede probar; el placebo y la sensibilidad lo ponen a prueba.
- **Positividad:** revisada con la propensión logística, sin leer resultados (detalle en el
  JSON). Es buena en nómina, débito, tarjeta, cuenta electrónica y KHM frente a KHN: ningún
  tratado (o el 0,3 % en débito y el 1,6 % en cuenta electrónica) tiene propensión mayor que
  0,95. **En KHQ frente a KHM (18 a 30 años) es mala:** el 86 % de los tratados por KHQ tiene
  propensión mayor que 0,95, porque KHQ es casi solo universitario. Ese análisis queda como
  exploratorio y su resultado no se interpreta como causal.
- **La actividad no tiene definición pública:** puede incluir mecánicamente el abono de la
  nómina o los movimientos de un débito o una tarjeta.
- Los códigos de canal están anonimizados; el panel termina en mayo de 2016.
- Efecto por intención de tratar: algunos controles se tratan después (diluye el efecto).

## Desviaciones

Cualquier cambio en los archivos con huella (diseños, métodos, refutaciones, flujo del hito 4
y resultados del hito 3) después del tag se informa aquí, con su motivo.

*Ninguna hasta ahora.*
