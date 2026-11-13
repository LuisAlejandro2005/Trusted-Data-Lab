# Entrega E1 — ORMO

## Objetivo

Implementar un flujo reproducible de ETL para meteorología histórica con arquitectura Medallion y cuarentena de registros inválidos.

## Componentes incluidos

- Ingesta y normaliza datos meteorológicos en un esquema común.
- Diagnostica nulos, imputación y valores atípicos.
- Aplica normalización min-max y z-score dejando columnas originales intactas.
- Ejecuta validación de esquema y rangos con Pandera.
- Guarda registros inválidos en `data/quarantine/`.
- Genera indicadores mensuales para la capa Oro.

## Ejecución

```bash
python src/pipeline.py
```

## Estructura principal

- `src/ingestion.py`: lectura de fuentes y datos sintéticos de respaldo.
- `src/limpieza.py`: diagnóstico, imputación y detección de atípicos.
- `src/integracion.py`: normalización y resolución de conflictos.
- `src/validacion.py`: validación y cuarentena.
- `src/transformaciones.py`: jerarquías temporales y geográficas.
- `src/indicadores.py`: agregados de capa Oro.
- `src/pipeline.py`: flujo principal.

## Consideraciones

- Los registros meteorológicos extremos se conservan si son físicamente plausibles.
- Los valores imposibles o con errores confirmados se envían a cuarentena.
- La trazabilidad de la fuente se conserva en `fuente_datos`.
