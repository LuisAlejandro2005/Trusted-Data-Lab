from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def generar_datos_muestra() -> pd.DataFrame:
    """Fuente A (estilo Open-Meteo): conjunto sintético diario para Colima."""
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


def generar_fuente_secundaria(seed: int = 42) -> pd.DataFrame:
    """Fuente B (estilo estaciones CONAGUA/SMN): esquema y tipos deliberadamente distintos.

    Diferencias con la fuente A que la integración debe resolver:
    - nombres de columna en mayúsculas y abreviados (FECHA, TMAX, PRECIP...),
    - fecha como texto dd/mm/aaaa,
    - números almacenados como texto, con "Inap" (lluvia inapreciable) y "-" (sin dato),
    - viento en m/s en lugar de km/h,
    - municipio en mayúsculas sin acentos y estación con espacios/minúsculas,
    - sin humedad ni ráfagas,
    - una estación extra (EST-03, Manzanillo) que no existe en la fuente A.
    """
    rng = np.random.default_rng(seed)
    base = generar_datos_muestra()
    filas = []

    # Días que también reporta la fuente A (solapamiento -> conflictos de valores).
    for i in range(2, len(base), 5):
        r = base.loc[i]
        filas.append(
            {
                "FECHA": r["fecha"].strftime("%d/%m/%Y"),
                "ESTACION": f" {r['estacion_id'].lower()} ",
                "MUNICIPIO": str(r["municipio"]).upper(),
                "TMAX": f"{r['temperatura_maxima'] + rng.normal(0.8, 0.3):.1f}",
                "TMIN": f"{r['temperatura_minima'] - rng.normal(0.5, 0.3):.1f}",
                "PRECIP": "Inap" if r["precipitacion_mm"] == 0 and i % 4 == 0 else f"{r['precipitacion_mm']:.1f}",
                "VIENTO_MS": f"{r['velocidad_viento_kmh'] / 3.6:.2f}",
            }
        )

    # Estación exclusiva de la fuente B.
    for i, fecha in enumerate(pd.date_range("2024-01-01", "2024-12-31", freq="3D")):
        lluvioso = fecha.month in (6, 7, 8, 9, 10)
        filas.append(
            {
                "FECHA": fecha.strftime("%d/%m/%Y"),
                "ESTACION": "EST-03",
                "MUNICIPIO": "MANZANILLO",
                "TMAX": f"{31 + rng.normal(0, 1.5):.1f}",
                "TMIN": f"{23 + rng.normal(0, 1.0):.1f}",
                "PRECIP": f"{max(0.0, rng.gamma(1.5, 12.0)) if lluvioso and i % 2 else 0.0:.1f}",
                "VIENTO_MS": f"{abs(rng.normal(4.0, 1.2)):.2f}",
            }
        )

    df = pd.DataFrame(filas)
    # Errores típicos de captura en la fuente B.
    df.loc[3, "TMAX"] = "-"            # sin dato
    df.loc[10, "TMIN"] = "45.0"        # TMIN > TMAX -> cuarentena
    df.loc[len(df) - 5, "PRECIP"] = "-12.0"  # precipitación negativa -> cuarentena
    df["FUENTE"] = "conagua-sintetico"
    df["F_EXTRACCION"] = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    return df


def cargar_datos_bronze(base_dir: str | Path, archivo: str = "weather_bronze.csv") -> pd.DataFrame:
    """Carga la fuente A de Bronce; si no existe, genera un conjunto sintético y lo guarda."""
    base = Path(base_dir)
    bronze_dir = base / "data" / "bronze"
    bronze_dir.mkdir(parents=True, exist_ok=True)
    destino = bronze_dir / archivo

    if destino.exists():
        return pd.read_csv(destino, parse_dates=["fecha", "fecha_extraccion"])

    df = generar_datos_muestra()
    df.to_csv(destino, index=False)
    return df


def cargar_fuente_secundaria(base_dir: str | Path, archivo: str = "conagua_bronze.csv") -> pd.DataFrame:
    """Carga la fuente B de Bronce tal cual (todo como texto); si no existe, la genera."""
    bronze_dir = Path(base_dir) / "data" / "bronze"
    bronze_dir.mkdir(parents=True, exist_ok=True)
    destino = bronze_dir / archivo

    if destino.exists():
        return pd.read_csv(destino, dtype=str, keep_default_na=False)

    df = generar_fuente_secundaria()
    df.to_csv(destino, index=False)
    return df
