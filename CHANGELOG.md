# Cambios

## Después de v1.0 (2026-10-20)

- Diagnóstico del MAP@7 (`scripts/hito2_diagnostico_map.py`, sin tocar el modelo congelado):
  confirma que solo se predicen productos nuevos y agrega el MAP@7 sobre todos los
  clientes-mes (0,0251 contra 0,0205 de la referencia), con los 24 productos y con "nuevo
  estricto". La página del hito 2, el README y la portada explican qué mide 0,856.

## v1.0 (2026-10-20)

- **Hito 4:** estimación en Santander según el preregistro (12 análisis, 6 primarios), con
  refutaciones de DoWhy, placebo de adelanto, valor de robustez, valor E, consistencia y Holm.
  Exploratorio aparte: el reemplazo de la cuenta corriente por la cuenta nómina.
- **Hito 5:** bosque causal, SHAP sobre el efecto y árboles de política; en Hillstrom con
  mitad de prueba y valor de política por ponderación; en Santander, contraste de la
  propensión a adquirir (hito 2) con el efecto de adquirir.
- `docs/resultados/resumen.json`: resumen estructurado para un futuro agente intérprete.
- README final, portada de Pages y `scripts/verificar_cifras.py` (comprobaciones de README y
  páginas contra los JSON, también en CI).

## Preregistro (2026-10-20)

- Preguntas, DAG supuesto, tratamientos, resultados, ventanas, métodos, criterios de
  refutación y regla de veredicto, con huellas SHA-256; tag `preregistro`.
- Positividad revisada sin leer resultados: KHQ frente a KHM queda como exploratorio.

## Hito 3 (2026-10-20)

- Estimadores con salida común: ingenuo, regresión, emparejamiento, Double ML del ATT,
  diferencias en diferencias doble robusto y bosque causal.
- Hillstrom completo y sesgado (10 sorteos) y semisintético con tres escenarios
  (10 repeticiones) sobre covariables reales de Santander.

## Hito 2 (2026-10-20)

- Propensión a adquirir 13 productos el mes siguiente con LightGBM, partición temporal,
  referencia por celdas, AP con IC, MAP@7 y SHAP marcado como predictivo.
- Congelado en `hito2-congelado` y medido una vez en prueba (abril y mayo de 2016).

## Hito 1 (2026-10-19)

- Estructura del repositorio, uv, ruff, pytest, CI y fuente de Pages en `docs/`.
- Ingesta del CSV de Santander en DuckDB (todo como texto, tipado explícito, UTF-8 verificado).
- Calidad del dato: faltantes por mes, inconsistencias demográficas, congelamiento de la
  demografía y la actividad en enero-julio de 2015, registro tardío del canal y el segmento.
- Diseños de las tres preguntas causales (nómina, canal, productos) como emulación de ensayo
  objetivo, con placebos de adelanto.
- Mini-Santander sintético para pruebas y CI.
