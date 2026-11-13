# Observatorio de Riesgos Meteorológicos y Operativos (ORMO)

Proyecto académico orientado al análisis de sensores y series meteorológicas históricas para Colima, México.

## Objetivo

Implementar una arquitectura Medallion para:

- conservar datos originales en Bronce,
- limpiar y homologar registros en Plata,
- generar indicadores agregados en Oro,
- y enviar a cuarentena los registros inválidos.

## Estructura del repositorio

- `src/ingestion.py`: lectura de las dos fuentes crudas (con datos sintéticos de respaldo).
- `src/integracion.py`: homologación de esquema, tipos, unidades y catálogos; fusión con resolución de conflictos.
- `src/validacion.py`: puerta de calidad con Pandera y cuarentena con motivo.
- `src/limpieza.py`: mecanismo de ausencia (MCAR/MAR/MNAR), imputación, atípicos (IQR + Z robusto) y normalización.
- `src/transformaciones.py`: discretización y jerarquías temporales y geográficas.
- `src/indicadores.py`: reducción por agregación mensual y selección de variables (capa Oro).
- `src/pipeline.py`: flujo principal reproducible.
- `tests/test_pipeline.py`: pruebas automatizadas.
- `docs/E1/ENTREGA.md`: ficha técnica de la entrega E1.
- `docs/relatoria-E1.md`: relatoría de la etapa E1.
- `data/` (generada, no versionada): capas Bronce, Plata, Oro y cuarentena.

## Ejecución

```bash
python -m pip install -r requirements.txt
python src/pipeline.py
python -m pytest
```

## Calidad de datos

- Integra dos fuentes heterogéneas y registra los conflictos resueltos.
- Valida esquema, tipos y rangos con Pandera antes de pasar a Plata.
- Envía los registros inválidos a `data/quarantine/` con su motivo; nunca los borra.
- Diagnostica el mecanismo de ausencia e imputa con una estrategia justificada por variable.
- Detecta atípicos con IQR y Z-Score robusto y los trata por winsorización.
- Conserva las columnas originales y agrega las versiones Min-Max y Z-Score.

## Tag 01

Este repositorio conserva los avances anteriores del proyecto junto con la implementación de la Entrega E1.
