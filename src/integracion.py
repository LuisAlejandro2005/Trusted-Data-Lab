from __future__ import annotations

import pandas as pd


MAPPING_COLUMNAS = {
    "temperature_max": "temperatura_maxima",
    "temperature_min": "temperatura_minima",
    "temperature_mean": "temperatura_media",
    "precipitation": "precipitacion_mm",
    "relative_humidity": "humedad_relativa",
    "wind_speed": "velocidad_viento_kmh",
    "wind_gust": "rafagas_viento_kmh",
    "date": "fecha",
    "municipality": "municipio",
    "station_id": "estacion_id",
    "source": "fuente_datos",
    "extraction_date": "fecha_extraccion",
}


def homologar_columnas(df: pd.DataFrame, mapeo: dict | None = None) -> pd.DataFrame:
    """Renombra columnas para un esquema común de meteorología."""
    referencia = mapeo or MAPPING_COLUMNAS
    datos = df.rename(columns={k: v for k, v in referencia.items() if k in df.columns and v not in df.columns})
    if "fecha" in datos.columns:
        datos["fecha"] = pd.to_datetime(datos["fecha"], errors="coerce")
    if "fecha_extraccion" in datos.columns:
        datos["fecha_extraccion"] = pd.to_datetime(datos["fecha_extraccion"], errors="coerce")
    return datos


def normalizar_unidades(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte unidades a un esquema consistente para Colima. Los valores ya se manejan en mm y km/h."""
    datos = df.copy()
    if "precipitacion_mm" in datos.columns:
        datos["precipitacion_mm"] = pd.to_numeric(datos["precipitacion_mm"], errors="coerce")
    if "humedad_relativa" in datos.columns:
        datos["humedad_relativa"] = pd.to_numeric(datos["humedad_relativa"], errors="coerce")
    if "temperatura_maxima" in datos.columns:
        datos["temperatura_maxima"] = pd.to_numeric(datos["temperatura_maxima"], errors="coerce")
    if "temperatura_minima" in datos.columns:
        datos["temperatura_minima"] = pd.to_numeric(datos["temperatura_minima"], errors="coerce")
    if "temperatura_media" in datos.columns:
        datos["temperatura_media"] = pd.to_numeric(datos["temperatura_media"], errors="coerce")
    if "velocidad_viento_kmh" in datos.columns:
        datos["velocidad_viento_kmh"] = pd.to_numeric(datos["velocidad_viento_kmh"], errors="coerce")
    if "rafagas_viento_kmh" in datos.columns:
        datos["rafagas_viento_kmh"] = pd.to_numeric(datos["rafagas_viento_kmh"], errors="coerce")
    return datos


def resolver_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    """Elimina duplicados con criterio reproducible sobre fecha, ubicación y fuente."""
    clave = [c for c in ["fecha", "municipio", "estacion_id", "fuente_datos"] if c in df.columns]
    if not clave:
        return df
    return df.drop_duplicates(subset=clave, keep="last").reset_index(drop=True)


def integrar_fuentes(df1: pd.DataFrame, df2: pd.DataFrame | None = None) -> pd.DataFrame:
    """Integra dos fuentes distintas conservando trazabilidad."""
    if df2 is None:
        return resolver_duplicados(df1.copy())
    integrados = pd.concat([df1, df2], ignore_index=True, sort=False)
    return resolver_duplicados(integrados)
