from __future__ import annotations

import pandas as pd


def generar_agregados_mensuales(df: pd.DataFrame) -> pd.DataFrame:
    """Reducción por agregación: de registros diarios a indicadores mensuales por estación (capa Oro)."""
    datos = df.copy()
    if "mes" not in datos.columns:
        datos["mes"] = pd.to_datetime(datos["fecha"]).dt.month
    if "anio" not in datos.columns:
        datos["anio"] = pd.to_datetime(datos["fecha"]).dt.year
    if "municipio" not in datos.columns:
        datos["municipio"] = "Colima"
    for bandera in ["lluvia_intensa", "temperatura_extrema_alta", "viento_fuerte"]:
        if bandera not in datos.columns:
            datos[bandera] = False

    agregaciones = {
        "dias_registrados": ("fecha", "count"),
        "precipitacion_acumulada_mm": ("precipitacion_mm", "sum"),
        "temperatura_maxima_mensual_c": ("temperatura_maxima", "max"),
        "temperatura_minima_mensual_c": ("temperatura_minima", "min"),
        "dias_lluvia_intensa": ("lluvia_intensa", "sum"),
        "dias_temperatura_extrema": ("temperatura_extrema_alta", "sum"),
        "dias_viento_fuerte": ("viento_fuerte", "sum"),
    }
    if "temperatura_media" in datos.columns:
        agregaciones["temperatura_media_mensual_c"] = ("temperatura_media", "mean")
    if "humedad_relativa" in datos.columns:
        agregaciones["humedad_relativa_media"] = ("humedad_relativa", "mean")

    claves = [c for c in ["estado", "region", "municipio", "estacion_id", "anio", "mes"] if c in datos.columns]
    return datos.groupby(claves, dropna=False).agg(**agregaciones).reset_index().round(2)


def seleccionar_variables(df: pd.DataFrame, umbral_correlacion: float = 0.95) -> tuple[pd.DataFrame, dict]:
    """Reducción por selección de variables para el conjunto analítico diario.

    1. Elimina columnas constantes (varianza nula: no aportan información).
    2. Entre variables numéricas con |correlación de Pearson| > umbral, conserva sólo la primera
       (las demás son redundantes).
    Devuelve el conjunto reducido y un resumen de qué se eliminó y por qué.
    """
    constantes = [c for c in df.columns if df[c].nunique(dropna=False) <= 1]
    datos = df.drop(columns=constantes)

    numericas = datos.select_dtypes("number").drop(columns=["anio", "mes", "dia", "trimestre"], errors="ignore")
    numericas = numericas.loc[:, numericas.std() > 0]
    correlacion = numericas.corr().abs()
    redundantes: dict[str, str] = {}
    columnas = list(correlacion.columns)
    for i, col in enumerate(columnas):
        if col in redundantes:
            continue
        for otra in columnas[i + 1:]:
            if otra not in redundantes and correlacion.loc[col, otra] > umbral_correlacion:
                redundantes[otra] = col
    datos = datos.drop(columns=list(redundantes))

    resumen = {
        "columnas_entrada": int(df.shape[1]),
        "columnas_salida": int(datos.shape[1]),
        "eliminadas_por_varianza_nula": constantes,
        "eliminadas_por_redundancia": {k: f"|r| > {umbral_correlacion} con {v}" for k, v in redundantes.items()},
    }
    return datos, resumen
