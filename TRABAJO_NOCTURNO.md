# Trabajo nocturno (19-20 de octubre de 2026)

Bitácora de lo hecho sin supervisión. Las decisiones que normalmente se consultarían se
anotan con su justificación.

## Decisiones

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
