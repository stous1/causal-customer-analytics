# CLAUDE.md

Guía para trabajar en este repositorio.

## Objetivo

Caso de uso 6 del portafolio de ciencia de datos aplicado a banca: **analítica de clientes
causal y explicable**. Separa dos preguntas que suelen confundirse:

- **Predicción:** ¿quién va a adquirir un producto el mes que viene?
- **Causalidad:** ¿a quién le cambia el resultado una acción?

Sobre el panel mensual de Santander Product Recommendation (17 meses, 957 mil clientes) y el
experimento de Hillstrom (correo con tratamiento y control aleatorizados).

Hitos:

1. Estructura, ingesta en DuckDB, calidad del dato, exploración y diseños (tratamientos,
   resultados y ventanas).
2. Capa predictiva: propensión a adquirir cada producto el mes siguiente, con SHAP, partición
   temporal y una referencia simple. Congelada con tag y medida una vez en prueba.
3. Validación de métodos causales donde se conoce la respuesta: Hillstrom (contra el
   experimento) y un semisintético con efectos inyectados sobre covariables reales.
4. Preregistro con tag; después, estimación en Santander con refutaciones, placebo, controles
   negativos y sensibilidad.
5. Efectos heterogéneos: bosque causal, SHAP sobre el efecto y árboles de política.
6. Páginas, README final, verificación de cifras, CHANGELOG y tag v1.0.

Trabajo futuro (no se implementa): un agente intérprete de resultados. Por eso todo resultado
queda en JSON estructurado en `docs/resultados/` (ver "Resultados estructurados").

## Stack

- Python 3.12, manejado por **uv** (`.python-version` fija 3.12).
- **DuckDB** local (`data/santander.duckdb`), limitado a 24 GB con desborde a
  `data/tmp/` (`causal.base.conectar`). Sin servicios externos.
- pandas, numpy, scikit-learn, LightGBM, SHAP, EconML, DoWhy, scikit-uplift, statsmodels;
  Altair + vl-convert para gráficos HTML y PNG.
- **GPU:** no se usa. LightGBM de PyPI no trae CUDA y los modelos entrenan en minutos en CPU;
  EconML y DoWhy no usan GPU. Ver `TRABAJO_NOCTURNO.md`.
- **pytest** para pruebas y **ruff** para lint y formato.

## Comandos

```bash
uv sync                                       # crea .venv e instala dependencias (incluye dev)
uv run pytest                                 # todas las pruebas (mini-Santander sintético)
uv run pytest -m "not integracion"            # solo pruebas rápidas
uv run ruff check . && uv run ruff format .   # lint y formato
uv run python scripts/hito1.py preparar       # CSV -> data/santander.duckdb (~2 min)
uv run python scripts/hito1.py explorar       # -> reports/hito1/exploracion.json y gráficos
uv run python scripts/hito2.py desarrollar    # validación -> reports/hito2/parametros.json (~10 min)
uv run python scripts/publicar_resultados.py --hito 2 --solo-parametros   # congelar (+ tag)
uv run python scripts/hito2.py evaluar        # prueba, una vez, con los parámetros publicados
uv run python scripts/hito3.py hillstrom      # validación en Hillstrom (~5 min)
uv run python scripts/hito3.py semisintetico  # validación en el semisintético (~15 min)
uv run python scripts/hito3.py graficos
uv run python scripts/preregistrar.py         # docs/resultados/preregistro.json (+ tag preregistro)
uv run python scripts/hito4.py estimar        # Santander; se niega a correr sin el tag preregistro
uv run python scripts/hito4.py graficos
uv run python scripts/hito5.py                # heterogeneidad y políticas
uv run python scripts/publicar_resultados.py --hito 1   # reports/hitoN -> docs/resultados/hitoN
uv run python scripts/verificar_cifras.py     # cifras de README y Pages contra los JSON
```

## Datos

- `data/raw/train_ver2.csv` (Santander, 2,3 GB) y `data/raw/hillstrom/` (descargado con
  `sklift.datasets.fetch_hillstrom`). **No se versionan.**
