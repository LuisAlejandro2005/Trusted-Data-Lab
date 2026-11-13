# Ficha técnica — Entrega E1 · ORMO

**Proyecto:** Observatorio de Riesgos Meteorológicos y Operativos (ORMO) — Colima, México
**Entrega:** E1 · Automatización hacia las capas Plata y Oro con puerta de calidad y cuarentena
**Tag:** `e1`

## Objetivo

Automatizar el flujo de datos Bronce → Plata → Oro mediante un pipeline de limpieza estadística
y una puerta de calidad automática (Pandera) que envía los registros inválidos a cuarentena con
motivo documentado.

## Ejecución

```bash
python -m pip install -r requirements.txt
python src/pipeline.py      # genera data/bronze, data/silver, data/gold, data/quarantine
python -m pytest            # 7 pruebas automatizadas
```

Compatibilidad verificada con pandas 2.2 y 3.1, y Pandera 0.36.

## Flujo del pipeline (`src/pipeline.py`)

| # | Etapa | Módulo | Salida |
|---|-------|--------|--------|
| 1 | Ingesta de dos fuentes crudas | `ingestion.py` | `data/bronze/weather_bronze.csv`, `data/bronze/conagua_bronze.csv` |
| 2 | Integración y resolución de conflictos | `integracion.py` | registro único por (fecha, estación) |
| 3 | Puerta de calidad (Pandera) | `validacion.py` | válidos → Plata · inválidos → `data/quarantine/weather_quarantine.csv` |
| 4 | Limpieza y preprocesamiento | `limpieza.py`, `transformaciones.py` | `data/silver/weather_silver.csv`, `data/silver/diagnostico_ausencia.csv` |
| 5 | Reducción y agregación | `indicadores.py` | `data/gold/weather_gold.csv`, `data/gold/weather_gold_analitico.csv` |
| — | Reporte de ejecución | `pipeline.py` | `data/execution_report.json` |

La puerta de calidad va **antes** de la limpieza para que los valores físicamente imposibles no
sesguen las medianas de imputación ni las escalas de normalización.

## Cumplimiento de entregables

### 1. Pipeline de limpieza y preprocesamiento

| Requisito | Implementación |
|-----------|----------------|
| Valores faltantes: mecanismo e imputación | `diagnosticar_mecanismo_por_variable`: compara la tasa de ausencia entre fuentes, estaciones, municipios y meses. Si difiere más de 20 puntos → **MAR**; si es homogénea → **MCAR**; se anota el riesgo **MNAR** donde aplica (pluviómetros). `imputar_faltantes` usa una estrategia justificada por variable (ver tabla abajo) y marca cada imputación en `<col>_imputado`. |
| Atípicos y ruido | `detectar_atipicos`: **IQR** (cercas de Tukey) + **Z-Score robusto** (MAD, umbral 3.5). Tratamiento por **winsorización** en `<col>_tratado`; el valor original se conserva. Para la precipitación, las cercas se calculan sólo con días lluviosos (el IQR global es 0). |
| Normalización y estandarización | `normalizar_variables`: `<col>_minmax` y `<col>_zscore` calculados sobre la versión tratada. |
| Discretización y jerarquías conceptuales | `discretizar_variables`: lluvia (escala SMN), temperatura, viento (Beaufort agrupada) y humedad (cuantiles). Jerarquías: día → mes → trimestre → temporada → año, y estación → municipio → región → estado. |
| Reducción de datos | **Agregación** diaria → mensual por estación (`weather_gold.csv`) y **selección de variables** que elimina columnas de varianza nula y redundantes con \|r\| > 0.95 (`weather_gold_analitico.csv`). |

Estrategias de imputación:

