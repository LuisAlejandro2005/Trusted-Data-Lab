from __future__ import annotations

import pandas as pd

from src.limpieza import diagnosticar_faltantes, detectar_atipicos, imputar_faltantes
from src.pipeline import run_pipeline
from src.validacion import ejecutar_puerta_calidad


def test_diagnostico_y_imputacion():
    df = pd.DataFrame(
        {
            "fecha": pd.date_range("2024-01-01", periods=5, freq="D"),
            "municipio": ["Colima"] * 5,
            "estacion_id": ["E1"] * 5,
            "temperatura_maxima": [28.0, None, 31.0, 29.0, 33.0],
            "temperatura_minima": [18.0, 17.0, None, 16.0, 19.0],
            "precipitacion_mm": [2.0, None, 4.0, 3.0, 1.0],
            "humedad_relativa": [70.0, None, 68.0, 72.0, 74.0],
            "fuente_datos": ["open-meteo"] * 5,
            "fecha_extraccion": pd.to_datetime(["2024-01-02"] * 5),
            "mes": [1] * 5,
        }
    )

    resumen = diagnosticar_faltantes(df)
    assert resumen.loc["temperatura_maxima", "porcentaje"] > 0

    imputado = imputar_faltantes(df)
    assert imputado["temperatura_maxima_imputado"].sum() >= 1
    assert imputado["precipitacion_mm"].notna().all()


def test_puerta_calidad_cuarentena():
    df = pd.DataFrame(
        {
            "fecha": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "municipio": ["Colima", "Colima", "Colima"],
            "estacion_id": ["E1", "E1", "E1"],
            "temperatura_maxima": [25.0, 18.0, 31.0],
            "temperatura_minima": [20.0, 20.0, 35.0],
            "temperatura_media": [22.5, 19.0, 33.0],
            "precipitacion_mm": [1.0, -2.0, 0.5],
            "humedad_relativa": [70.0, 120.0, 65.0],
            "velocidad_viento_kmh": [12.0, 0.0, 5.0],
            "rafagas_viento_kmh": [15.0, 2.0, 3.0],
            "fuente_datos": ["open-meteo", "open-meteo", "open-meteo"],
            "fecha_extraccion": pd.to_datetime(["2024-01-04", "2024-01-04", "2024-01-04"]),
        }
    )

    validos, invalidos, reporte = ejecutar_puerta_calidad(df, carpeta_quarantine="./data/quarantine")
    assert len(validos) == 1
    assert len(invalidos) == 2
    assert reporte["registros_invalidos"] == 2


def test_pipeline_generates_gold_data(tmp_path):
    report = run_pipeline(tmp_path)

    assert (tmp_path / "data" / "silver" / "weather_silver.csv").exists()
    assert (tmp_path / "data" / "gold" / "weather_gold.csv").exists()
    assert (tmp_path / "data" / "quarantine" / "weather_quarantine.csv").exists()
    assert "reporte_calidad" in report
