# Analítica de clientes causal y explicable

**¿Quién va a adquirir un producto, y a quién le cambia el resultado una acción?** Son dos
preguntas distintas. Este proyecto las separa sobre el panel mensual de Santander (957 mil
clientes, 17 meses) y el experimento de correo de Hillstrom. Caso 6 de un portafolio de
ciencia de datos aplicada a banca.

[Código](https://github.com/stous1/causal-customer-analytics) ·
[Preregistro](preregistro.md) ·
[Resumen estructurado (JSON)](resultados/resumen.json)

## Resultados

| Pregunta | Efecto en los tratados | Veredicto |
|---|---|---|
| ¿La nómina vuelve más activo al cliente? | +8,9 pp a 3 meses | no separable de la selección: los que la traerán ya están 5,8 pp más activos antes |
| ¿El canal de vinculación cambia cuánto dura activo? | KHM: −0,38 meses de 6 frente a KHN | creíble |
| ¿Qué productos frenan el paso a inactivo? | débito, tarjeta, cuenta electrónica | ninguno con credibilidad |

**Predicción:** MAP@7 de 0,856 (referencia 0,700) para anticipar qué producto adquiere cada
cliente. Lo que más predice una adquisición es que el cliente ya sea activo; adquirir el
producto no causa de forma creíble más actividad.

## En un minuto

- **Hito 5, heterogeneidad** ([página](hito5.md)): en Hillstrom, el bosque causal ordena bien a
  los clientes del correo de mujer, pero segmentar no supera mandarle a todos el de hombre. En
  Santander, los clientes con más propensión a adquirir son en los que adquirir menos cambia.
- **Hito 4, efectos en Santander** ([página](hito4.md)): veredictos preregistrados; el placebo
  de adelanto desarma la historia de la nómina.
- **Preregistro** ([página](preregistro.md)): preguntas, DAG, ventanas, métodos y criterios,
  fijados antes de estimar.
- **Hito 3, validación** ([página](hito3.md)): en Hillstrom sesgado el ingenuo se equivoca 43 %;
  Double ML acierta. En el semisintético, ningún método salva una tendencia oculta, pero el
  placebo la detecta.
- **Hito 2, predicción** ([página](hito2.md)): LightGBM congelado y medido una vez en prueba.
- **Hito 1, datos** ([página](hito1.md)): la demografía y la actividad de enero a julio de 2015
  están congeladas.

## Hitos

1. [Datos, calidad y diseños](hito1.md) ✔
2. [Capa predictiva](hito2.md) ✔
3. [Validación de métodos causales](hito3.md) ✔
4. [Preregistro](preregistro.md) y [efectos causales en Santander](hito4.md) ✔
5. [Efectos heterogéneos y políticas](hito5.md) ✔
