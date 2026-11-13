from __future__ import annotations

import pandas as pd
import pytest

from src.integracion import homologar_columnas, integrar_fuentes, preparar_fuente_conagua
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


def test_puerta_calidad_documenta_motivo():
    df = pd.DataFrame(
        {
            "fecha": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "municipio": ["Colima", "Colima"],
            "estacion_id": ["E1", "E1"],
            "temperatura_maxima": [30.0, 60.0],
            "temperatura_minima": [20.0, 20.0],
            "fuente_datos": ["open-meteo", "open-meteo"],
            "fecha_extraccion": pd.to_datetime(["2024-01-04", "2024-01-04"]),
        }
    )
    _, invalidos, _ = ejecutar_puerta_calidad(df)
    assert len(invalidos) == 1
    assert "temperatura_maxima" in invalidos.loc[0, "motivo_rechazo"]


def test_puerta_calidad_rechaza_columnas_no_declaradas():
    df = pd.DataFrame(
        {
            "fecha": pd.to_datetime(["2024-01-01"]),
            "municipio": ["Colima"],
            "estacion_id": ["E1"],
            "fuente_datos": ["open-meteo"],
            "fecha_extraccion": pd.to_datetime(["2024-01-04"]),
            "columna_inesperada": [1],
        }
    )
    with pytest.raises(ValueError, match="esquema"):
        ejecutar_puerta_calidad(df)


def test_integracion_resuelve_esquema_tipos_y_conflictos():
    fuente_a = pd.DataFrame(
        {
            "fecha": pd.to_datetime(["2024-03-01", "2024-03-02"]),
            "municipio": ["Villa de Alvarez", "Colima"],
            "estacion_id": ["EST-02", "EST-01"],
            "temperatura_maxima": [30.0, 31.0],
            "temperatura_minima": [18.0, 19.0],
            "precipitacion_mm": [0.0, 1.0],
            "humedad_relativa": [60.0, 65.0],
            "velocidad_viento_kmh": [10.0, 12.0],
            "fuente_datos": ["open-meteo-sintetico"] * 2,
            "fecha_extraccion": pd.to_datetime(["2024-03-05"] * 2),
        }
    )
    fuente_b = pd.DataFrame(
        {
            "FECHA": ["01/03/2024", "05/03/2024"],
            "ESTACION": [" est-02 ", "EST-03"],
            "MUNICIPIO": ["VILLA DE ALVAREZ", "MANZANILLO"],
            "TMAX": ["32.0", "-"],
            "TMIN": ["18.0", "24.0"],
            "PRECIP": ["Inap", "3.5"],
            "VIENTO_MS": ["5.0", "2.0"],
            "FUENTE": ["conagua-sintetico"] * 2,
            "F_EXTRACCION": ["2024-03-06"] * 2,
        }
    )

    integrado = integrar_fuentes(homologar_columnas(fuente_a), preparar_fuente_conagua(fuente_b))

    assert len(integrado) == 3  # el 01/03 en EST-02 se fusiona en un solo registro
    fila = integrado[(integrado["estacion_id"] == "EST-02")].iloc[0]
    assert fila["temperatura_maxima"] == 32.0  # gana la estación (prioridad)
    assert fila["humedad_relativa"] == 60.0  # se complementa con la otra fuente
    assert fila["velocidad_viento_kmh"] == pytest.approx(18.0)  # 5 m/s -> 18 km/h
    assert fila["municipio"] == "Villa de Álvarez"
    assert "temperatura_maxima" in fila["variables_conflicto"]
    est3 = integrado[integrado["estacion_id"] == "EST-03"].iloc[0]
    assert pd.isna(est3["temperatura_maxima"])  # "-" se interpreta como sin dato


def test_atipicos_se_tratan_sin_perder_original():
    df = pd.DataFrame({"temperatura_maxima": [30.0, 31.0, 29.0, 30.5, 30.0, 31.5, 45.0],
                       "precipitacion_mm": [0.0, 0.0, 0.0, 10.0, 12.0, 11.0, 0.0]})
    resultado = detectar_atipicos(df)
    assert bool(resultado.loc[6, "temperatura_maxima_atipico"]) is True
    assert resultado.loc[6, "temperatura_maxima"] == 45.0
    assert resultado.loc[6, "temperatura_maxima_tratado"] < 45.0
    assert not resultado["precipitacion_mm_atipico"].any()  # la lluvia normal no es atípica


def test_pipeline_generates_gold_data(tmp_path):
    report = run_pipeline(tmp_path)

    assert (tmp_path / "data" / "silver" / "weather_silver.csv").exists()
    assert (tmp_path / "data" / "gold" / "weather_gold.csv").exists()
    assert (tmp_path / "data" / "quarantine" / "weather_quarantine.csv").exists()
    assert "reporte_calidad" in report
    assert report["integracion"]["registros_con_conflicto"] > 0
    assert report["reporte_calidad"]["registros_invalidos"] > 0
    cuarentena = pd.read_csv(tmp_path / "data" / "quarantine" / "weather_quarantine.csv")
    assert cuarentena["motivo_rechazo"].notna().all()
