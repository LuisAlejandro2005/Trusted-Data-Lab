from __future__ import annotations

import pandas as pd


def agregar_jerarquias_temporales(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega jerarquías temporales para consultas futuras del observatorio."""
    datos = df.copy()
    if "fecha" in datos.columns:
        datos["anio"] = pd.to_datetime(datos["fecha"]).dt.year
        datos["mes"] = pd.to_datetime(datos["fecha"]).dt.month
        datos["dia"] = pd.to_datetime(datos["fecha"]).dt.day
    return datos


def agregar_jerarquias_geograficas(df: pd.DataFrame) -> pd.DataFrame:
    """Establece un catálogo base para municipios y estaciones."""
    datos = df.copy()
    if "municipio" not in datos.columns:
        datos["municipio"] = "Colima"
    if "estacion_id" not in datos.columns:
        datos["estacion_id"] = "EST-SIN-ID"
    return datos


def discretizar_eventos(df: pd.DataFrame) -> pd.DataFrame:
    """Añade indicadores simples de eventos meteorológicos relevantes."""
    datos = df.copy()
    if "precipitacion_mm" in datos.columns:
        datos["lluvia_intensa"] = datos["precipitacion_mm"] >= 30
    if "temperatura_maxima" in datos.columns:
        datos["temperatura_extrema_alta"] = datos["temperatura_maxima"] >= 35
    if "velocidad_viento_kmh" in datos.columns:
        datos["viento_fuerte"] = datos["velocidad_viento_kmh"] >= 30
    return datos
