from __future__ import annotations

from pathlib import Path

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

from src.integracion import CATALOGO_MUNICIPIOS


# Rangos físicamente plausibles para el estado de Colima (no son umbrales de alerta).
RANGOS = {
    "temperatura_maxima": (-5.0, 50.0),
    "temperatura_minima": (-5.0, 50.0),
    "temperatura_media": (-5.0, 50.0),
    "precipitacion_mm": (0.0, 500.0),
    "humedad_relativa": (0.0, 100.0),
    "velocidad_viento_kmh": (0.0, 250.0),
    "rafagas_viento_kmh": (0.0, 300.0),
}

CHECK_TMAX_TMIN = "temperatura_maxima >= temperatura_minima"
ERROR_TMAX_TMIN = "temperatura_maxima no puede ser menor que temperatura_minima"


def _tmax_mayor_igual_tmin(df: pd.DataFrame) -> pd.Series:
    tmax, tmin = df["temperatura_maxima"], df["temperatura_minima"]
    return tmax.isna() | tmin.isna() | (tmax >= tmin)


def construir_esquema() -> pa.DataFrameSchema:
    """Esquema estricto de entrada a la capa Plata.

    - `strict=True`: cualquier columna no declarada detiene el pipeline (deriva de esquema).
    - `coerce=True`: los tipos se fuerzan; un valor que no se puede convertir es un error de fila.
    - Las medidas admiten nulos (se imputan después), pero si existen deben estar en rango.
    """
    hoy = pd.Timestamp.now().normalize() + pd.Timedelta(days=1)
    columnas = {
        "fecha": pa.Column(pd.Timestamp, nullable=False, coerce=True,
                           checks=pa.Check.in_range(pd.Timestamp("2000-01-01"), hoy)),
        "municipio": pa.Column(str, nullable=False,
                               checks=pa.Check.isin(sorted(CATALOGO_MUNICIPIOS.values()))),
        "estacion_id": pa.Column(str, nullable=False, checks=pa.Check.str_length(min_value=1)),
        "fuente_datos": pa.Column(str, nullable=False),
        "fecha_extraccion": pa.Column(pd.Timestamp, nullable=False, coerce=True),
        "n_conflictos": pa.Column(int, required=False, coerce=True, checks=pa.Check.ge(0)),
        "variables_conflicto": pa.Column(str, required=False, nullable=True),
    }
    for col, (minimo, maximo) in RANGOS.items():
        columnas[col] = pa.Column(float, nullable=True, coerce=True, required=False,
                                  checks=pa.Check.in_range(minimo, maximo))

    return pa.DataFrameSchema(
        columnas,
        checks=[pa.Check(_tmax_mayor_igual_tmin, name=CHECK_TMAX_TMIN,
                         error=ERROR_TMAX_TMIN)],
        unique=["fecha", "estacion_id"],
        report_duplicates="all",
        strict=True,
        name="puerta_calidad_plata",
    )


def _casos_por_fila(casos: pd.DataFrame) -> pd.DataFrame:
    """Normaliza los failure_cases de Pandera: un caso por (fila, regla, columna).

    Las reglas a nivel de DataFrame (tmax >= tmin) se reportan una vez por cada columna de la
    fila; aquí se colapsan a un solo caso con columna "temperatura_maxima/temperatura_minima".
    """
    casos = casos.dropna(subset=["index"]).copy()
    casos["index"] = casos["index"].astype(int)
    for col in ["column", "check", "failure_case"]:
        casos[col] = casos[col].astype(object)
    es_tmax_tmin = casos["check"].astype(str).isin([CHECK_TMAX_TMIN, ERROR_TMAX_TMIN])
    casos.loc[es_tmax_tmin, "check"] = CHECK_TMAX_TMIN
    casos.loc[es_tmax_tmin, "column"] = "temperatura_maxima/temperatura_minima"
    casos.loc[es_tmax_tmin, "failure_case"] = "no se cumple"
    casos["column"] = casos["column"].fillna("registro")
    return casos.drop_duplicates(subset=["index", "check", "column"])


def _motivos_por_fila(casos: pd.DataFrame) -> pd.Series:
    """Convierte los casos de falla en un motivo legible por fila."""
    motivo = casos["column"].astype(str) + ": " + casos["check"].astype(str) + " (valor=" + casos["failure_case"].astype(str) + ")"
    return motivo.groupby(casos["index"]).agg("; ".join)


def ejecutar_puerta_calidad(df: pd.DataFrame, carpeta_quarantine: str | Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Valida con Pandera (modo lazy) y separa los registros inválidos hacia cuarentena.

    Ningún registro se elimina en silencio: cada fila rechazada conserva sus valores originales
    y recibe `motivo_rechazo`, `regla_fallida` y `fecha_cuarentena`. Los errores a nivel de
    esquema (columnas faltantes o no declaradas) no son de una fila concreta: detienen el pipeline.
    """
    datos = df.reset_index(drop=True).copy()
    size = len(datos)
    esquema = construir_esquema()

    try:
        validos = esquema.validate(datos, lazy=True)
        casos = pd.DataFrame(columns=["index", "column", "check", "failure_case"])
    except SchemaErrors as err:
        de_esquema = err.failure_cases[err.failure_cases["index"].isna()]
        if not de_esquema.empty:
            raise ValueError(
                "La estructura del lote no cumple el esquema de Plata: "
                + "; ".join(f"{r.column}: {r.check}" for r in de_esquema.itertuples())
            ) from err
        casos = _casos_por_fila(err.failure_cases)
        validos = esquema.validate(datos.drop(index=casos["index"].unique()), lazy=True)

    filas_invalidas = sorted(casos["index"].unique())
    invalidos = datos.loc[filas_invalidas].copy()
    if filas_invalidas:
        invalidos["motivo_rechazo"] = _motivos_por_fila(casos)
        invalidos["regla_fallida"] = casos.groupby("index")["check"].agg(lambda c: ",".join(map(str, c)))
    else:
        invalidos["motivo_rechazo"] = pd.Series(dtype=str)
        invalidos["regla_fallida"] = pd.Series(dtype=str)
    invalidos["fecha_cuarentena"] = pd.Timestamp.now().floor("s")

    if carpeta_quarantine is not None:
        qdir = Path(carpeta_quarantine)
        qdir.mkdir(parents=True, exist_ok=True)
        invalidos.to_csv(qdir / "weather_quarantine.csv", index=False)

    reporte = {
        "total_registros": int(size),
        "registros_validos": int(len(validos)),
        "registros_invalidos": int(len(invalidos)),
        "errores_por_columna": {str(k): int(v) for k, v in casos["column"].value_counts().items()},
        "errores_por_regla": {str(k): int(v) for k, v in casos["check"].value_counts().items()},
    }
    return validos.reset_index(drop=True), invalidos.reset_index(drop=True), reporte
