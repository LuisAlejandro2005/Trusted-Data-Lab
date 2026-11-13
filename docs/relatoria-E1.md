# Relatoría de etapa — E1 · ORMO

**Etapa:** E1 · Pipeline de limpieza, integración y puerta de calidad
**Integrantes:** Gael Alexandro Cortez Sarmienta, Luis Alejandro Mendoza Peñaloza

## 1. Punto de partida

El repositorio sólo contenía un README breve. El objetivo de la etapa fue construir un flujo
reproducible con arquitectura Medallion: conservar los datos crudos en Bronce, entregar datos
limpios y validados en Plata, indicadores en Oro, y aislar en cuarentena todo lo que no pasara
la validación.

## 2. Desarrollo

### Primera iteración: base del pipeline
- Se organizó el código en módulos (`ingestion`, `integracion`, `limpieza`, `validacion`,
  `transformaciones`, `indicadores`) orquestados por `pipeline.py`.
- Se implementó el diagnóstico de nulos, la imputación con indicadores, la detección por IQR, las
  columnas Min-Max y Z-Score, las banderas de eventos y la agregación mensual.
- Se agregaron pruebas automatizadas y un generador de datos sintéticos para Colima.

### Segunda iteración: cierre de requisitos de E1
Al revisar el pipeline contra la rúbrica se encontraron huecos que se corrigieron:

| Hallazgo | Corrección |
|----------|------------|
| Había una sola fuente; la integración no se ejecutaba. | Se agregó una segunda fuente con otro esquema (nombres, fechas en texto, `"Inap"`/`"-"`, viento en m/s, catálogos sin acentos) y una fusión con reglas de prioridad y registro de conflictos. |
| Pandera se ejecutaba, pero su resultado se ignoraba; las reglas reales eran filtros manuales. | La puerta de calidad ahora la decide Pandera (`strict`, `coerce`, `lazy`); el motivo de cuarentena sale de los `failure_cases`. |
| El mecanismo de ausencia se decidía sólo por el porcentaje global de nulos. | Se contrasta la ausencia contra variables observadas (fuente, estación, mes) para distinguir MCAR de MAR. |
| Los atípicos sólo se marcaban, sin tratamiento; en precipitación el IQR era 0 y todo día lluvioso salía como atípico. | Se añadió el Z-Score robusto, la winsorización en una columna `_tratado` y cercas calculadas sólo con días lluviosos. |
| La validación ocurría después de imputar y normalizar. | Se movió antes: los valores imposibles ya no influyen en las medianas ni en las escalas. |
| Discretización limitada a tres banderas. | Categorías de lluvia (SMN), temperatura, viento (Beaufort) y humedad (cuantiles); jerarquías temporal y geográfica completas. |
| Error con versiones distintas de pandas (`cannot insert municipio, already exists`). | Se reescribió el agrupamiento de patrones de ausencia; el código se verificó con pandas 2.2 y 3.1. |

## 3. Decisiones técnicas y su justificación

1. **Validar antes de limpiar.** Un −8 mm de lluvia o 52 °C en Colima son errores, no atípicos;
   si entran a la imputación, contaminan las medianas.
2. **Nunca sobrescribir el valor original.** Imputación, tratamiento de atípicos y escalado
   generan columnas nuevas (`_imputado`, `_tratado`, `_minmax`, `_zscore`), lo que permite
   auditar cada transformación.
3. **Prioridad a la estación en conflictos.** Es una medición in situ; el modelo de reanálisis
   complementa las variables que la estación no mide.
4. **Esquema estricto.** Una columna inesperada indica un cambio en la fuente; es preferible
   detener el pipeline que procesar datos con un significado desconocido.
5. **Cuarentena con motivo legible.** Cada registro rechazado indica la columna, la regla y el
   valor que falló, para que se pueda corregir en origen.

## 4. Resultados

- 488 registros integrados a partir de 366 + 195 crudos; 73 conflictos resueltos.
- 483 registros válidos en Plata y 5 en cuarentena, todos con motivo documentado.
- Ausencia en humedad, ráfagas y temperatura media clasificada como MAR (depende de la fuente);
  en precipitación, como MCAR con riesgo MNAR anotado.
- Oro: 60 registros mensuales (reducción del 88 %) y un conjunto analítico de 26 columnas (de 70).
- 7 pruebas automatizadas aprobadas.

## 5. Dificultades

- Diferencias de entorno entre integrantes (versiones de Python/pandas e intérpretes distintos al
  instalar dependencias) provocaron errores que no aparecían en todas las máquinas.
- En variables con muchos ceros (precipitación), los métodos clásicos de atípicos no funcionan sin
  adaptación.

## 6. Pendientes para la siguiente etapa

- Sustituir los datos sintéticos por la ingesta real de Open-Meteo y CONAGUA.
- Imputar por región (costa / interior) en lugar de usar la mediana estatal.
- Revisar con datos reales los rangos de la puerta de calidad y los umbrales de eventos.
