from __future__ import annotations

import numpy as np
import pandas as pd


# Jerarquía geográfica: estación -> municipio -> región -> estado.
REGION_POR_MUNICIPIO = {
    "Colima": "Zona conurbada Colima-Villa de Álvarez",
    "Villa de Álvarez": "Zona conurbada Colima-Villa de Álvarez",
    "Comala": "Zona norte",
    "Manzanillo": "Costa",
    "Tecomán": "Costa",
}

# Clasificación de lluvia acumulada en 24 h usada por el SMN en sus pronósticos.
CORTES_LLUVIA = [-np.inf, 0.0, 25.0, 50.0, 75.0, 150.0, np.inf]
ETIQUETAS_LLUVIA = ["sin lluvia", "aislada", "fuerte", "muy fuerte", "intensa", "torrencial"]

# Rangos de confort térmico para temperatura máxima (criterio del proyecto).
CORTES_TEMPERATURA = [-np.inf, 25.0, 30.0, 35.0, 40.0, np.inf]
ETIQUETAS_TEMPERATURA = ["templada", "cálida", "calurosa", "muy calurosa", "extrema"]

# Escala de Beaufort agrupada (km/h).
CORTES_VIENTO = [-np.inf, 12.0, 29.0, 50.0, 75.0, np.inf]
ETIQUETAS_VIENTO = ["calma/ligero", "moderado", "fuerte", "muy fuerte", "temporal"]


def agregar_jerarquias_temporales(df: pd.DataFrame) -> pd.DataFrame:
    """Jerarquía conceptual temporal: día -> mes -> trimestre -> temporada -> año."""
    datos = df.copy()
    if "fecha" in datos.columns:
        fecha = pd.to_datetime(datos["fecha"])
        datos["anio"] = fecha.dt.year
        datos["mes"] = fecha.dt.month
        datos["dia"] = fecha.dt.day
        datos["trimestre"] = fecha.dt.quarter
        # En Colima la temporada de lluvias va de junio a octubre; el resto del año es seca.
        datos["temporada"] = np.where(fecha.dt.month.between(6, 10), "lluvias", "seca")
    return datos


def agregar_jerarquias_geograficas(df: pd.DataFrame) -> pd.DataFrame:
    """Jerarquía conceptual geográfica: estación -> municipio -> región -> estado."""
    datos = df.copy()
    if "municipio" not in datos.columns:
        datos["municipio"] = "Colima"
    if "estacion_id" not in datos.columns:
        datos["estacion_id"] = "EST-SIN-ID"
    datos["region"] = datos["municipio"].map(REGION_POR_MUNICIPIO).fillna("Sin región")
    datos["estado"] = "Colima"
    return datos


def discretizar_variables(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte variables continuas en categorías ordinales con cortes documentados."""
    datos = df.copy()
    if "precipitacion_mm" in datos.columns:
        datos["categoria_lluvia"] = pd.cut(datos["precipitacion_mm"], CORTES_LLUVIA,
                                           labels=ETIQUETAS_LLUVIA, right=True).astype(str)
    if "temperatura_maxima" in datos.columns:
        datos["categoria_temperatura"] = pd.cut(datos["temperatura_maxima"], CORTES_TEMPERATURA,
                                                labels=ETIQUETAS_TEMPERATURA, right=False).astype(str)
    if "velocidad_viento_kmh" in datos.columns:
        datos["categoria_viento"] = pd.cut(datos["velocidad_viento_kmh"], CORTES_VIENTO,
                                           labels=ETIQUETAS_VIENTO, right=False).astype(str)
    if "humedad_relativa" in datos.columns:
        # Discretización por igual frecuencia (cuantiles) como alternativa a cortes fijos.
        # rank(method="first") evita cortes repetidos cuando hay muchos valores iguales.
        datos["nivel_humedad"] = pd.qcut(datos["humedad_relativa"].rank(method="first"), q=3,
                                         labels=["baja", "media", "alta"]).astype(str)
    return datos


def discretizar_eventos(df: pd.DataFrame) -> pd.DataFrame:
    """Añade banderas binarias de eventos meteorológicos relevantes (umbrales del proyecto)."""
    datos = df.copy()
    if "precipitacion_mm" in datos.columns:
        datos["lluvia_intensa"] = datos["precipitacion_mm"] >= 30
    if "temperatura_maxima" in datos.columns:
        datos["temperatura_extrema_alta"] = datos["temperatura_maxima"] >= 35
    if "velocidad_viento_kmh" in datos.columns:
        datos["viento_fuerte"] = datos["velocidad_viento_kmh"] >= 30
    return datos
