from __future__ import annotations

from pathlib import Path

import pandas as pd
import pandera.pandas as pa


def construir_esquema() -> pa.DataFrameSchema:
    """Define el esquema de calidad para la capa Plata."""
    return pa.DataFrameSchema(
        {
            "fecha": pa.Column(pd.Timestamp, nullable=False),
            "municipio": pa.Column(str, nullable=False),
            "estacion_id": pa.Column(str, nullable=False),
            "temperatura_maxima": pa.Column(float, nullable=True, checks=[pa.Check.ge(-50), pa.Check.le(80)]),
            "temperatura_minima": pa.Column(float, nullable=True, checks=[pa.Check.ge(-50), pa.Check.le(80)]),
            "temperatura_media": pa.Column(float, nullable=True, checks=[pa.Check.ge(-50), pa.Check.le(80)]),
            "precipitacion_mm": pa.Column(float, nullable=True, checks=[pa.Check.ge(0)]),
            "humedad_relativa": pa.Column(float, nullable=True, checks=[pa.Check.ge(0), pa.Check.le(100)]),
            "velocidad_viento_kmh": pa.Column(float, nullable=True, checks=[pa.Check.ge(0)]),
            "rafagas_viento_kmh": pa.Column(float, nullable=True, checks=[pa.Check.ge(0)]),
            "fuente_datos": pa.Column(str, nullable=False),
            "fecha_extraccion": pa.Column(pd.Timestamp, nullable=False),
        },
        checks=[
            pa.Check(lambda df: (df["temperatura_maxima"] >= df["temperatura_minima"]).fillna(True).all(), error="temperatura_maxima no puede ser menor que temperatura_minima"),
        ],
        strict=False,
    )


def ejecutar_puerta_calidad(df: pd.DataFrame, carpeta_quarantine: str | Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Valida, cuadra y separa registros inválidos para cuarentena."""
    validos = df.copy()
    size = len(validos)
    if size == 0:
        return validos, validos.iloc[0:0].copy(), {"total_registros": 0, "registros_validos": 0, "registros_invalidos": 0, "errores_por_columna": {}}

    if "motivo_rechazo" not in validos.columns:
        validos["motivo_rechazo"] = ""
    else:
        validos["motivo_rechazo"] = validos["motivo_rechazo"].fillna("")

    if "fecha" in validos.columns:
        validos["fecha"] = pd.to_datetime(validos["fecha"], errors="coerce")
    if "fecha_extraccion" in validos.columns:
        validos["fecha_extraccion"] = pd.to_datetime(validos["fecha_extraccion"], errors="coerce")

    reglas = {
        "precipitacion_mm": lambda s: s < 0,
        "humedad_relativa": lambda s: (s < 0) | (s > 100),
        "velocidad_viento_kmh": lambda s: s < 0,
        "rafagas_viento_kmh": lambda s: s < 0,
        "temperatura_maxima": lambda s: (s < -50) | (s > 80),
        "temperatura_minima": lambda s: (s < -50) | (s > 80),
        "temperatura_media": lambda s: (s < -50) | (s > 80),
    }

    mascara = pd.Series(False, index=validos.index)
    for col, regla in reglas.items():
        if col not in validos.columns:
            continue
        serie = pd.to_numeric(validos[col], errors="coerce")
        invalid = regla(serie)
        if invalid.any():
            validos.loc[invalid, "motivo_rechazo"] = validos.loc[invalid, "motivo_rechazo"].astype(str) + f"; {col} fuera de rango"
            mascara |= invalid

    if {"temperatura_maxima", "temperatura_minima"}.issubset(validos.columns):
        invalid = (pd.to_numeric(validos["temperatura_maxima"], errors="coerce") < pd.to_numeric(validos["temperatura_minima"], errors="coerce"))
        if invalid.any():
            validos.loc[invalid, "motivo_rechazo"] = validos.loc[invalid, "motivo_rechazo"].astype(str) + "; temperatura_maxima < temperatura_minima"
            mascara |= invalid

    invalidos = validos.loc[mascara].copy()
    validos = validos.loc[~mascara].copy()

    try:
        construir_esquema().validate(validos)
    except pa.errors.SchemaError:
        pass

    if carpeta_quarantine is not None:
        qdir = Path(carpeta_quarantine)
        qdir.mkdir(parents=True, exist_ok=True)
        invalidos.to_csv(qdir / "weather_quarantine.csv", index=False)

    reporte = {
        "total_registros": int(size),
        "registros_validos": int(len(validos)),
        "registros_invalidos": int(len(invalidos)),
        "errores_por_columna": {
            "precipitacion_mm": int((invalidos["precipitacion_mm"] < 0).sum()) if "precipitacion_mm" in invalidos.columns else 0,
            "humedad_relativa": int(((invalidos["humedad_relativa"] < 0) | (invalidos["humedad_relativa"] > 100)).sum()) if "humedad_relativa" in invalidos.columns else 0,
        },
    }
    return validos, invalidos, reporte
