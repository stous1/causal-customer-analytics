# Trabajo nocturno (19-20 de octubre de 2026)

Bitácora de lo hecho sin supervisión. Se cumplieron las reglas de los CLAUDE.md anteriores:
sin `push --force`, sin borrar ramas ni tags, sin reescribir historia, sin terminar procesos
ajenos, credenciales solo para `git push`, y código de salida real de pytest y ruff
verificado (sin tuberías) antes de cada commit. Los repositorios hermanos no se tocaron.

## Estado: los seis hitos terminados

Tags: `hito2-congelado`, `preregistro` y `v1.0`. 30 pruebas pasan; 71 comprobaciones de
cifras de README y Pages contra los JSON publicados, sin fallas (también corren en CI).

### Hito 1: estructura, datos y diseños

- uv, ruff, pytest, CI (lint, pruebas rápidas, verificación de cifras; integración en main),
  `docs/` para Pages, CLAUDE.md adaptado.
- Ingesta de 13.647.309 filas (956.645 clientes, 17 meses) en DuckDB limitado a 24 GB, en ~2
  minutos. Todo leído como texto y tipado en un solo lugar; UTF-8 verificado.
- **Hallazgo principal de calidad:** de enero a julio de 2015 la demografía, la antigüedad,
  el segmento y la actividad están congelados (copia de julio); los productos no. En julio
  entran 193 mil clientes que ya existían. El canal y el segmento de un cliente nuevo se
  registran un mes tarde.
- Diseños de las tres preguntas como emulación de ensayo objetivo mes a mes, con placebos de
  adelanto. Mini-Santander sintético para pruebas y CI.

### Hito 2: capa predictiva

- 13 productos, LightGBM, partición temporal, congelado con tag y medido una vez en prueba
  (abril y mayo de 2016). **MAP@7 0,856 contra 0,700** de la referencia; AP de 0,24 a 0,47 en
  los productos frecuentes contra 0,01 a 0,05 de la referencia.
- SHAP marcado como predictivo: lo que más predice una adquisición es que el cliente ya sea
  activo.

### Hito 3: validación de métodos

- Hillstrom sesgado (10 sorteos): ingenuo +43 %, Double ML +0 % con cobertura 10 de 10.
- Semisintético sobre covariables reales (3 escenarios × 10): con selección en observables
  todos los métodos que ajustan aciertan; con efecto fijo oculto solo DiD; con tendencias no
  paralelas ninguno, pero el placebo las detecta en 10 de 10.

### Hito 4: preregistro y Santander

- Preregistro con tag antes de estimar (huellas SHA-256; `scripts/hito4.py` se niega a
  correr sin el tag; el código con huella no cambió después).
- **Nómina -> actividad: +8,9 pp (8,3 a 9,5), pero el placebo de adelanto da +5,8 pp: no
  separable de la selección** ("los activos la traen").
- Nómina -> otros productos: −0,42, artefacto: el 51 % cambia la cuenta corriente por la
  cuenta nómina. Exploratorio sin la cuenta corriente: +0,149, placebo +0,094.
- **Canal KHM frente a KHN: −0,38 meses activo de 6 (−0,50 a −0,26): creíble.**
- Productos que frenan la inactividad: débito sin efecto; tarjeta y cuenta electrónica no
  separables de la selección.

### Hito 5: heterogeneidad y políticas

- Hillstrom (mitad de prueba): el bosque ordena bien el correo de mujer (quintil bajo 0,014,
  alto 0,085; Qini 0,071); el árbol de política no supera mandar el correo de hombre a todos.
- Santander: la heterogeneidad del canal no se confirma en la mitad independiente; el efecto
  de la nómina sobre la actividad está entero en los inactivos (compatible con un efecto
  mecánico de la definición).
- **Predice contra causa:** correlación de Spearman +0,30 (tarjeta) y +0,34 (cuenta
  electrónica) entre propensión a adquirir y efecto (negativo = protege): los más propensos
  son en quienes adquirir menos cambia.

