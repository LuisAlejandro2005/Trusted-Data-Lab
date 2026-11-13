# Observatorio de Riesgos Meteorológicos y Operativos (ORMO)

Proyecto académico orientado al análisis de sensores y series meteorológicas históricas para Colima, México.

## Objetivo

Implementar una arquitectura Medallion para:

- conservar datos originales en Bronce,
- limpiar y homologar registros en Plata,
- generar indicadores agregados en Oro,
- y enviar a cuarentena los registros inválidos.

## Estructura del repositorio

- `src/ingestion.py`: lectura y generación de datos de respaldo.
- `src/limpieza.py`: diagnóstico de faltantes, imputación y detección de atípicos.
- `src/integracion.py`: homogeneización y resolución de duplicados.
- `src/validacion.py`: validación con Pandera y cuarentena.
- `src/transformaciones.py`: jerarquías temporales y geográficas.
- `src/indicadores.py`: indicadores mensuales para Oro.
- `src/pipeline.py`: flujo principal reproducible.
- `tests/test_pipeline.py`: pruebas automatizadas.
- `data/`: capas Bronce, Plata, Oro y cuarentena.

## Ejecución

```bash
python src/pipeline.py
```

## Calidad de datos

- Detecta valores nulos y porcentajes por variable.
- Imputa con criterios meteorológicos conservadores.
- Identifica valores atípicos con IQR.
- Mantiene columnas originales y agrega versiones min-max y z-score.
- Envía registros inválidos a `data/quarantine/`.

## Tag 01

Este repositorio conserva los avances anteriores del proyecto junto con la implementación de la Entrega E1.
