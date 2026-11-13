from __future__ import annotations

import pandas as pd


def generar_agregados_mensuales(df: pd.DataFrame) -> pd.DataFrame:
    """Genera una capa Oro con indicadores mensuales por municipio y estación."""
    datos = df.copy()
    if "mes" not in datos.columns:
        datos["mes"] = pd.to_datetime(datos["fecha"]).dt.month
    if "anio" not in datos.columns:
        datos["anio"] = pd.to_datetime(datos["fecha"]).dt.year
    if "municipio" not in datos.columns:
        datos["municipio"] = "Colima"

    resumen = (
        datos.groupby(["municipio", "estacion_id", "anio", "mes"], dropna=False)
        .agg(
            precipitacion_acumulada_mm=("precipitacion_mm", "sum"),
            temperatura_maxima_mensual_c=("temperatura_maxima", "max"),
            temperatura_minima_mensual_c=("temperatura_minima", "min"),
            dias_lluvia_intensa=("lluvia_intensa", "sum"),
            dias_temperatura_extrema=("temperatura_extrema_alta", "sum"),
            dias_viento_fuerte=("viento_fuerte", "sum"),
        )
        .reset_index()
    )
    return resumen
