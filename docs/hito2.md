# Hito 2: capa predictiva

[← Volver a la portada](index.md)

**Pregunta:** ¿quién va a adquirir cada producto el mes que viene? Es una pregunta de
**predicción**: sirve para decidir a quién mostrarle una oferta, no para saber qué la causa.

## Cómo se evaluó

- Una fila por cliente y mes `t` (julio de 2015 a abril de 2016: solo meses con demografía
  real). La etiqueta de un producto vale 1 si el cliente no lo tenía en `t` y lo tiene en
  `t+1`.
- Partición temporal: entrenamiento con `t` = julio a diciembre de 2015, validación con enero
  y febrero de 2016. Ahí se eligieron los productos, la configuración de LightGBM y las rondas.
- Parámetros congelados con el tag `hito2-congelado`. Reentrenamiento con julio de 2015 a
  febrero de 2016 y **una sola medición en prueba**: adquisiciones de abril y mayo de 2016.
- Referencia simple: la tasa de adquisición de cada producto por segmento, tramo de edad y
  actividad.
- Métricas: precisión promedio (AP) por producto, con IC por bootstrap, y MAP@7 por cliente
  (la métrica de la competencia; ver abajo qué mide exactamente). Nunca exactitud: con 1 % de positivos, decir "nadie
  compra" acierta el 99 %.

## Resultados en prueba

![Precisión promedio por producto](resultados/hito2/ap_productos.png)

| Producto | AP modelo (IC 95 %) | AP referencia | Adquisiciones en prueba |
|---|---|---|---|
| Cuenta nómina | 0,472 (0,459 a 0,489) | 0,010 | 4.727 |
| Pensiones (nómina) | 0,389 (0,379 a 0,399) | 0,020 | 9.937 |
| Cuenta corriente | 0,371 (0,360 a 0,383) | 0,027 | 7.881 |
| Cuenta electrónica | 0,351 (0,339 a 0,366) | 0,023 | 4.958 |
| Nómina | 0,351 (0,338 a 0,364) | 0,020 | 9.278 |
| Débito automático | 0,305 (0,300 a 0,312) | 0,046 | 19.962 |
| Tarjeta de crédito | 0,239 (0,229 a 0,247) | 0,020 | 8.348 |

Los productos raros (fondos, valores, depósitos a largo plazo, impuestos) quedan con AP menor
a 0,05; el detalle está en [metricas.json](resultados/hito2/metricas.json).

## Qué mide el MAP@7 (y por qué 0,856 no se compara con Kaggle)

Se predicen **solo productos nuevos**: la etiqueta vale 1 si el cliente no tenía el producto en
`t` y lo tiene en `t+1`, y el ranking nunca incluye un producto que ya tiene (0 etiquetas y 0
puntajes sobre productos tenidos, verificado). No hay tenencia previa inflando la cifra.

Lo que sí la hace alta es **sobre quién se promedia**. El MAP@7 publicado promedia solo los
clientes-mes que adquirieron algo (el 3 %) y elige entre 13 productos. Un
[diagnóstico](resultados/hito2/diagnostico_map.json) sobre las mismas predicciones del modelo
congelado (reproducido y verificado: la AP de los 13 productos coincide con la publicada):

| Definición del MAP@7 | Clientes-mes | Modelo | Referencia | Popularidad global |
|---|---|---|---|---|
| Publicada: con alguna adquisición entre los 13 productos | 54.213 | 0,856 | 0,700 | 0,646 |
| Con alguna adquisición entre los 24 productos | 54.611 | 0,849 | 0,695 | 0,641 |
| Todos los clientes-mes (0 si no adquiere nada, como Kaggle) | 1.850.077 | 0,0251 | 0,0205 | 0,0189 |
| "Nuevo estricto": sin el producto ni en t ni en t-1 | 36.837 | 0,775 | 0,673 | 0,604 |

- Hasta la popularidad global (recomendar a todos los mismos productos) llega a 0,646 con la
  definición publicada: la cifra absoluta dice poco; lo que vale es la **mejora sobre las
  referencias**, que se mantiene en todas las definiciones (+0,16 sobre la referencia por
  celdas en la publicada, +22 % relativo en la de todos los clientes).
- Muchas adquisiciones son **productos que vuelven**: el cliente los tenía en `t-1`, no en
  `t`, y otra vez en `t+1` (45 % de las altas de nómina, 35 % de las de débito y de tarjeta).
  La definición de Kaggle también los cuenta como nuevos. Sin ellos, un tercio de los
  clientes-mes con adquisición se queda sin ninguna (de 54.213 a 36.837) y el MAP@7 baja a
  0,775.
- **No hizo falta reentrenar:** el modelo ya se entrenó para productos nuevos. Estas cifras son
  un diagnóstico sobre la misma medición en prueba, no una segunda prueba.

## Lo que predice (y lo que no dice)

![SHAP tarjeta de crédito](resultados/hito2/shap_tjcr.png)

En los cuatro productos que se contrastan con la capa causal (nómina, débito automático,
tarjeta de crédito y cuenta electrónica), las variables que más pesan son la **actividad**
del cliente y su **relación activa** (`tiprel_1mes = A`): el cliente activo es el que compra.
En la nómina pesa también haberla tenido el mes anterior: muchas nóminas van y vienen.

> **Esto no es causalidad.** Que la actividad prediga la adquisición no dice si adquirir un
> producto vuelve más activo al cliente, ni si ser activo lleva a adquirirlo, ni si ambas
> cosas tienen una causa común. Esa es la pregunta del [hito 4](hito4.md), que va en la
> dirección contraria: ¿adquirir el producto cambia la actividad?

Gráficos de las demás importancias: [nómina](resultados/hito2/shap_nomina.png),
[débito automático](resultados/hito2/shap_recibo.png),
[cuenta electrónica](resultados/hito2/shap_ecue.png).