- El CSV se lee todo como texto y se tipa en `ingesta.py`: espacios a la izquierda, `NA`,
  `-999999` en antigüedad, `indrel_1mes` con `1` y `1.0`. Es UTF-8 válido (la eñe viene como
  `C3 91`); la carga verifica que no haya caracteres de reemplazo.
- `mes` = índice 0 (enero de 2015) a 16 (mayo de 2016).
- **Congelamiento de enero a julio de 2015:** en los meses 0 a 5 la demografía, la
  antigüedad, el segmento y la actividad son una copia del mes 6: no cambia ningún cliente.
  Los productos sí cambian. **Toda variable que no sea un producto se toma de los meses 6 a
  16** (`disenos.PRIMER_MES_DEMOGRAFIA`). Usar esos meses como pasado filtraría el futuro.
- **Registro tardío:** en el mes de alta de un cliente nuevo faltan el canal (99 %) y el
  segmento (100 %); aparecen al mes siguiente.
- `nomina = 1` implica `nom_pens = 1`; la cuenta nómina (`cno`) se abre con la nómina. Los
  tres se excluyen de "otros productos" (`disenos.OTROS`).

## Estructura

- `src/causal/`: toda la lógica, como funciones reutilizables.
  - `rutas.py`: rutas del proyecto. **Toda ruta se obtiene de aquí.**
  - `base.py`: conexión a DuckDB con memoria limitada, desborde a disco y UTC.
  - `ingesta.py`: CSV -> tabla `panel` tipada. `PRODUCTOS` con códigos cortos y nombres.
  - `calidad.py`: faltantes, inconsistencias, congelamiento, registro tardío. **No cruza
    tratamientos con resultados.**
  - `disenos.py`: tabla `rezagos` (t-6 ... t+4 con marcos `RANGE`, sin saltar huecos) y las
    tablas de los diseños (`d_nomina`, `d_canal`, `d_producto_{recibo,tjcr,ecue}` y sus
    placebos). `columnas_x` define el conjunto de ajuste de cada diseño.
  - `graficos.py`: Altair a HTML y PNG.
  - `sintetico.py`: mini-Santander con el formato del CSV real, para pruebas y CI.
  - `flujo_hito1.py`: preparar y explorar.
  - Hito 2: `prediccion.py` (tabla `pred`: variables en t, etiqueta = adquisición en t+1;
    LightGBM, métricas, referencia por celdas, MAP@7) y `flujo_hito2.py` (desarrollar y
    evaluar). Congelado en `hito2-congelado` con `docs/resultados/hito2/parametros.json`
    (lo verifica `tests/test_congelados.py`). Los modelos finales de nómina, débito, tarjeta y
    cuenta electrónica quedan en `reports/hito2/modelos/` para el contraste del hito 5.
  - Hito 3: `metodos.py` (ingenuo, regresión, emparejamiento, Double ML del ATT, DiD doble
    robusto, bosque causal; salida común `Estimacion`), `hillstrom.py`, `semisintetico.py`
    (solo recibe covariables) y `flujo_hito3.py`.
  - Hito 4: `refutaciones.py` (DoWhy, valor de robustez, valor E, consistencia, Holm),
    `preregistro.py` (DAG, supuestos, huellas) y `flujo_hito4.py` (`ANALISIS` preregistrados,
    veredicto). `scripts/hito4.py` no corre sin el tag `preregistro`.
  - Hito 5: `flujo_hito5.py` (bosque causal, SHAP sobre el efecto, árboles de política;
    Hillstrom con mitad de prueba; contraste predice contra causa).
- `scripts/`: puntos de entrada delgados que orquestan funciones de `src/`.
- `notebooks/`: solo exploración. Nada en `src/` ni `scripts/` importa de notebooks.
- `tests/`: pytest. Las lentas se marcan con `@pytest.mark.integracion`. Todas corren sobre el
  mini-Santander o sobre datos simulados: CI no necesita los datos reales.
- `data/` y `reports/` (ignoradas): datos, base DuckDB y salidas de trabajo.
- `docs/`: fuente de GitHub Pages (rama `main`, carpeta `/docs`). `docs/resultados/` se
  versiona y solo se actualiza con `scripts/publicar_resultados.py`.
- `README.md` es la puerta de entrada; `TRABAJO_NOCTURNO.md`, la bitácora de decisiones.