| Variable | Estrategia | Justificación |
|----------|------------|---------------|
| Temperaturas, humedad, viento | Mediana por estación y mes; respaldo: mediana del mes | Fuerte ciclo estacional; la mediana es robusta a atípicos. |
| Temperatura media | (máx + mín) / 2 del mismo día | Relación física directa con variables observadas. |
| Precipitación | Mediana del mes | Distribución muy sesgada; evita inventar lluvia en temporada seca. |

### 2. Integración y resolución de conflictos

Se fusionan dos fuentes heterogéneas:

| Aspecto | Fuente A (estilo Open-Meteo) | Fuente B (estilo estaciones CONAGUA/SMN) | Resolución |
|---------|------------------------------|------------------------------------------|------------|
| Nombres | `temperatura_maxima`, … | `TMAX`, `TMIN`, `PRECIP`, … | `MAPPING_CONAGUA` |
| Fecha | `datetime` ISO | texto `dd/mm/aaaa` | `to_datetime(format=…)` |
| Tipos | numéricos | texto con `"Inap"` y `"-"` | `"Inap"` → 0 mm, `"-"` → nulo, `to_numeric` |
| Viento | km/h | m/s | × 3.6 |
| Catálogos | `Villa de Alvarez` | `VILLA DE ALVAREZ`, `" est-02 "` | catálogo oficial de municipios, normalización de estaciones |
| Variables | incluye humedad y ráfagas | no las mide | complementación |
| Cobertura | EST-01, EST-02 | EST-01, EST-02 y EST-03 (Manzanillo) | unión externa |

Si ambas fuentes reportan la misma (fecha, estación) con valores distintos, **prevalece la
estación** (observación in situ) y queda registro en `n_conflictos`, `variables_conflicto`, y el
linaje en `fuente_datos` (`conagua-sintetico+open-meteo-sintetico`).

### 3. Puerta de calidad automática (Pandera)

Esquema `puerta_calidad_plata` en `validacion.py`:

- `strict=True`: una columna no declarada (o una obligatoria ausente) **detiene el pipeline**.
- `coerce=True`: un valor que no puede convertirse al tipo declarado es un error de fila.
- Rangos plausibles para Colima: temperaturas −5 a 50 °C, precipitación 0 a 500 mm,
  humedad 0 a 100 %, viento 0 a 250 km/h, ráfagas 0 a 300 km/h.
- Regla entre columnas: `temperatura_maxima >= temperatura_minima`.
- Catálogo de municipios, fechas entre 2000-01-01 y hoy, unicidad de (fecha, estación).

Validación en modo `lazy`: se recopilan **todas** las fallas. Cada registro rechazado se escribe
en cuarentena con sus valores originales más `motivo_rechazo`, `regla_fallida` y
`fecha_cuarentena`. Ningún registro se elimina en silencio.

## Resultados de la ejecución de referencia

| Métrica | Valor |
|---------|-------|
| Registros fuente A / fuente B | 366 / 195 |
| Registros integrados | 488 |
| Registros con conflicto resuelto | 73 |
| Válidos (Plata) | 483 |
| En cuarentena | 5 (1 temperatura fuera de rango, 2 precipitaciones negativas, 2 tmax < tmin) |
| Mecanismo de ausencia | humedad, ráfagas y temperatura media: MAR (dependen de la fuente); precipitación: MCAR |
| Oro mensual | 60 registros (reducción del 88 %) |
| Conjunto analítico | 70 → 26 columnas |

## Limitaciones conocidas

- **Los datos son sintéticos**; reproducen los problemas reales esperados (esquemas distintos,
  convenciones de captura, errores, conflictos). La conexión a Open-Meteo y CONAGUA es trabajo
  de la siguiente etapa.
- Los umbrales de eventos (lluvia ≥ 30 mm, temperatura ≥ 35 °C, viento ≥ 30 km/h) son
  criterios del proyecto, no alertas oficiales.
- La humedad de EST-03 (costa) se imputa con la mediana mensual de estaciones del interior, lo
  que puede subestimarla; con datos reales convendrá imputar por región.
