# Cambios

## Hito 1 (2026-10-19)

- Estructura del repositorio, uv, ruff, pytest, CI y fuente de Pages en `docs/`.
- Ingesta del CSV de Santander en DuckDB (todo como texto, tipado explícito, UTF-8 verificado).
- Calidad del dato: faltantes por mes, inconsistencias demográficas, congelamiento de la
  demografía y la actividad en enero-julio de 2015, registro tardío del canal y el segmento.
- Diseños de las tres preguntas causales (nómina, canal, productos) como emulación de ensayo
  objetivo, con placebos de adelanto.
- Mini-Santander sintético para pruebas y CI.