## Resultados estructurados

Cada hito deja un JSON en `docs/resultados/hitoN/` con cifras, intervalos, supuestos y
veredictos. Pensados para que un agente intérprete los lea sin mirar código: cada estimación
causal lleva `metodo`, `estimando`, `efecto`, `ic95`, `refutaciones` (con `pasa`) y
`limitaciones`. Las importancias SHAP predictivas llevan `tipo: "predictivo"`.

## Convenciones

- La lógica vive en `src/` como funciones reutilizables **con type hints**.
- Las pruebas no dependen de internet ni de `data/raw`.
- **Las pruebas son deterministas**: semillas fijas y nada que dependa del reloj ni de la
  zona horaria. El muestreo de controles usa `hash(cliente, mes, semilla)` de DuckDB, no el
  orden de lectura.
- Documentación, docstrings y mensajes de commit **en español**.
- Rutas centralizadas en `causal.rutas`; **nunca rutas absolutas** en el código.
- Commits pequeños y enfocados. En modo autónomo no se pide confirmación antes de cada commit:
  al cerrar cada hito se hace push.

## Regla de evaluación

- **Predicción (hito 2):** partición temporal. Solo meses con demografía real (t >= 6).
  Todo se elige en validación y se congela con tag (`hito2-congelado` y
  `docs/resultados/hito2/parametros.json`); la prueba se mide **una sola vez**. Métricas:
  precisión promedio (AP) por producto, MAP@7 y comparación contra la referencia simple.
  Nunca exactitud.
- **Causalidad:** en Santander no hay verdad causal. La credibilidad se construye así:
  1. Validar los métodos donde se conoce la respuesta: Hillstrom (experimento) y el
     semisintético (efectos inyectados sobre covariables reales de Santander). El
     semisintético **solo lee covariables**, nunca resultados reales (lo verifica una prueba).
  2. **Preregistro antes de estimar cualquier efecto en Santander** (tag `preregistro`,
     `docs/preregistro.md` y `docs/resultados/preregistro.json` con huellas SHA-256). Si hay
     que desviarse, se informa como desviación.
  3. En Santander: refutaciones de DoWhy, placebo de adelanto, controles negativos,
     sensibilidad a variables omitidas y consistencia entre métodos.
- **Nunca presentar la importancia SHAP de un modelo predictivo como causa.** Contrastar
  siempre "lo que predice" con "lo que causa".
- Declarar siempre los supuestos y las limitaciones de los datos observacionales.

## Regla de pruebas antes de un commit (para Claude y cualquier subagente)

- **Nunca encadenar pytest (ni ruff) con tuberías que oculten el código de salida**, como
  `uv run pytest | tail -1 && git commit`: el código que ve `&&` es el de `tail`.
- Antes de cada commit, ejecutar las pruebas sin tubería (o redirigir a un archivo) y
  **verificar el código de salida real** (`echo $?` en bash, `$LASTEXITCODE` en PowerShell).
  Solo se hace el commit si es 0.

## Regla de procesos (para Claude y cualquier subagente)

- **Nunca terminar procesos que no hayas iniciado tú.** Nada de `taskkill /IM`, `pkill`,
  `killall` ni `kill` generales por nombre.
- Si un comando se traba, termina solo ese proceso por su identificador.
- Al delegar en un subagente, incluye esta regla en sus instrucciones.

## Regla de credenciales (para Claude y cualquier subagente)

- Las credenciales guardadas en la máquina solo se usan para `git push`. Para cualquier otra
  cosa (leer logs de CI, llamar la API de GitHub, activar Pages) hay que preguntarle antes al
  usuario.

## Regla de git

- Nunca `git push --force`, borrar ramas o tags ni reescribir la historia.

## Regla dura de datos

- **Nunca usar datos reales de clientes.** Solo datasets públicos (Santander Product
  Recommendation de Kaggle, Hillstrom) o sintéticos.
- **Tampoco** código, reglas ni ideas de proyectos internos de ningún banco.
- Los repositorios hermanos (`../identity-resolution`, `../aml-graph-detection`) son solo de
  referencia: no se modifican desde aquí ni se corre git en ellos.

## Docker

No se usa: todo corre local con DuckDB.