### Hito 6: cierre

- Páginas por hito, README como puerta de entrada, `docs/resultados/resumen.json` para un
  futuro agente intérprete, CHANGELOG y tag `v1.0`.

## Pendiente o bloqueado

- **Activar GitHub Pages** (Settings > Pages > Deploy from a branch > `main` / `docs`): requiere
  la web o la API de GitHub y las credenciales solo se usan para `git push`. Los enlaces del
  README a `stous1.github.io/causal-customer-analytics` funcionarán al activarlo.
- **No revisé el resultado de CI en GitHub** (leerlo requiere la API). Localmente pasan ruff,
  formato, las 30 pruebas y la verificación de cifras. Riesgo conocido: CI instala con
  `uv sync --locked` en Linux; EconML/DoWhy/LightGBM tienen ruedas para Linux.
- **Trabajo futuro:** el agente intérprete (no se implementó, como se pidió); el "extra
  opcional" de comparar modelos con demografía sucia y limpia; una prueba fresca de la capa
  predictiva si aparecieran meses posteriores a mayo de 2016.
- La definición preregistrada de "otros productos" no previó el cambio de cuenta corriente
  por cuenta nómina: si se repite el estudio, preregistrar "otros productos sin cuentas".

## Decisiones tomadas por ti

1. **Nombre del paquete:** `causal` (en `src/causal/`).
2. **Congelamiento de enero a julio de 2015.** La demografía, la antigüedad, el segmento y la
   actividad no cambian para ningún cliente entre los meses 0 y 6; los productos sí. Decisión:
   toda variable no-producto se toma de los meses 6 a 16. Las cohortes de tratamiento empiezan
   en t = 9 para tener actividad real en t-3. *Por qué:* usar esos meses como pasado filtraría
   información de julio.
3. **Emulación de ensayo objetivo (ITT) en lugar de "controles limpios".** Los controles son
   quienes no inician el tratamiento en t, aunque lo inicien después. *Por qué:* exigir que
   los controles no se traten en t+1 ... t+3 condiciona en el futuro, y quien se vuelve
   inactivo deja de adquirir productos: sesgaría a favor de un efecto protector.
4. **Estimando principal: efecto en los tratados (ATT)**, con controles muestreados 1 de cada
   20 de forma determinista (`hash` de DuckDB). *Por qué:* hay ~200 mil elegibles por mes; con
   controles muestreados al azar el ATT no cambia.
5. **Resultado de tenencia sin nómina, pensiones ni cuenta nómina.** *Por qué:* `nomina = 1`
   implica `nom_pens = 1` siempre, y la cuenta nómina se abre con la nómina; contarlos haría
   el efecto mecánico.
6. **Pregunta del canal: KHM frente a KHN** (los dos canales no universitarios con más altas,
   edades parecidas). KHQ frente a KHM queda como secundaria, restringida a 18-30 años, por
   positividad débil (KHQ es 92 % universitario). Canal, segmento y renta se toman de alta+1
   (registro tardío) y la actividad se mide de alta+2 a alta+7. Los productos del mes de alta
   no se ajustan (posibles mediadores).
7. **Productos de la pregunta 3:** débito automático (`recibo`), tarjeta de crédito (`tjcr`)
   y cuenta electrónica (`ecue`): los tres con más altas fuera de la nómina y la cuenta
   corriente.
8. **GPU no usada:** LightGBM de PyPI no trae CUDA y entrena en minutos en CPU; EconML y DoWhy
   no la aprovechan.
9. **Pages:** la carpeta `docs/` queda lista para "main /docs". Activar Pages requiere la API
   o la web de GitHub, y las credenciales solo se usan para `git push`: **queda pendiente para
   el usuario** (Settings > Pages > Deploy from a branch > main /docs).
