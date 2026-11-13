from __future__ import annotations

from pathlib import Path

import pandas as pd


def generar_datos_muestra() -> pd.DataFrame:
    """Genera un conjunto sintético de datos meteorológicos para Colima."""
    fechas = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    data = []
    for i, fecha in enumerate(fechas):
        municipio = "Colima" if i % 3 == 0 else "Villa de Alvarez"
        estacion = "EST-01" if i % 2 == 0 else "EST-02"
        data.append(
            {
                "fecha": fecha,
                "municipio": municipio,
                "estacion_id": estacion,
                "temperatura_maxima": 27 + (i % 12) * 1.5 + (i % 5) * 0.6,
                "temperatura_minima": 18 + (i % 9) * 1.2,
                "temperatura_media": 22 + (i % 10) * 0.9,
                "precipitacion_mm": 0.0 if i % 7 else 12.5 + (i % 4) * 8.4,
                "humedad_relativa": 62 + (i % 9) * 3,
                "velocidad_viento_kmh": 10 + (i % 8) * 2.4,
                "rafagas_viento_kmh": 18 + (i % 6) * 3.5,
                "fuente_datos": "open-meteo-sintetico",
                "fecha_extraccion": pd.Timestamp.now(tz="UTC").normalize(),
            }
        )

    df = pd.DataFrame(data)
    df.loc[5, "precipitacion_mm"] = None
    df.loc[12, "humedad_relativa"] = None
    df.loc[20, "temperatura_maxima"] = 52.0
    df.loc[21, "temperatura_maxima"] = 16.0
    df.loc[23, "precipitacion_mm"] = -8.0
    return df


def cargar_datos_bronze(base_dir: str | Path, archivo: str = "weather_bronze.csv") -> pd.DataFrame:
    """Carga datos de Bronce; si no existen, genera un conjunto sintético y lo guarda."""
    base = Path(base_dir)
    bronze_dir = base / "data" / "bronze"
    bronze_dir.mkdir(parents=True, exist_ok=True)
    destino = bronze_dir / archivo

    if destino.exists():
        return pd.read_csv(destino, parse_dates=["fecha", "fecha_extraccion"])

    df = generar_datos_muestra()
    df.to_csv(destino, index=False)
    return df
