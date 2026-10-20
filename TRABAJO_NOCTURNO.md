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