10. **Productos de la capa predictiva:** los que tienen al menos 1.000 adquisiciones en
    entrenamiento y 100 en validación (13 productos). *Por qué:* los depósitos a corto y
    mediano plazo (`deco`, `deme`) dejan de venderse a fines de 2015; con cero positivos en
    validación la AP no está definida.
11. **Entrenamiento predictivo solo con t >= 6** por el congelamiento; negativos muestreados al
    10 % con peso 10 (validación y prueba completas). Dos configuraciones (31 y 127 hojas) con
    parada temprana por AP en validación (t = 12 y 13); reentrenamiento final con t = 6 ... 13
    y las rondas congeladas; prueba t = 14 y 15, una sola vez.
12. **Referencia simple:** tasa de adquisición del producto por celda (segmento, tramo de edad,
    actividad) en el entrenamiento.
13. **IC de la AP por bootstrap de filas** (100 repeticiones). Un cliente aparece a lo sumo dos
    veces en prueba: el efecto de no agrupar por cliente es pequeño; se declara.
14. **Estimador principal en Santander: Double ML con el puntaje del ATT (implementación
    propia, `metodos.dml_att`)** y no `LinearDML` de EconML. *Por qué:* `LinearDML` con efecto
    constante estima un promedio ponderado por la varianza del tratamiento, no el ATT. DoWhy
    refuta con `LinearDML` (estimador distinto, declarado en el preregistro).
15. **Bosque causal:** ATT = promedio del efecto condicional en los tratados, con el IC de
    EconML, que es conservador (promedia errores individuales). El ATT doble robusto del
    bosque (`att_`) fue más ruidoso en una simulación rápida; se guarda como dato.
16. **Hillstrom sesgado:** se conservan todos los controles y cada tratado con probabilidad
    logística conocida de la historia de compra, la recencia, ser nuevo y el canal web. El
    ATT verdadero se calcula con el experimento completo ponderando por esa probabilidad.
    10 sorteos.
17. **Semisintético:** 50 mil filas de covariables reales del diseño de nómina, tres
    escenarios, 10 repeticiones. Se agregó "Double ML con resultados previos" porque es lo
    que se hace en Santander (los rezagos de actividad y tenencia son covariables).
18. **Costo por correo en la política de Hillstrom: 0,05 visitas** (supuesto ilustrativo; el
    efecto medio del correo de hombre es 0,077 y el de mujer 0,045).
19. **Ensayo del flujo del hito 4 sobre el mini-Santander sintético antes del preregistro.**
    *Por qué:* corregir errores de código después del tag sería una desviación; el ensayo no
    toca datos reales. Se agregaron los canales KHM y KHN al generador sintético para eso.
20. **KHQ frente a KHM (18 a 30 años) queda como exploratorio:** el 86 % de los tratados por
    KHQ tiene propensión mayor que 0,95 (positividad mala). Se anotó en el preregistro antes
    de estimar.
21. **Tag `preregistro`** sobre el commit con `docs/preregistro.md` y
    `docs/resultados/preregistro.json` (huellas SHA-256 de diseños, métodos, refutaciones,
    flujo del hito 4 y resultados del hito 3). `scripts/hito4.py` se niega a estimar sin ese
    tag, y `tests/test_congelados.py` verifica que el JSON no cambie.
22. **Exploratorio de la cuenta corriente** agregado después del tag y marcado como tal; no
    cambia ningún resultado preregistrado. Anotado en `docs/preregistro.md` (desviaciones).
23. **Árboles de política en Santander:** el umbral es el ATT del hito 4 y el árbol se ajusta
    sobre el efecto condicional del bosque en una mitad y se evalúa con puntajes doble
    robustos en la otra. Primero usé el promedio de los puntajes individuales como umbral
    (no estima el ATT) y un signo equivocado para la inactividad; ambos se corrigieron antes
    de publicar.
24. **Hito 5 solo con análisis primarios con efecto distinto de cero**, cada uno con el
    veredicto del hito 4 al lado; los no creíbles se presentan como ilustración del método.
